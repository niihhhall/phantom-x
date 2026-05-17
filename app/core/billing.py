# app/core/billing.py
import logging
from typing import Dict, Any
from fastapi import HTTPException, status
from app.core.database import get_db_client

logger = logging.getLogger(__name__)

async def get_workspace_quota_limits(workspace_id: str) -> Dict[str, Any]:
    """
    Fetch active limits for a workspace. Uses the stored database function
    to gracefully handle defaults, trials, and billing cancellations.
    """
    try:
        client = get_db_client()
        # Execute the database function get_workspace_limits(workspace_id)
        res = await client.rpc("get_workspace_limits", {"p_workspace_id": workspace_id}).execute()
        if res.data:
            return res.data
    except Exception as e:
        logger.error(f"Failed to fetch workspace quotas for {workspace_id}: {e}")
        
    # Return conservative safe defaults if database check fails
    return {
        "max_linkedin_accounts": 1,
        "max_daily_actions_per_account": 50,
        "max_leads_per_month": 500,
        "allow_ai_personalization": True,
        "allow_email_enrichment": False,
        "allow_multi_account_rotation": False
    }

async def verify_linkedin_account_quota(workspace_id: str) -> None:
    """
    Verify if the workspace can add another LinkedIn account based on their plan limits.
    """
    limits = await get_workspace_quota_limits(workspace_id)
    max_allowed = limits.get("max_linkedin_accounts", 1)
    
    client = get_db_client()
    accounts_res = await client.table("linkedin_accounts").select("id", count="exact").eq("workspace_id", workspace_id).execute()
    current_count = accounts_res.count if accounts_res.count is not None else 0
    
    if current_count >= max_allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Workspace has reached its maximum limit of {max_allowed} LinkedIn account(s). Please upgrade your plan."
        )

async def verify_outreach_rotation_quota(workspace_id: str, account_ids: list) -> None:
    """
    Verify if the campaign setup attempts to rotate multiple accounts without plan permission.
    """
    if len(account_ids) > 1:
        limits = await get_workspace_quota_limits(workspace_id)
        if not limits.get("allow_multi_account_rotation", False):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Multi-account campaign rotation is restricted to Pro and Agency tiers. Please upgrade to unlock."
            )

async def verify_email_enrichment_quota(workspace_id: str) -> None:
    """
    Verify if the workspace is allowed to trigger email enrichment waterfalls (Apollo/Hunter).
    """
    limits = await get_workspace_quota_limits(workspace_id)
    if not limits.get("allow_email_enrichment", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Waterfall email enrichment is only available on paid plans. Please upgrade to unlock."
        )

async def verify_leads_quota(workspace_id: str, new_import_count: int = 0) -> None:
    """
    Verify if importing/scraping more leads exceeds the workspace's monthly limit.
    """
    limits = await get_workspace_quota_limits(workspace_id)
    max_leads = limits.get("max_leads_per_month", 500)
    
    client = get_db_client()
    leads_res = await client.table("leads").select("id", count="exact").eq("workspace_id", workspace_id).execute()
    current_leads = leads_res.count if leads_res.count is not None else 0
    
    if (current_leads + new_import_count) > max_leads:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Action would exceed your workspace monthly lead capacity of {max_leads}. Current leads: {current_leads}."
        )
