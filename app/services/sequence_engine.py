import logging
import json
import asyncio
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
from app.core.database import get_db_client, get_leads, get_campaign_by_id, upsert_lead
from app.core.queue import enqueue_job
from app.services.ai_service import score_lead_icp

logger = logging.getLogger("phantomx.sequence_engine")
logger.setLevel(logging.INFO)

async def generate_followup_message(lead: dict, campaign_context: dict, step_template: str) -> str:
    """
    Generate personalized followup message leveraging the Claude service.
    Falls back to simple template tags replacing if the Anthropic API is disabled.
    """
    first_name = (lead.get("full_name") or "").split()[0] if lead.get("full_name") else "there"
    company = lead.get("company") or "your company"
    headline = lead.get("headline") or "your work"
    
    # 1. Fallback Template-tag injection
    templated = step_template.replace("{{first_name}}", first_name)\
                             .replace("{{company}}", company)\
                             .replace("{{headline}}", headline)
                             
    # 2. Advanced Claude rewrite for humanized variety
    try:
        from app.config import settings
        if settings.ANTHROPIC_API_KEY:
            # We construct a rich context to humanize the template
            from anthropic import AsyncAnthropic
            anthropic_client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
            
            prompt = (
                f"You are a professional LinkedIn outreach copywriter.\n"
                f"Personalize the following message for {lead.get('full_name')} who works at {company} as {headline}.\n\n"
                f"Original Template:\n\"{templated}\"\n\n"
                f"Make it sound highly premium, natural, human, conversational, and non-generic. "
                f"Avoid corporate fluff. Respond ONLY with the final message body. No headers or intros."
            )
            
            res = await anthropic_client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=250,
                temperature=0.7,
                messages=[{"role": "user", "content": prompt}]
            )
            ai_text = res.content[0].text.strip()
            if ai_text:
                logger.info("Successfully humanized follow-up message via Claude 3.5 Sonnet.")
                return ai_text
    except Exception as e:
        logger.error(f"Failed using Claude for follow-up personalization: {e}")
        
    return templated

async def process_lead_sequence(lead: dict, campaign: dict) -> bool:
    """
    Inspect a lead's sequence state, verify delay rules against campaign sequence definitions,
    and trigger the next follow-up message if due.
    """
    lead_id = lead["id"]
    workspace_id = lead["workspace_id"]
    campaign_id = campaign["id"]
    
    # Exclude replied/interested stages to prevent duplicate outreach
    if lead.get("pipeline_stage") in ("replied", "interested", "booked", "closed", "not_interested"):
        logger.info(f"Lead ID {lead_id} is in final pipeline stage. Skipping sequence.")
        return False
        
    # Read campaign sequence array
    sequence_steps = campaign.get("sequence") or []
    if not sequence_steps:
        logger.info(f"Campaign {campaign_id} has no sequence steps configured.")
        return False
        
    # Parse lead sequence metadata from the notes field (stores JSON tracking details)
    seq_state = {"current_step": 0, "last_step_sent_at": None}
    try:
        if lead.get("notes") and lead["notes"].strip().startswith("{"):
            seq_state = json.loads(lead["notes"])
    except Exception:
        pass
        
    current_step_num = seq_state.get("current_step", 0)
    
    # Check if there is a next step
    next_step_idx = current_step_num
    if next_step_idx >= len(sequence_steps):
        logger.info(f"Lead ID {lead_id} has already completed all {len(sequence_steps)} sequence steps.")
        return False
        
    next_step = sequence_steps[next_step_idx]
    delay_days = next_step.get("delay_days", 1)
    template = next_step.get("template", "")
    
    # Determine base time for delay checking
    last_sent_str = seq_state.get("last_step_sent_at")
    if last_sent_str:
        base_time = datetime.fromisoformat(last_sent_str)
    else:
        # If first step, check delay since connection confirmation
        conn_at = lead.get("connected_at") or lead.get("sent_at") or lead.get("created_at")
        if isinstance(conn_at, str):
            # Parse iso format
            try:
                base_time = datetime.fromisoformat(conn_at.replace("Z", "+00:00"))
            except Exception:
                base_time = datetime.now(timezone.utc)
        elif conn_at:
            base_time = conn_at
        else:
            base_time = datetime.now(timezone.utc)
            
    now = datetime.now(timezone.utc)
    target_time = base_time + timedelta(days=delay_days)
    
    if now < target_time:
        delta = target_time - now
        logger.info(f"Lead ID {lead_id} next step is not due yet. Remaining: {delta.days}d {delta.seconds//3600}h.")
        return False
        
    # Lead is due for next outreach step!
    logger.info(f"Triggering sequence Step {next_step_idx+1} for Lead ID {lead_id}")
    
    message_text = await generate_followup_message(lead, campaign, template)
    
    # Enqueue a messaging background job
    payload = {
        "lead_id": lead_id,
        "profile_url": lead["profile_url"],
        "account_id": lead.get("account_id") or campaign.get("account_ids", [None])[0],
        "campaign_id": campaign_id,
        "workspace_id": workspace_id,
        "message": message_text
    }
    
    if not payload["account_id"]:
        logger.error(f"Cannot dispatch sequence message for Lead {lead_id}: No LinkedIn account ID mapped.")
        return False
        
    await enqueue_job("message", payload, workspace_id)
    
    # Update lead notes state tracking
    seq_state["current_step"] = next_step_idx + 1
    seq_state["last_step_sent_at"] = now.isoformat()
    
    update_data = {
        "id": lead_id,
        "workspace_id": workspace_id,
        "profile_url": lead["profile_url"],
        "message_sent": message_text,
        "notes": json.dumps(seq_state)
    }
    await upsert_lead(update_data)
    return True

async def check_and_trigger_sequences(workspace_id: str) -> dict:
    """
    Examine active campaigns, fetch eligible connected leads, and advance them through sequence stages.
    """
    logger.info(f"Running automated sequence checks for workspace: {workspace_id}")
    
    # 1. Fetch campaigns
    from app.core.database import get_campaigns
    campaigns = await get_campaigns(workspace_id)
    active_campaigns = [c for c in campaigns if c.get("status") == "active"]
    
    processed = 0
    triggered = 0
    
    for campaign in active_campaigns:
        # We process connected leads matching campaign ID
        leads = await get_leads(workspace_id, {"campaign_id": campaign["id"]})
        # Eligible stages: connected (ideal) or sent (if no template-note, we might check inbox)
        eligible_leads = [l for l in leads if l.get("pipeline_stage") in ("connected", "sent")]
        
        for lead in eligible_leads:
            try:
                started = await process_lead_sequence(lead, campaign)
                processed += 1
                if started:
                    triggered += 1
            except Exception as e:
                logger.error(f"Error executing sequence step for Lead ID {lead.get('id')}: {e}")
                
    return {
        "active_campaigns_processed": len(active_campaigns),
        "total_leads_checked": processed,
        "messages_enqueued": triggered
    }
