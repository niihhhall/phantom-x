from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from app.core.auth import get_current_user
from app.core.database import (
    get_campaigns,
    get_campaign_by_id,
    create_campaign,
    update_campaign,
    delete_campaign
)

router = APIRouter(prefix="/campaigns", tags=["campaigns"])

class CampaignCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    status: Optional[str] = "draft"
    account_ids: Optional[List[str]] = []
    sequence: Optional[List[Dict[str, Any]]] = []
    daily_limit: Optional[int] = 50
    icp_description: Optional[str] = None

class CampaignUpdate(BaseModel):
    name: Optional[str] = None
    status: Optional[str] = None
    account_ids: Optional[List[str]] = None
    sequence: Optional[List[Dict[str, Any]]] = None
    daily_limit: Optional[int] = None
    icp_description: Optional[str] = None

@router.post("", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
async def api_create_campaign(
    body: CampaignCreate,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    workspace_id = current_user["workspace_id"]
    campaign_data = {
        "workspace_id": workspace_id,
        "name": body.name,
        "status": body.status,
        "account_ids": body.account_ids,
        "sequence": body.sequence,
        "daily_limit": body.daily_limit,
        "icp_description": body.icp_description
    }
    created = await create_campaign(campaign_data)
    return created

@router.get("", response_model=List[Dict[str, Any]])
async def api_list_campaigns(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    workspace_id = current_user["workspace_id"]
    return await get_campaigns(workspace_id)

@router.get("/{campaign_id}", response_model=Dict[str, Any])
async def api_get_campaign(
    campaign_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    campaign = await get_campaign_by_id(campaign_id)
    if not campaign or campaign["workspace_id"] != current_user["workspace_id"]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found"
        )
    return campaign

@router.put("/{campaign_id}", response_model=Dict[str, Any])
async def api_update_campaign(
    campaign_id: str,
    body: CampaignUpdate,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    campaign = await get_campaign_by_id(campaign_id)
    if not campaign or campaign["workspace_id"] != current_user["workspace_id"]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found"
        )
    
    update_data = {}
    if body.name is not None:
        update_data["name"] = body.name
    if body.status is not None:
        if body.status not in ('draft', 'active', 'paused', 'completed', 'error'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid status"
            )
        update_data["status"] = body.status
    if body.account_ids is not None:
        update_data["account_ids"] = body.account_ids
    if body.sequence is not None:
        update_data["sequence"] = body.sequence
    if body.daily_limit is not None:
        update_data["daily_limit"] = body.daily_limit
    if body.icp_description is not None:
        update_data["icp_description"] = body.icp_description

    updated = await update_campaign(campaign_id, update_data)
    return updated

@router.post("/{campaign_id}/start", response_model=Dict[str, Any])
async def api_start_campaign(
    campaign_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Start the campaign: transition status to active, fetch up to 10 queued leads,
    assign round-robin accounts from the campaign's pool, and queue connection requests.
    """
    from app.core.database import get_db_client
    from app.core.queue import enqueue_job
    from app.services.ai_service import generate_connection_message
    
    # 1. Fetch and verify campaign ownership
    campaign = await get_campaign_by_id(campaign_id)
    if not campaign or campaign["workspace_id"] != current_user["workspace_id"]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found"
        )
        
    # Check rotation pool accounts
    account_ids = campaign.get("account_ids", [])
    if not account_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active LinkedIn accounts configured for this campaign rotation pool."
        )
        
    # 2. Update campaign status to active
    await update_campaign(campaign_id, {"status": "active"})
    
    # 3. Fetch up to 10 queued leads
    client = get_db_client()
    leads_res = await client.table("leads")\
        .select("*")\
        .eq("campaign_id", campaign_id)\
        .eq("pipeline_stage", "queued")\
        .limit(10)\
        .execute()
        
    leads = leads_res.data or []
    jobs_queued = 0
    
    # 4. For each lead: assign round-robin account and queue connection request
    for idx, lead in enumerate(leads):
        account_id = account_ids[idx % len(account_ids)]
        
        # Determine outreach personalized message using Claude service
        msg = await generate_connection_message(lead, campaign.get("icp_description"))
        
        payload = {
            "lead_id": lead["id"],
            "profile_url": lead["profile_url"],
            "account_id": str(account_id),
            "campaign_id": campaign_id,
            "workspace_id": current_user["workspace_id"],
            "message": msg
        }
        
        # Enqueue connect task
        await enqueue_job("connect", payload, current_user["workspace_id"])
        jobs_queued += 1
        
    return {
        "started": True,
        "jobs_queued": jobs_queued
    }

@router.post("/{campaign_id}/pause", response_model=Dict[str, Any])
async def api_pause_campaign(
    campaign_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Pause the campaign by changing its status to paused."""
    campaign = await get_campaign_by_id(campaign_id)
    if not campaign or campaign["workspace_id"] != current_user["workspace_id"]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found"
        )
        
    await update_campaign(campaign_id, {"status": "paused"})
    return {"paused": True}

@router.delete("/{campaign_id}", response_model=Dict[str, Any])
async def api_delete_campaign(
    campaign_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    campaign = await get_campaign_by_id(campaign_id)
    if not campaign or campaign["workspace_id"] != current_user["workspace_id"]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found"
        )
    
    success = await delete_campaign(campaign_id)
    return {"status": "success", "deleted": success}
