import asyncio
import logging
import re
from typing import List, Dict, Any
from linkedin_api import Linkedin

logger = logging.getLogger("phantomx.voyager")

def extract_public_id(profile_url: str) -> str:
    """Extract public_id from standard LinkedIn profile URL."""
    cleaned = profile_url.rstrip("/")
    if "/in/" in cleaned:
        return cleaned.split("/in/")[-1].split("?")[0]
    return cleaned

class VoyagerClient:
    """Stealth LinkedIn Voyager API client fallback wrapper."""
    
    def __init__(self, username: str, password: str):
        self.username = username
        self.password = password
        self.api = None
        
    def _ensure_connected(self):
        if not self.api:
            logger.info("Initializing VoyagerClient authentication session...")
            self.api = Linkedin(self.username, self.password)
            
    async def search_people(self, keywords: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Search people matching keyword query on LinkedIn."""
        try:
            await asyncio.to_thread(self._ensure_connected)
            results = await asyncio.to_thread(
                self.api.search_people,
                keywords=keywords,
                limit=limit
            )
            return results or []
        except Exception as e:
            logger.error(f"VoyagerClient search_people failed: {e}", exc_info=True)
            return []
            
    async def get_profile(self, profile_url: str) -> Dict[str, Any]:
        """Fetch profile details using internal Voyager APIs."""
        logger.info(f"VoyagerClient fetching profile: {profile_url}")
        try:
            await asyncio.to_thread(self._ensure_connected)
            public_id = extract_public_id(profile_url)
            
            profile = await asyncio.to_thread(
                self.api.get_profile,
                public_id
            )
            
            # Map internal Voyager format to the unified scrape_profile schema
            first_name = profile.get("firstName", "") or ""
            last_name = profile.get("lastName", "") or ""
            full_name = f"{first_name} {last_name}".strip()
            
            # Extract current experience/company if present
            company_name = None
            experiences = profile.get("experience", [])
            if experiences and len(experiences) > 0:
                company_name = experiences[0].get("companyName")
                
            return {
                "profile_url": profile_url,
                "full_name": full_name or None,
                "headline": profile.get("headline") or None,
                "company": company_name or None,
                "location": profile.get("locationName") or None,
                "about": profile.get("summary") or None,
                "recent_posts": []
            }
        except Exception as e:
            logger.error(f"VoyagerClient get_profile failed: {e}", exc_info=True)
            return {
                "profile_url": profile_url,
                "full_name": None,
                "headline": None,
                "company": None,
                "location": None,
                "about": None,
                "recent_posts": []
            }
