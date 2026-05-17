from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from app.core.auth import get_current_user
from app.core.database import create_job, get_job_by_id

router = APIRouter(prefix="/scrape", tags=["scrape"])

class ScrapeTriggerRequest(BaseModel):
    profile_url: Optional[str] = Field(None, example="https://www.linkedin.com/in/william-gates-98b/")
    sales_navigator_url: Optional[str] = Field(None, example="https://www.linkedin.com/sales/search/people?query=...")
    campaign_id: Optional[str] = Field(None, description="Associate the scraped lead(s) with this campaign")
    account_id: Optional[str] = Field(None, description="LinkedIn account ID to run the scraping session")

@router.post("/trigger", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
async def api_trigger_scrape(
    body: ScrapeTriggerRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Trigger manual LinkedIn scraper or enrichment flow (F-01, F-06).
    Enqueues a background scraper job in the workspace queue.
    """
    if not body.profile_url and not body.sales_navigator_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either profile_url or sales_navigator_url must be provided"
        )
        
    job_payload = {
        "profile_url": body.profile_url,
        "sales_navigator_url": body.sales_navigator_url,
        "campaign_id": body.campaign_id,
        "account_id": body.account_id
    }
    
    job_data = {
        "workspace_id": current_user["workspace_id"],
        "type": "scrape",
        "status": "queued",
        "payload": job_payload,
        "retries": 0
    }
    
    job = await create_job(job_data)
    return {
        "status": "success",
        "job": job
    }

@router.get("/jobs/{job_id}", response_model=Dict[str, Any])
async def api_get_scrape_job(
    job_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Query current status and execution log of the scraper worker (F-06).
    """
    job = await get_job_by_id(job_id)
    if not job or job["workspace_id"] != current_user["workspace_id"]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
    return job
