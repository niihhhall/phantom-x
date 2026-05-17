import logging
import httpx
from typing import Dict, Any, List
from app.core.database import get_db_client

logger = logging.getLogger("phantomx.webhooks")
logger.setLevel(logging.INFO)

async def fire_webhook(event: str, payload: dict, workspace_id: str):
    """
    Find all registered webhooks for the workspace that are subscribed to the triggered event type,
    and post the payload event asynchronously.
    """
    logger.info(f"Triggering webhook event '{event}' in workspace: {workspace_id}")
    
    client = get_db_client()
    try:
        # Query webhooks for this workspace
        res = await client.table("webhooks")\
            .select("*")\
            .eq("workspace_id", workspace_id)\
            .execute()
            
        webhooks = res.data or []
    except Exception as e:
        logger.error(f"Failed to query registered webhooks: {e}")
        return
        
    # Filter webhooks that contain this event inside their events text array
    subscribed_webhooks = []
    for wh in webhooks:
        events = wh.get("events") or []
        if event in events:
            subscribed_webhooks.append(wh)
            
    if not subscribed_webhooks:
        logger.info(f"No webhooks registered for event '{event}' in this workspace.")
        return
        
    # Construct complete event body
    event_body = {
        "event": event,
        "workspace_id": workspace_id,
        "timestamp": datetime_now_iso(),
        "data": payload
    }
    
    async with httpx.AsyncClient(timeout=8.0) as http_client:
        for wh in subscribed_webhooks:
            url = wh.get("url")
            logger.info(f"Posting event '{event}' to webhook endpoint: {url}")
            try:
                post_res = await http_client.post(url, json=event_body)
                logger.info(f"Webhook response status: {post_res.status_code}")
            except Exception as ex:
                logger.error(f"Failed to POST webhook payload to {url}: {ex}")

def datetime_now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()
