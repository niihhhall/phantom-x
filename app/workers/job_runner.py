import asyncio
import json
import logging
import sys
import redis
from app.config import settings
from app.core.database import (
    get_db_client,
    update_job_status,
    upsert_lead,
    update_lead_stage
)
from app.workers.browser_engine import LinkedInBrowser

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("phantomx.worker")

# Initialize Redis connection
try:
    redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
    logger.info("Connected to Redis successfully.")
except Exception as e:
    logger.critical(f"Failed to connect to Redis: {e}")
    sys.exit(1)

QUEUE_NAME = "phantomx:jobs:queue"

import datetime
from app.core.auth import decrypt_cookie

async def get_account_cookie(account_id: str) -> str:
    """Fetch LinkedIn account from database and decrypt li_at session cookie."""
    client = get_db_client()
    res = await client.table("linkedin_accounts").select("*").eq("id", account_id).execute()
    if not res.data:
        raise ValueError(f"LinkedIn account {account_id} not found in database.")
    account = res.data[0]
    return decrypt_cookie(account["li_at_encrypted"])

async def handle_health_check(job_id: str, payload: dict) -> dict:
    """Execute a login session validation for a specific account."""
    workspace_id = payload.get("workspace_id")
    account_id = payload.get("account_id")
    
    if not workspace_id or not account_id:
        raise ValueError("Missing required fields for health check: workspace_id or account_id")
        
    li_at = await get_account_cookie(account_id)
    
    # Reload account details to get proxy country
    client = get_db_client()
    acc_res = await client.table("linkedin_accounts").select("*").eq("id", account_id).execute()
    proxy_country = acc_res.data[0].get("proxy_country", "US") if acc_res.data else "US"
    
    async with LinkedInBrowser(workspace_id, account_id, proxy_country) as browser:
        is_active = await browser.login_via_cookie(li_at)
        status = "active" if is_active else "expired"
        
        # Update database status
        await client.table("linkedin_accounts").update({
            "status": status,
            "last_health_check": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }).eq("id", account_id).execute()
        
        return {"status": status, "is_active": is_active}

async def handle_scrape(job_id: str, payload: dict) -> dict:
    """Navigate to and scrape a prospect's profile, saving results in the database."""
    workspace_id = payload.get("workspace_id")
    account_id = payload.get("account_id")
    profile_url = payload.get("profile_url")
    campaign_id = payload.get("campaign_id")
    
    if not workspace_id or not account_id or not profile_url:
        raise ValueError("Missing required fields for scraping job")
        
    li_at = await get_account_cookie(account_id)
    
    client = get_db_client()
    acc_res = await client.table("linkedin_accounts").select("*").eq("id", account_id).execute()
    proxy_country = acc_res.data[0].get("proxy_country", "US") if acc_res.data else "US"
    
    async with LinkedInBrowser(workspace_id, account_id, proxy_country) as browser:
        logged_in = await browser.login_via_cookie(li_at)
        if not logged_in:
            raise RuntimeError("Failed to login using session cookie during scraping.")
            
        profile_data = await browser.scrape_profile(profile_url)
        profile_data["workspace_id"] = workspace_id
        if campaign_id:
            profile_data["campaign_id"] = campaign_id
            
        # Save scraped profile data to database
        saved_lead = await upsert_lead(profile_data)
        return {"scraped_lead_id": saved_lead.get("id"), "full_name": profile_data.get("full_name")}

async def handle_connect(job_id: str, payload: dict) -> dict:
    """Send connection request to prospect and update pipeline stage."""
    workspace_id = payload.get("workspace_id")
    account_id = payload.get("account_id")
    profile_url = payload.get("profile_url")
    lead_id = payload.get("lead_id")
    message = payload.get("message")
    
    if not workspace_id or not account_id or not profile_url or not lead_id:
        raise ValueError("Missing required fields for connection job")
        
    li_at = await get_account_cookie(account_id)
    
    client = get_db_client()
    acc_res = await client.table("linkedin_accounts").select("*").eq("id", account_id).execute()
    proxy_country = acc_res.data[0].get("proxy_country", "US") if acc_res.data else "US"
    
    async with LinkedInBrowser(workspace_id, account_id, proxy_country) as browser:
        logged_in = await browser.login_via_cookie(li_at)
        if not logged_in:
            raise RuntimeError("Failed to login using session cookie during connection request.")
            
        success = await browser.send_connection_request(profile_url, message)
        if success:
            await update_lead_stage(lead_id, "sent")
            # Log action usage to account limits
            await client.rpc("increment_actions", {"account_id": account_id}).execute()
            
        return {"success": success, "lead_id": lead_id}

async def process_job(job_data: dict):
    """Router to coordinate job execution based on type."""
    job_id = job_data.get("id")
    job_type = job_data.get("type")
    payload = job_data.get("payload", {})
    
    logger.info(f"Processing job {job_id} of type: {job_type}")
    await update_job_status(job_id, "running")
    
    try:
        if job_type == "health_check":
            res = await handle_health_check(job_id, payload)
        elif job_type == "scrape":
            res = await handle_scrape(job_id, payload)
        elif job_type == "connect":
            res = await handle_connect(job_id, payload)
        else:
            raise ValueError(f"Unknown job type: {job_type}")
            
        logger.info(f"Job {job_id} finished successfully.")
        await update_job_status(job_id, "done", result=res)
    except Exception as err:
        logger.error(f"Job {job_id} failed: {err}", exc_info=True)
        await update_job_status(job_id, "failed", result={"error": str(err)})

async def main():
    logger.info("Initializing Phantom-X worker process...")
    
    # Loop and pull tasks from Redis
    while True:
        try:
            # BLPOP blocks until an item is available in Redis list
            task = redis_client.blpop(QUEUE_NAME, timeout=5)
            if task:
                _, item_str = task
                logger.info(f"Retrieved task: {item_str}")
                job_data = json.loads(item_str)
                await process_job(job_data)
        except redis.RedisError as re:
            logger.error(f"Redis connection issue: {re}")
            await asyncio.sleep(5)
        except Exception as e:
            logger.error(f"Error in main loop: {e}")
            await asyncio.sleep(1)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Worker stopped by user.")
