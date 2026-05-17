import datetime
from typing import List, Dict, Any, Optional
from supabase import AsyncClient
from app.config import settings

_db_client = None

def get_db_client():
    """Lazily initialize the Supabase AsyncClient to allow app startup with placeholder keys."""
    global _db_client
    if _db_client is None:
        # Use SUPABASE_SERVICE_KEY to bypass Row-Level Security (RLS) in background workers
        _db_client = AsyncClient(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)
    return _db_client

async def get_leads(workspace_id: str, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """Fetch leads in a workspace, optionally applying key-value filters."""
    client = get_db_client()
    query = client.table("leads").select("*").eq("workspace_id", workspace_id)
    
    if filters:
        for key, val in filters.items():
            if val is not None:
                query = query.eq(key, val)
                
    res = await query.execute()
    return res.data

async def get_campaigns(workspace_id: str) -> List[Dict[str, Any]]:
    """Fetch all campaigns in a workspace."""
    client = get_db_client()
    res = await client.table("campaigns").select("*").eq("workspace_id", workspace_id).execute()
    return res.data

async def get_campaign_by_id(campaign_id: str) -> Optional[Dict[str, Any]]:
    """Fetch a campaign by its ID."""
    client = get_db_client()
    res = await client.table("campaigns").select("*").eq("id", campaign_id).execute()
    return res.data[0] if res.data else None

async def create_campaign(campaign_data: Dict[str, Any]) -> Dict[str, Any]:
    """Create a new campaign."""
    client = get_db_client()
    res = await client.table("campaigns").insert(campaign_data).execute()
    return res.data[0] if res.data else {}

async def update_campaign(campaign_id: str, campaign_data: Dict[str, Any]) -> Dict[str, Any]:
    """Update an existing campaign."""
    client = get_db_client()
    res = await client.table("campaigns").update(campaign_data).eq("id", campaign_id).execute()
    return res.data[0] if res.data else {}

async def delete_campaign(campaign_id: str) -> bool:
    """Delete a campaign by ID."""
    client = get_db_client()
    res = await client.table("campaigns").delete().eq("id", campaign_id).execute()
    return len(res.data) > 0

async def upsert_lead(lead_data: Dict[str, Any]) -> Dict[str, Any]:
    """Upsert a lead into the leads table. Matches on the unique constraint (workspace_id, profile_url)."""
    client = get_db_client()
    res = await client.table("leads").upsert(lead_data).execute()
    return res.data[0] if res.data else {}

async def update_lead_stage(lead_id: str, stage: str) -> Dict[str, Any]:
    """Update the pipeline stage of a lead, setting connected_at or replied_at timestamps accordingly."""
    client = get_db_client()
    update_data = {"pipeline_stage": stage}
    
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    if stage == "connected":
        update_data["connected_at"] = now
    elif stage == "replied":
        update_data["replied_at"] = now
    elif stage == "sent":
        update_data["sent_at"] = now
        
    res = await client.table("leads").update(update_data).eq("id", lead_id).execute()
    lead = res.data[0] if res.data else {}
    
    # Trigger event notification webhooks (Priority 4)
    if lead:
        workspace_id = lead.get("workspace_id")
        if stage == "connected":
            try:
                from app.services.webhook_service import fire_webhook
                await fire_webhook("lead.connected", lead, workspace_id)
            except Exception:
                pass
        elif stage == "replied":
            try:
                from app.services.webhook_service import fire_webhook
                await fire_webhook("lead.replied", lead, workspace_id)
            except Exception:
                pass
                
    return lead

async def get_lead_by_id(lead_id: str) -> Optional[Dict[str, Any]]:
    """Fetch a single lead by its ID."""
    client = get_db_client()
    res = await client.table("leads").select("*").eq("id", lead_id).execute()
    return res.data[0] if res.data else None

async def get_lead_by_profile_url(workspace_id: str, profile_url: str) -> Optional[Dict[str, Any]]:
    """Fetch a single lead by profile URL within a workspace."""
    client = get_db_client()
    res = await client.table("leads").select("*").eq("workspace_id", workspace_id).eq("profile_url", profile_url).execute()
    return res.data[0] if res.data else None

async def delete_lead(lead_id: str) -> bool:
    """Delete a lead by its ID."""
    client = get_db_client()
    res = await client.table("leads").delete().eq("id", lead_id).execute()
    return len(res.data) > 0

async def create_job(job_data: Dict[str, Any]) -> Dict[str, Any]:
    """Create a new job in the jobs table."""
    client = get_db_client()
    res = await client.table("jobs").insert(job_data).execute()
    return res.data[0] if res.data else {}

async def update_job_status(job_id: str, status: str, result: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Update job status and results, setting completed_at timestamp if final."""
    client = get_db_client()
    update_data = {"status": status}
    if result is not None:
        update_data["result"] = result
        
    if status in ("done", "failed"):
        update_data["completed_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        
    res = await client.table("jobs").update(update_data).eq("id", job_id).execute()
    return res.data[0] if res.data else {}

async def get_messages_for_lead(lead_id: str) -> List[Dict[str, Any]]:
    """Fetch chat history for a given lead."""
    client = get_db_client()
    res = await client.table("messages").select("*").eq("lead_id", lead_id).order("created_at").execute()
    return res.data

async def create_message(message_data: Dict[str, Any]) -> Dict[str, Any]:
    """Insert a new message record."""
    client = get_db_client()
    res = await client.table("messages").insert(message_data).execute()
    return res.data[0] if res.data else {}

async def get_job_by_id(job_id: str) -> Optional[Dict[str, Any]]:
    """Fetch a job record by its ID."""
    client = get_db_client()
    res = await client.table("jobs").select("*").eq("id", job_id).execute()
    return res.data[0] if res.data else None

async def get_analytics_summary(workspace_id: str) -> Dict[str, Any]:
    """Calculate aggregated pipeline, campaign, and safety score metrics for the workspace CRM (F-14)."""
    client = get_db_client()
    
    # 1. Fetch campaigns
    c_res = await client.table("campaigns").select("status, stats").eq("workspace_id", workspace_id).execute()
    campaigns = c_res.data or []
    
    total_campaigns = len(campaigns)
    active_campaigns = sum(1 for c in campaigns if c.get("status") == "active")
    paused_campaigns = sum(1 for c in campaigns if c.get("status") == "paused")
    
    sent_total = sum(int(c.get("stats", {}).get("sent", 0) or 0) for c in campaigns if c.get("stats"))
    connected_total = sum(int(c.get("stats", {}).get("connected", 0) or 0) for c in campaigns if c.get("stats"))
    replied_total = sum(int(c.get("stats", {}).get("replied", 0) or 0) for c in campaigns if c.get("stats"))
    meetings_total = sum(int(c.get("stats", {}).get("meetings", 0) or 0) for c in campaigns if c.get("stats"))
    
    # 2. Fetch leads pipeline stage and average ICP score
    l_res = await client.table("leads").select("id, pipeline_stage, icp_score").eq("workspace_id", workspace_id).execute()
    leads = l_res.data or []
    
    pipeline_stages = {
        "queued": 0, "sent": 0, "connected": 0, "replied": 0,
        "interested": 0, "booked": 0, "closed": 0, "not_interested": 0
    }
    icp_scores = []
    lead_ids = set()
    for l in leads:
        stage = l.get("pipeline_stage") or "queued"
        if stage in pipeline_stages:
            pipeline_stages[stage] += 1
        score = l.get("icp_score")
        if score is not None:
            icp_scores.append(score)
        lead_ids.add(l.get("id"))
            
    avg_icp_score = int(sum(icp_scores) / len(icp_scores)) if icp_scores else 0
    
    # 3. Fetch safety scores
    a_res = await client.table("linkedin_accounts").select("safety_score").eq("workspace_id", workspace_id).execute()
    accounts = a_res.data or []
    safety_scores = [a.get("safety_score", 100) for a in accounts if a.get("safety_score") is not None]
    avg_safety_score = int(sum(safety_scores) / len(safety_scores)) if safety_scores else 100
    
    # 4. Outbound messages count
    total_messages_sent = 0
    if lead_ids:
        m_res = await client.table("messages").select("lead_id").eq("direction", "outbound").execute()
        total_messages_sent = sum(1 for m in m_res.data or [] if m.get("lead_id") in lead_ids)
            
    return {
        "campaigns": {
            "total": total_campaigns,
            "active": active_campaigns,
            "paused": paused_campaigns
        },
        "outreach": {
            "sent": sent_total,
            "connected": connected_total,
            "replied": replied_total,
            "meetings": meetings_total
        },
        "crm": {
            "pipeline_stages": pipeline_stages,
            "avg_icp_score": avg_icp_score,
            "total_leads": len(leads)
        },
        "system": {
            "avg_safety_score": avg_safety_score,
            "rotation_pool_size": len(accounts),
            "total_messages_sent": total_messages_sent
        }
    }
