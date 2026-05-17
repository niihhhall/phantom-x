from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field
from app.core.auth import get_current_user
from app.core.database import (
    get_leads,
    get_lead_by_id,
    update_lead_stage,
    delete_lead
)

router = APIRouter(prefix="/leads", tags=["leads"])

class StageUpdate(BaseModel):
    stage: str = Field(..., description="Target pipeline stage")

@router.get("", response_model=List[Dict[str, Any]])
async def api_list_leads(
    campaign_id: Optional[str] = Query(None, description="Filter by Campaign ID"),
    stage: Optional[str] = Query(None, description="Filter by pipeline stage"),
    search: Optional[str] = Query(None, description="Search term in name, company, or headline"),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    workspace_id = current_user["workspace_id"]
    
    # Extract basic filters
    filters = {}
    if campaign_id:
        filters["campaign_id"] = campaign_id
    if stage:
        filters["pipeline_stage"] = stage
        
    leads = await get_leads(workspace_id, filters)
    
    # Apply manual keyword search filter if provided (safe local filtering for high-agency CRM search)
    if search:
        search_lower = search.lower()
        filtered = []
        for lead in leads:
            name = (lead.get("full_name") or "").lower()
            company = (lead.get("company") or "").lower()
            headline = (lead.get("headline") or "").lower()
            if search_lower in name or search_lower in company or search_lower in headline:
                filtered.append(lead)
        return filtered
        
    return leads

@router.get("/{lead_id}", response_model=Dict[str, Any])
async def api_get_lead(
    lead_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    lead = await get_lead_by_id(lead_id)
    if not lead or lead["workspace_id"] != current_user["workspace_id"]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lead not found"
        )
    return lead

@router.put("/{lead_id}/stage", response_model=Dict[str, Any])
async def api_update_lead_stage(
    lead_id: str,
    body: StageUpdate,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    lead = await get_lead_by_id(lead_id)
    if not lead or lead["workspace_id"] != current_user["workspace_id"]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lead not found"
        )
        
    valid_stages = ('queued', 'sent', 'connected', 'replied', 'interested', 'booked', 'closed', 'not_interested')
    if body.stage not in valid_stages:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid stage. Must be one of {valid_stages}"
        )
        
    updated = await update_lead_stage(lead_id, body.stage)
    return updated

@router.delete("/{lead_id}", response_model=Dict[str, Any])
async def api_delete_lead(
    lead_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    lead = await get_lead_by_id(lead_id)
    if not lead or lead["workspace_id"] != current_user["workspace_id"]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lead not found"
        )
        
    success = await delete_lead(lead_id)
    return {"status": "success", "deleted": success}
