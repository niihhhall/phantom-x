import json
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
import redis
from app.config import settings
from app.core.auth import get_current_user, encrypt_cookie, decrypt_cookie
from app.core.database import get_db_client, create_job
from app.core.billing import verify_linkedin_account_quota

router = APIRouter(prefix="/accounts", tags=["accounts"])

class AccountCreate(BaseModel):
    label: str
    li_at_raw: str
    proxy_country: Optional[str] = "US"

class LimitUpdate(BaseModel):
    daily_limit: int

async def queue_health_check_job(workspace_id: str, account_id: str) -> dict:
    """Helper to register a health check job in the database and push to Redis."""
    # 1. Create job in Supabase
    job_payload = {
        "workspace_id": workspace_id,
        "account_id": account_id
    }
    
    job_res = await create_job({
        "workspace_id": workspace_id,
        "type": "health_check",
        "payload": job_payload,
        "status": "queued"
    })
    
    # 2. Push job payload to Redis
    try:
        r_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
        r_client.rpush("phantomx:jobs:queue", json.dumps({
            "id": job_res["id"],
            "type": "health_check",
            "payload": job_payload
        }))
    except Exception as re:
        print(f"Failed to queue health check to Redis: {re}")
        
    return job_res

@router.get("")
async def list_accounts(current_user: dict = Depends(get_current_user)):
    """Fetch all LinkedIn accounts active in the user's workspace."""
    client = get_db_client()
    res = await client.table("linkedin_accounts").select("*").eq("workspace_id", current_user["workspace_id"]).execute()
    return res.data

@router.post("", status_code=status.HTTP_201_CREATED)
async def create_account(body: AccountCreate, current_user: dict = Depends(get_current_user)):
    """Register a new LinkedIn account with automatic session health validation queue."""
    # Enforce billing/plan quota restrictions first
    await verify_linkedin_account_quota(current_user["workspace_id"])
    
    client = get_db_client()

    
    # 1. Encrypt cookie
    li_at_encrypted = encrypt_cookie(body.li_at_raw)
    
    # 2. Insert account row
    account_res = await client.table("linkedin_accounts").insert({
        "workspace_id": current_user["workspace_id"],
        "label": body.label,
        "li_at_encrypted": li_at_encrypted,
        "status": "warming_up",
        "daily_limit": 50,
        "actions_today": 0,
        "proxy_country": body.proxy_country,
        "safety_score": 100
    }).execute()
    
    if not account_res.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to register LinkedIn account"
        )
    account = account_res.data[0]
    
    # 3. Trigger automatic health validation job
    await queue_health_check_job(current_user["workspace_id"], account["id"])
    
    return {
        "message": "Account registered, health check validation queued.",
        "account": {
            "id": account["id"],
            "label": account["label"],
            "status": account["status"],
            "daily_limit": account["daily_limit"],
            "proxy_country": account["proxy_country"]
        }
    }

@router.delete("/{account_id}")
async def delete_account(account_id: str, current_user: dict = Depends(get_current_user)):
    """Delete an account from the workspace."""
    client = get_db_client()
    
    # Verify account ownership first
    check = await client.table("linkedin_accounts").select("*").eq("id", account_id).eq("workspace_id", current_user["workspace_id"]).execute()
    if not check.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="LinkedIn account not found in your workspace"
        )
        
    await client.table("linkedin_accounts").delete().eq("id", account_id).execute()
    return {"message": "Account deleted successfully"}

@router.post("/{account_id}/health")
async def force_health_check(account_id: str, current_user: dict = Depends(get_current_user)):
    """Force an instant session status check for the LinkedIn account."""
    client = get_db_client()
    
    # Verify account ownership
    check = await client.table("linkedin_accounts").select("*").eq("id", account_id).eq("workspace_id", current_user["workspace_id"]).execute()
    if not check.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="LinkedIn account not found in your workspace"
        )
        
    job = await queue_health_check_job(current_user["workspace_id"], account_id)
    return {"message": "Health check queued", "job_id": job["id"]}

@router.get("/{account_id}/health")
async def get_account_health(account_id: str, current_user: dict = Depends(get_current_user)):
    """Retrieve verified live session, signal, and restriction safety health parameters."""
    client = get_db_client()
    
    # Verify account ownership
    check = await client.table("linkedin_accounts").select("*").eq("id", account_id).eq("workspace_id", current_user["workspace_id"]).execute()
    if not check.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="LinkedIn account not found in your workspace"
        )
    account = check.data[0]
    
    from app.services.safety_monitor import check_account_safety
    safety_data = await check_account_safety(account_id)
    
    return {
        "account_id": account_id,
        "valid": safety_data.get("valid", True),
        "signal": safety_data.get("signal", "nominal"),
        "status": safety_data.get("status", account.get("status", "warming_up")),
        "safety_score": safety_data.get("safety_score", account.get("safety_score", 100))
    }

@router.put("/{account_id}/limit")
async def update_account_limit(account_id: str, body: LimitUpdate, current_user: dict = Depends(get_current_user)):
    """Update the daily execution limit for a LinkedIn account."""
    client = get_db_client()
    
    # Verify account ownership
    check = await client.table("linkedin_accounts").select("*").eq("id", account_id).eq("workspace_id", current_user["workspace_id"]).execute()
    if not check.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="LinkedIn account not found in your workspace"
        )
        
    res = await client.table("linkedin_accounts").update({
        "daily_limit": body.daily_limit
    }).eq("id", account_id).execute()
    
    return {"message": "Daily limit updated successfully", "daily_limit": res.data[0]["daily_limit"]}
