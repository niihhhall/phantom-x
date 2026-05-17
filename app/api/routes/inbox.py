from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from app.core.auth import get_current_user
from app.core.database import (
    get_lead_by_id,
    get_messages_for_lead,
    create_message,
    create_job
)

router = APIRouter(prefix="/inbox", tags=["inbox"])

class SendMessageRequest(BaseModel):
    content: str = Field(..., min_length=1, description="Text content of the message to send")

@router.get("/{lead_id}", response_model=List[Dict[str, Any]])
async def api_get_messages(
    lead_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Fetch all chat messages exchanged with the specified lead (F-08).
    """
    lead = await get_lead_by_id(lead_id)
    if not lead or lead["workspace_id"] != current_user["workspace_id"]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lead not found"
        )
        
    return await get_messages_for_lead(lead_id)

@router.post("/{lead_id}/send", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
async def api_send_message(
    lead_id: str,
    body: SendMessageRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Send a direct message to the lead (F-08).
    Inserts a local message log and enqueues a background delivery job.
    """
    lead = await get_lead_by_id(lead_id)
    if not lead or lead["workspace_id"] != current_user["workspace_id"]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lead not found"
        )
        
    # Check if a LinkedIn account is linked to the lead
    account_id = lead.get("account_id")
    if not account_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No LinkedIn account has been associated with this lead yet"
        )
        
    # 1. Insert outbound message log locally
    msg_data = {
        "lead_id": lead_id,
        "direction": "outbound",
        "content": body.content,
        "sent_via": account_id
    }
    msg_record = await create_message(msg_data)
    
    # 2. Enqueue background delivery job
    job_payload = {
        "lead_id": lead_id,
        "message_id": msg_record.get("id"),
        "account_id": account_id,
        "content": body.content,
        "profile_url": lead.get("profile_url")
    }
    
    job_data = {
        "workspace_id": current_user["workspace_id"],
        "type": "message",
        "status": "queued",
        "payload": job_payload,
        "retries": 0
    }
    job_record = await create_job(job_data)
    
    return {
        "status": "success",
        "message": msg_record,
        "job": job_record
    }
