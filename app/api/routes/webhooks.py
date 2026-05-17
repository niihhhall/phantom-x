from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from app.core.database import (
    get_lead_by_profile_url,
    create_message,
    update_lead_stage
)
from app.core.auth import get_current_user

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

class LinkedInIncomingWebhook(BaseModel):
    workspace_id: Optional[str] = Field(None, description="Workspace ID (optional if authenticated via header)")
    profile_url: str = Field(..., example="https://www.linkedin.com/in/sarah-jenkins-87/")
    content: str = Field(..., example="Hi! Yes, I would love to connect and learn more about Phantom-X.")
    account_id: Optional[str] = Field(None, description="The local LinkedIn account ID that received this message")

@router.post("/linkedin-incoming", response_model=Dict[str, Any])
async def api_linkedin_incoming_webhook(
    body: LinkedInIncomingWebhook,
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user)
):
    """
    Webhook endpoint to sync incoming LinkedIn messages (F-08).
    Automatically maps the inbound message to a CRM lead, logs it,
    and transitions the lead pipeline stage to 'replied'.
    """
    # Determine the target workspace_id
    workspace_id = None
    if current_user:
        workspace_id = current_user.get("workspace_id")
    elif body.workspace_id:
        workspace_id = body.workspace_id
        
    if not workspace_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication or workspace_id context"
        )
        
    # 1. Fetch the lead by profile_url
    lead = await get_lead_by_profile_url(workspace_id, body.profile_url)
    if not lead:
        raise HTTPException(
            status_code=status.HTTP_444_CONNECTION_CLOSED, # Premium error code for unmatched lead sync
            detail="Lead with the specified profile URL was not found in this workspace"
        )
        
    # 2. Insert inbound message record
    msg_data = {
        "lead_id": lead["id"],
        "direction": "inbound",
        "content": body.content,
        "sent_via": body.account_id or lead.get("account_id")
    }
    msg_record = await create_message(msg_data)
    
    # 3. Transition lead stage to 'replied' automatically
    updated_lead = await update_lead_stage(lead["id"], "replied")
    
    return {
        "status": "success",
        "message": "Inbound message synced successfully",
        "message_record": msg_record,
        "lead_stage": updated_lead.get("pipeline_stage")
    }
