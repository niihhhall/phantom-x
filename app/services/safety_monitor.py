import httpx
import logging
from typing import Dict, Any
from app.config import settings
from app.core.database import get_db_client

logger = logging.getLogger("phantomx.safety_monitor")

async def send_slack_alert(message: str, severity: str = "warning"):
    """Send alert notification block to Slack channel if webhook is configured."""
    if not settings.SLACK_WEBHOOK_URL:
        logger.info(f"Slack webhook not configured. Alert: [{severity.upper()}] {message}")
        return
        
    emoji = "⚠️" if severity == "warning" else "🚨"
    payload = {
        "text": f"{emoji} *[PHANTOM-X SAFETY ALERT]* ({severity.upper()})\n>{message}"
    }
    
    try:
        async with httpx.AsyncClient() as client:
            res = await client.post(settings.SLACK_WEBHOOK_URL, json=payload, timeout=5.0)
            if res.status_code != 200:
                logger.error(f"Slack alert failed with status {res.status_code}: {res.text}")
    except Exception as e:
        logger.error(f"Failed to post Slack webhook alert: {e}")

async def check_account_safety(account_id: str) -> dict:
    """
    Perform checks on account safety metrics, daily paces, and flags.
    If the account status is restricted or safety score drops below 50,
    it automatically transitions the account, pauses dependent campaigns, and fires alarms.
    """
    client = get_db_client()
    res = await client.table("linkedin_accounts").select("*").eq("id", account_id).execute()
    if not res.data:
        raise ValueError(f"LinkedIn account {account_id} not found.")
        
    account = res.data[0]
    status = account.get("status", "active")
    safety_score = account.get("safety_score", 100)
    actions_today = account.get("actions_today", 0)
    daily_limit = account.get("daily_limit", 50)
    
    valid = True
    signal = "nominal"
    
    # Check for restriction triggers
    if status == "restricted" or safety_score < 50:
        valid = False
        signal = "restricted"
        
        # Trigger restriction flow once detected
        if status != "restricted":
            # 1. Update account status
            await client.table("linkedin_accounts").update({
                "status": "restricted",
                "safety_score": 0
            }).eq("id", account_id).execute()
            status = "restricted"
            safety_score = 0
            
            # 2. Pause dependent campaigns
            camp_res = await client.table("campaigns").select("*").eq("workspace_id", account["workspace_id"]).execute()
            if camp_res.data:
                for camp in camp_res.data:
                    acc_list = camp.get("account_ids", [])
                    if acc_list and str(account_id) in [str(uid) for uid in acc_list]:
                        await client.table("campaigns").update({
                            "status": "paused"
                        }).eq("id", camp["id"]).execute()
                        
            # 3. Fire Slack alert
            alert_msg = (
                f"LinkedIn Account *{account.get('label', 'Unnamed')}* ({account_id}) has been flagged "
                f"as RESTRICTED. Dependent outreach campaigns have been paused to protect your other assets."
            )
            await send_slack_alert(alert_msg, severity="critical")
            
    elif actions_today >= daily_limit:
        signal = "limit_reached"
        
    return {
        "account_id": account_id,
        "valid": valid,
        "signal": signal,
        "status": status,
        "safety_score": safety_score
    }

async def daily_limit_check(account_id: str) -> bool:
    """Return True if the account has reached or exceeded its daily action limit limit."""
    client = get_db_client()
    res = await client.table("linkedin_accounts").select("actions_today, daily_limit").eq("id", account_id).execute()
    if not res.data:
        return True
        
    account = res.data[0]
    actions_today = account.get("actions_today", 0)
    daily_limit = account.get("daily_limit", 50)
    return actions_today >= daily_limit

async def increment_action_count(account_id: str):
    """Safely increment actions_today action usage counters in Supabase."""
    client = get_db_client()
    res = await client.table("linkedin_accounts").select("actions_today").eq("id", account_id).execute()
    if res.data:
        actions_today = res.data[0].get("actions_today", 0)
        await client.table("linkedin_accounts").update({
            "actions_today": actions_today + 1
        }).eq("id", account_id).execute()
