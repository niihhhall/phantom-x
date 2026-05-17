import logging
import httpx
from typing import Dict, Any, Optional
from app.config import settings
from app.core.database import get_db_client, get_lead_by_id, get_leads, upsert_lead

logger = logging.getLogger("phantomx.enrichment")
logger.setLevel(logging.INFO)

def clean_company_domain(company_name: str) -> str:
    """Clean company name to predict a likely website domain name."""
    if not company_name:
        return "company.com"
    clean = company_name.lower().strip()
    # Remove common corporate suffixes
    suffixes = [" llc", " inc.", " inc", " corp.", " corp", " ltd.", " ltd", " co.", " co", " group"]
    for suffix in suffixes:
        if clean.endswith(suffix):
            clean = clean[:-len(suffix)].strip()
    # Clean characters and remove spaces
    clean = "".join(c for c in clean if c.isalnum() or c in ["-", "_"])
    return f"{clean}.com" if clean else "company.com"

async def query_apollo(full_name: str, first_name: str, last_name: str, company: str) -> Optional[Dict[str, str]]:
    """Query Apollo API match endpoint to locate a verified email."""
    if not settings.APOLLO_API_KEY:
        logger.info("Apollo API key is missing. Skipping Apollo waterfall stage.")
        return None
        
    url = "https://api.apollo.io/v1/people/match"
    payload = {
        "api_key": settings.APOLLO_API_KEY,
        "first_name": first_name,
        "last_name": last_name,
        "organization_name": company,
        "name": full_name
    }
    
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            res = await client.post(url, json=payload)
            if res.status_code == 200:
                data = res.json()
                person = data.get("person", {})
                email = person.get("email")
                if email:
                    logger.info(f"Email located via Apollo API match: {email}")
                    # If verified flag exists in contact info
                    is_verified = person.get("email_status") == "verified"
                    return {
                        "email": email,
                        "confidence": "verified" if is_verified else "likely",
                        "source": "apollo"
                    }
    except Exception as e:
        logger.error(f"Error querying Apollo API match: {e}")
    return None

async def query_hunter(first_name: str, last_name: str, company: str) -> Optional[Dict[str, str]]:
    """Query Hunter.io Email Finder API endpoint."""
    if not settings.HUNTER_API_KEY:
        logger.info("Hunter.io API key is missing. Skipping Hunter waterfall stage.")
        return None
        
    domain = clean_company_domain(company)
    url = "https://api.hunter.io/v2/email-finder"
    params = {
        "api_key": settings.HUNTER_API_KEY,
        "first_name": first_name,
        "last_name": last_name,
        "domain": domain
    }
    
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            res = await client.get(url, params=params)
            if res.status_code == 200:
                data = res.json().get("data", {})
                email = data.get("email")
                if email:
                    logger.info(f"Email located via Hunter.io API: {email}")
                    score = data.get("score", 0)
                    confidence = "verified" if score >= 80 else ("likely" if score >= 50 else "guessed")
                    return {
                        "email": email,
                        "confidence": confidence,
                        "source": "hunter"
                    }
    except Exception as e:
        logger.error(f"Error querying Hunter.io API: {e}")
    return None

async def enrich_lead_email(lead: dict) -> dict:
    """
    Waterfall Enrichment Logic (F-07):
    Stage 1: Apollo.io API Match lookup
    Stage 2: Hunter.io API Email Finder lookup
    Stage 3: Local pattern guessing fallback based on names & domains
    Returns lead dict updated with email metadata.
    """
    full_name = lead.get("full_name") or ""
    company = lead.get("company") or ""
    
    # Split name safely
    parts = full_name.split(maxsplit=1)
    first_name = parts[0] if parts else ""
    last_name = parts[1] if len(parts) > 1 else ""
    
    if not first_name:
        logger.warning(f"Lead ID {lead.get('id')} has no valid name fields for enrichment. Skipping.")
        return lead

    # 1. Apollo API Match
    res_apollo = await query_apollo(full_name, first_name, last_name, company)
    if res_apollo:
        lead.update(res_apollo)
        return lead
        
    # 2. Hunter.io API Finder
    res_hunter = await query_hunter(first_name, last_name, company)
    if res_hunter:
        lead.update(res_hunter)
        return lead
        
    # 3. Pattern Guessing Fallback
    domain = clean_company_domain(company)
    fn_clean = first_name.lower().strip()
    ln_clean = last_name.lower().strip()
    
    guessed_email = f"{fn_clean}.{ln_clean}@{domain}" if ln_clean else f"{fn_clean}@{domain}"
    logger.info(f"Waterfall exhausted. Applying local pattern guessed email: {guessed_email}")
    
    lead.update({
        "email": guessed_email,
        "confidence": "guessed",
        "source": "pattern_guess"
    })
    return lead

async def enrich_campaign_leads(campaign_id: str, workspace_id: str) -> dict:
    """Fetch all leads associated with a campaign and execute concurrent enrichment waterfall."""
    logger.info(f"Triggering email enrichment waterfall for campaign: {campaign_id}")
    leads = await get_leads(workspace_id, {"campaign_id": campaign_id})
    if not leads:
        return {"processed": 0, "enriched": 0}
        
    enriched_count = 0
    for lead in leads:
        # Skip already verified emails to conserve API usage
        if lead.get("email") and lead.get("email_confidence") == "verified":
            continue
            
        try:
            enriched_lead = await enrich_lead_email(lead)
            
            # Map enrichment parameters to leads table update structure
            update_data = {
                "id": lead["id"],
                "workspace_id": workspace_id,
                "profile_url": lead["profile_url"],
                "email": enriched_lead.get("email"),
                "email_confidence": enriched_lead.get("confidence")
            }
            await upsert_lead(update_data)
            enriched_count += 1
        except Exception as e:
            logger.error(f"Failed enriching lead ID {lead.get('id')}: {e}")
            
    return {"processed": len(leads), "enriched": enriched_count}
