import asyncio
import logging
import random
from typing import Dict, Any, Optional
from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from app.config import settings

logger = logging.getLogger("phantomx.browser")
logger.setLevel(logging.INFO)

async def human_delay(min_sec: float = 3.0, max_sec: float = 8.0):
    """Simulate human reading or interaction delay with randomized sleep."""
    delay = random.uniform(min_sec, max_sec)
    await asyncio.sleep(delay)

class LinkedInBrowser:
    """Stealth Playwright wrapper for LinkedIn interaction via residential proxies."""
    
    def __init__(self, workspace_id: str, account_id: str, proxy_country: str = "US"):
        self.workspace_id = workspace_id
        self.account_id = account_id
        self.proxy_country = proxy_country
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None

    async def __aenter__(self):
        await self.init_browser()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def init_browser(self):
        """Initialize browser instance with proxy and anti-detection custom configurations."""
        self.playwright = await async_playwright().start()
        
        # Configure residential proxy if credentials exist
        proxy_config = None
        if settings.DECODO_USERNAME and settings.DECODO_PASSWORD:
            proxy_config = {
                "server": "http://gateway.decodo.co:8000",
                "username": settings.DECODO_USERNAME,
                "password": settings.DECODO_PASSWORD
            }
            logger.info(f"Routing browser via Decodo proxy country={self.proxy_country}")
            
        self.browser = await self.playwright.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-infobars",
                "--window-size=1280,720"
            ]
        )
        
        self.context = await self.browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            proxy=proxy_config,
            viewport={"width": 1280, "height": 720}
        )
        
        # Injects script to completely remove/override automation flags
        await self.context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            window.chrome = {
                runtime: {}
            };
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en']
            });
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });
        """)
        
        self.page = await self.context.new_page()

    async def login_via_cookie(self, li_at: str) -> bool:
        """Inject the user session li_at cookie and verify authentication."""
        logger.info("Attempting session login via cookie injection...")
        cookie = {
            "name": "li_at",
            "value": li_at,
            "domain": ".linkedin.com",
            "path": "/",
            "secure": True,
            "sameSite": "None"
        }
        await self.context.add_cookies([cookie])
        
        # Navigate to home feed
        await self.page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded")
        await human_delay(4.0, 7.0)
        
        # Verify authenticated state
        current_url = self.page.url
        if "feed" in current_url:
            logger.info("Successfully validated session via URL structure.")
            return True
            
        try:
            # Check for standard search input element
            search_box = await self.page.wait_for_selector(".global-nav__search-input", timeout=6000)
            if search_box:
                logger.info("Successfully validated session via presence of search bar.")
                return True
        except Exception:
            pass
            
        logger.warning("Failed to authenticate session using the injected cookie.")
        return False

    async def scrape_profile(self, profile_url: str) -> Dict[str, Any]:
        """Navigate to profile URL and extract key user details with fallback mechanisms."""
        logger.info(f"Scraping LinkedIn profile: {profile_url}")
        await self.page.goto(profile_url, wait_until="domcontentloaded")
        await human_delay(5.0, 9.0)
        
        profile_data = {
            "profile_url": profile_url,
            "full_name": None,
            "headline": None,
            "company": None,
            "location": None,
            "about": None,
            "recent_posts": []
        }
        
        try:
            # 1. Full name extraction
            name_el = await self.page.query_selector("h1.text-heading-xlarge")
            if name_el:
                profile_data["full_name"] = (await name_el.text_content()).strip()
            else:
                h1s = await self.page.query_selector_all("h1")
                if h1s:
                    profile_data["full_name"] = (await h1s[0].text_content()).strip()
                    
            # 2. Headline extraction
            headline_el = await self.page.query_selector(".text-body-medium")
            if headline_el:
                profile_data["headline"] = (await headline_el.text_content()).strip()
                
            # 3. Company extraction
            company_el = await self.page.query_selector("button[aria-label^='Current company']")
            if company_el:
                profile_data["company"] = (await company_el.text_content()).strip()
                
            # 4. Location extraction
            location_el = await self.page.query_selector("span.text-body-small.inline.t-black--light.break-words")
            if location_el:
                profile_data["location"] = (await location_el.text_content()).strip()
                
            # 5. About extraction
            about_section = await self.page.query_selector("section#about-section")
            if about_section:
                profile_data["about"] = (await about_section.text_content()).strip()
            else:
                # Fallback to general div matching about section text
                about_el = await self.page.query_selector(".display-flex.ph5.pv3")
                if about_el:
                    profile_data["about"] = (await about_el.text_content()).strip()
                    
        except Exception as e:
            logger.error(f"Error extracting DOM properties from profile: {e}")
            
        return profile_data

    async def send_connection_request(self, profile_url: str, message: Optional[str] = None) -> bool:
        """Find the connection button, click, inject personalized note if provided, and submit."""
        logger.info(f"Attempting to connect with prospect: {profile_url}")
        await self.page.goto(profile_url, wait_until="domcontentloaded")
        await human_delay(4.0, 7.0)
        
        try:
            # Look for the primary Connect button on profile card
            connect_btn = None
            buttons = await self.page.query_selector_all("button")
            for btn in buttons:
                text = (await btn.text_content()).strip().lower()
                if "connect" in text and "pending" not in text:
                    connect_btn = btn
                    break
                    
            if not connect_btn:
                # Check for "More" dropdown to find hidden Connect button
                more_btn = None
                for btn in buttons:
                    aria_label = await btn.get_attribute("aria-label") or ""
                    text = (await btn.text_content()).strip().lower()
                    if "more actions" in aria_label.lower() or "more" in text:
                        more_btn = btn
                        break
                if more_btn:
                    logger.info("Connect not visible. Clicking 'More' dropdown...")
                    await more_btn.click()
                    await human_delay(1.5, 3.0)
                    
                    dropdown_buttons = await self.page.query_selector_all("div.artdeco-dropdown__content button")
                    for btn in dropdown_buttons:
                        text = (await btn.text_content()).strip().lower()
                        if "connect" in text:
                            connect_btn = btn
                            break
                            
            if not connect_btn:
                logger.warning("Could not find a valid 'Connect' button on this profile.")
                return False
                
            logger.info("Found Connect button. Triggering click...")
            await connect_btn.click()
            await human_delay(2.0, 4.0)
            
            # Connection options modal
            if message:
                # Personalized note
                add_note_btn = await self.page.wait_for_selector("button[aria-label^='Add a note']", timeout=5000)
                if add_note_btn:
                    await add_note_btn.click()
                    await human_delay(1.0, 3.0)
                    
                    # Human typing simulation
                    textarea = await self.page.wait_for_selector("textarea#custom-message", timeout=5000)
                    if textarea:
                        for char in message:
                            await textarea.type(char)
                            await asyncio.sleep(random.uniform(0.05, 0.15))
                        await human_delay(2.0, 4.0)
                        
                        send_btn = await self.page.wait_for_selector("button[aria-label^='Send']", timeout=5000)
                        if send_btn:
                            await send_btn.click()
                            await human_delay(3.0, 5.0)
                            logger.info("Connection request with note sent successfully.")
                            return True
            else:
                # Send directly
                send_without_note_btn = await self.page.wait_for_selector("button[aria-label^='Send without a note']", timeout=5000)
                if send_without_note_btn:
                    await send_without_note_btn.click()
                    await human_delay(3.0, 5.0)
                    logger.info("Connection request without note sent successfully.")
                    return True
                    
        except Exception as e:
            logger.error(f"Failed to complete connection request: {e}")
            
        return False

    async def close(self):
        """Clean up and close pages, context, and Playwright instances."""
        if self.page:
            await self.page.close()
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        logger.info("Browser session closed cleanly.")
