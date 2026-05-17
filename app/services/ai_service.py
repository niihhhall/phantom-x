import json
import logging
from typing import Dict, Any, Optional
from anthropic import AsyncAnthropic
from app.config import settings

logger = logging.getLogger("phantomx.ai_service")

# Initialize AsyncAnthropic client safely
client = None
if settings.ANTHROPIC_API_KEY:
    try:
        client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    except Exception as e:
        logger.error(f"Failed to initialize Anthropic client: {e}")

MODEL_NAME = "claude-haiku-4-5-20251001"

def _get_first_name(profile_data: dict) -> str:
    full_name = profile_data.get("full_name", "")
    if not full_name:
        return "there"
    return full_name.split()[0]

def _get_company(profile_data: dict) -> str:
    return profile_data.get("company", "your firm")

def _get_headline(profile_data: dict) -> str:
    return profile_data.get("headline", "your field")

async def generate_connection_message(profile_data: dict, campaign_brief: str = None) -> str:
    """
    Generate a personalized connection message using Claude Haiku.
    Falls back to a standard dynamic template on API failures or when ANTHROPIC_API_KEY is not configured.
    """
    first_name = _get_first_name(profile_data)
    company = _get_company(profile_data)
    headline = _get_headline(profile_data)
    
    fallback_message = f"Hi {first_name}, I saw your profile and was impressed by your work at {company} as {headline}. Let's connect!"
    
    if not client:
        return fallback_message
        
    try:
        prompt = (
            f"You are a professional outreach strategist. Write a highly personalized, short LinkedIn connection request "
            f"(under 300 characters, no hashtags, no buzzwords) to the following prospect.\n\n"
            f"Prospect Profile Data:\n{json.dumps(profile_data, indent=2)}\n"
            f"Campaign Context / Brief: {campaign_brief or 'General B2B networking'}\n\n"
            f"Strict Requirement: Output ONLY the final outreach message itself, without any introductory or concluding text."
        )
        
        response = await client.messages.create(
            model=MODEL_NAME,
            max_tokens=150,
            temperature=0.7,
            messages=[{"role": "user", "content": prompt}]
        )
        message_content = response.content[0].text.strip() if response.content else ""
        return message_content if message_content else fallback_message
    except Exception as err:
        logger.error(f"Claude API failed in generate_connection_message: {err}")
        return fallback_message

async def score_lead_icp(profile_data: dict, icp_description: str) -> int:
    """
    Evaluate the fit score (0-100) of a lead against a target Ideal Customer Profile (ICP) description.
    Falls back to robust local keyword mapping if Claude API fails or is unconfigured.
    """
    headline = _get_headline(profile_data).lower()
    about = profile_data.get("about", "").lower()
    company = _get_company(profile_data).lower()
    
    # Fast keyword-based fallback calculation
    score = 50
    if icp_description:
        icp_words = [w.lower().strip() for w in icp_description.replace(",", " ").split() if len(w) > 3]
        matches = 0
        for word in icp_words:
            if word in headline or word in about or word in company:
                matches += 1
        score = min(50 + (matches * 15), 98)
        
    if not client:
        return score
        
    try:
        prompt = (
            f"You are an ICP (Ideal Customer Profile) Fit Analyzer.\n"
            f"Target ICP Criteria:\n{icp_description}\n\n"
            f"Prospect Profile Data:\n{json.dumps(profile_data, indent=2)}\n\n"
            f"Rate the prospect on a scale of 0 to 100 on how closely they match the Target ICP. "
            f"Provide ONLY a single JSON response containing the fit score. Do not explain your reasoning.\n"
            f"Output JSON Format:\n{{\"score\": <integer>}}"
        )
        
        response = await client.messages.create(
            model=MODEL_NAME,
            max_tokens=50,
            temperature=0.2,
            messages=[{"role": "user", "content": prompt}]
        )
        res_text = response.content[0].text.strip() if response.content else ""
        
        # Parse output safely
        if "{" in res_text and "}" in res_text:
            cleaned = res_text[res_text.find("{"):res_text.find("}")+1]
            data = json.loads(cleaned)
            parsed_score = data.get("score", score)
            return max(0, min(100, int(parsed_score)))
        return score
    except Exception as err:
        logger.error(f"Claude API failed in score_lead_icp: {err}")
        return score

async def generate_followup_message(profile_data: dict, step: int) -> str:
    """
    Generate a personalized LinkedIn follow-up message using Claude Haiku based on sequence step.
    Falls back to a standard dynamic template if the API call is unavailable or fails.
    """
    first_name = _get_first_name(profile_data)
    company = _get_company(profile_data)
    
    if step == 1:
        fallback_message = f"Hi {first_name}, thanks for connecting! Curious if you're experiencing any resource bottlenecks at {company} currently?"
    else:
        fallback_message = f"Hi {first_name}, just checking in to see if you had a moment to review my previous message? Let me know your thoughts."
        
    if not client:
        return fallback_message
        
    try:
        prompt = (
            f"You are an outreach copywriter. Write a personalized LinkedIn follow-up message (under 400 characters) "
            f"to the following prospect for Sequence Step {step}.\n\n"
            f"Prospect Profile Data:\n{json.dumps(profile_data, indent=2)}\n\n"
            f"Strict Requirement: Output ONLY the follow-up message itself, no intro, no conversational filler."
        )
        
        response = await client.messages.create(
            model=MODEL_NAME,
            max_tokens=200,
            temperature=0.7,
            messages=[{"role": "user", "content": prompt}]
        )
        message_content = response.content[0].text.strip() if response.content else ""
        return message_content if message_content else fallback_message
    except Exception as err:
        logger.error(f"Claude API failed in generate_followup_message: {err}")
        return fallback_message
