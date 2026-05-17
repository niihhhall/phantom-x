import logging
import random
import asyncio
from typing import List, Dict, Any
from app.core.database import get_db_client
from app.workers.browser_engine import human_delay, LinkedInBrowser

logger = logging.getLogger("phantomx.warmup")
logger.setLevel(logging.INFO)

# High-authority target profiles to safely visit during warm-up
FAMOUS_PROFILES = [
    "https://www.linkedin.com/in/williamhgates",
    "https://www.linkedin.com/in/satyanadella",
    "https://www.linkedin.com/in/reidhoffman",
    "https://www.linkedin.com/in/jeffweiner08",
    "https://www.linkedin.com/in/ryan-roslansky",
    "https://www.linkedin.com/in/gwynne-shotwell",
    "https://www.linkedin.com/in/sherylsandberg",
    "https://www.linkedin.com/in/marcbenioff",
    "https://www.linkedin.com/in/richardbranson",
    "https://www.linkedin.com/in/brianchesky"
]

def get_warmup_limits(day: int) -> Dict[str, Any]:
    """Calculate target limit constraints and profile visits for the current warm-up day (F-05)."""
    if day <= 3:
        return {"visits_count": 5, "daily_limit": 5}
    elif day <= 7:
        return {"visits_count": 10, "daily_limit": 10}
    elif day <= 14:
        return {"visits_count": 25, "daily_limit": 25}
    else:
        return {"visits_count": 0, "daily_limit": 50, "complete": True}

async def run_warmup_actions(account_id: str, browser: LinkedInBrowser) -> dict:
    """
    Perform humanized warm-up actions: determine daily visit bounds, pick famous profiles,
    execute sequential navigations with safe delays, and increment warm-up progression in CRM.
    """
    client = get_db_client()
    res = await client.table("linkedin_accounts").select("*").eq("id", account_id).execute()
    if not res.data:
        logger.error(f"LinkedIn account ID {account_id} not found for warm-up execution.")
        return {"success": False, "error": "Account not found"}
        
    account = res.data[0]
    current_day = account.get("warmup_day", 1)
    
    limits = get_warmup_limits(current_day)
    
    if limits.get("complete"):
        logger.info(f"Account {account_id} has finished warm-up progression. Graduating to active status.")
        await client.table("linkedin_accounts").update({
            "status": "active",
            "daily_limit": 50,
            "actions_today": 0
        }).eq("id", account_id).execute()
        return {"success": True, "graduated": True}
        
    visits_needed = limits["visits_count"]
    daily_limit = limits["daily_limit"]
    
    logger.info(f"Account {account_id} warm-up Day {current_day}. Executing {visits_needed} simulation visits...")
    
    # Pick a unique set of profiles to visit
    targets = random.sample(FAMOUS_PROFILES, min(visits_needed, len(FAMOUS_PROFILES)))
    visits_success = 0
    
    for url in targets:
        try:
            logger.info(f"Warm-up navigation visit: {url}")
            await browser.page.goto(url, wait_until="domcontentloaded")
            await scroll_around_slightly(browser.page)
            # Long human-like delays to emulate natural profile viewing
            await human_delay(7.0, 15.0)
            visits_success += 1
        except Exception as e:
            logger.error(f"Failed warm-up visit to {url}: {e}")
            
    # Advance warm-up state in CRM database
    next_day = current_day + 1
    update_payload = {
        "warmup_day": next_day,
        "daily_limit": daily_limit,
        "actions_today": account.get("actions_today", 0) + visits_success
    }
    
    # Graduating to active state check
    if next_day >= 15:
        logger.info(f"Warm-up completed successfully. Account ID {account_id} is graduating!")
        update_payload["status"] = "active"
        update_payload["daily_limit"] = 50
        
    await client.table("linkedin_accounts").update(update_payload).eq("id", account_id).execute()
    
    return {
        "success": True,
        "day_processed": current_day,
        "visits_attempted": len(targets),
        "visits_success": visits_success,
        "graduated": next_day >= 15
    }

async def scroll_around_slightly(page):
    """Simulate user scrolling up and down briefly."""
    try:
        await page.evaluate("window.scrollBy(0, 300)")
        await asyncio.sleep(random.uniform(0.5, 1.2))
        await page.evaluate("window.scrollBy(0, -150)")
    except Exception:
        pass

async def tick_warmup(account_id: str) -> str:
    """Trigger the queueing of a warmup background job in Redis (F-05)."""
    from app.core.queue import enqueue_job
    logger.info(f"Scheduling warm-up tasks for LinkedIn Account: {account_id}")
    
    client = get_db_client()
    res = await client.table("linkedin_accounts").select("workspace_id").eq("id", account_id).execute()
    workspace_id = res.data[0].get("workspace_id") if res.data else None
    
    if not workspace_id:
        raise ValueError(f"Could not resolve workspace ID for account: {account_id}")
        
    job_id = await enqueue_job(
        job_type="warmup",
        payload={"account_id": account_id, "workspace_id": workspace_id},
        workspace_id=workspace_id
    )
    return job_id
