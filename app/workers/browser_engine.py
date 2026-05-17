import asyncio
import logging
import random
from typing import Dict, Any, Optional
from rebrowser_playwright.async_api import async_playwright, Browser, BrowserContext, Page
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

    async def simulate_history(self):
        """Simulate realistic browser history before accessing target site."""
        logger.info("Simulating realistic history entries...")
        try:
            # Seed history with standard search engine queries to bypass headless profiles check
            await self.page.goto("https://www.google.com", wait_until="domcontentloaded")
            await human_delay(2.0, 4.0)
            
            # Populate history stack with realistic navigational context
            await self.page.evaluate("""
                history.pushState({}, '', '/search?q=linkedin+jobs');
                history.pushState({}, '', '/search?q=professional+networking+platform');
            """)
            await human_delay(1.5, 3.0)
        except Exception as e:
            logger.warning(f"History simulation warning: {e}")

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
            
        # Randomize screen resolution within normal desktop ranges
        resolutions = [
            {"width": 1920, "height": 1080},
            {"width": 1440, "height": 900},
            {"width": 1536, "height": 864},
            {"width": 1366, "height": 768},
            {"width": 1280, "height": 800}
        ]
        chosen_res = random.choice(resolutions)
        width = chosen_res["width"]
        height = chosen_res["height"]
        logger.info(f"Stealth resolution randomized to: {width}x{height}")
            
        self.browser = await self.playwright.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-infobars",
                f"--window-size={width},{height}"
            ]
        )
        
        self.context = await self.browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            proxy=proxy_config,
            viewport={"width": width, "height": height}
        )
        
        # Injects script to randomize canvas fingerprint and spoof WebGL renderer (anti-detection stealth layer)
        await self.context.add_init_script("""
            // Override chrome runtime object
            window.chrome = {
                runtime: {}
            };
            
            // Languages spoof
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en']
            });
            
            // Plugins list spoof
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });
            
            // WebGL Renderer Spoofing
            const getParameter = WebGLRenderingContext.prototype.getParameter;
            WebGLRenderingContext.prototype.getParameter = function(parameter) {
                // UNMASKED_VENDOR_WEBGL = 37445
                if (parameter === 37445) {
                    return 'Google Inc. (Intel)';
                }
                // UNMASKED_RENDERER_WEBGL = 37446
                if (parameter === 37446) {
                    const renderers = [
                        'ANGLE (Intel, Intel(R) UHD Graphics (0x9BC8) Direct3D11 vs_5_0 ps_5_0)',
                        'Intel(R) Iris(R) Xe Graphics Direct3D11 vs_5_0 ps_5_0',
                        'NVIDIA GeForce RTX 3060/PCIe/SSE2'
                    ];
                    return renderers[Math.floor(Math.random() * renderers.length)];
                }
                return getParameter.apply(this, arguments);
            };

            // Canvas Fingerprint Randomization (add subtle noise to canvas calls)
            const toDataURL = HTMLCanvasElement.prototype.toDataURL;
            HTMLCanvasElement.prototype.toDataURL = function() {
                const ctx = this.getContext('2d');
                if (ctx) {
                    // Inject imperceptible single-pixel canvas noise
                    const oldStyle = ctx.fillStyle;
                    ctx.fillStyle = 'rgba(0,0,0,0.01)';
                    ctx.fillRect(0, 0, 1, 1);
                    ctx.fillStyle = oldStyle;
                }
                return toDataURL.apply(this, arguments);
            };
        """)
        
        self.page = await self.context.new_page()
        await self.simulate_history()


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
            
        # Fallback to VoyagerClient if DOM scraping is incomplete
        if not profile_data.get("full_name") or not profile_data.get("headline"):
            logger.info("DOM scraping yielded incomplete profile data. Querying Voyager Client fallback...")
            if settings.LINKEDIN_EMAIL and settings.LINKEDIN_PASSWORD:
                try:
                    from app.services.voyager_client import VoyagerClient
                    voyager = VoyagerClient(settings.LINKEDIN_EMAIL, settings.LINKEDIN_PASSWORD)
                    voyager_data = await voyager.get_profile(profile_url)
                    if voyager_data and voyager_data.get("full_name"):
                        logger.info("Successfully populated profile fields via Voyager fallback client!")
                        profile_data.update(voyager_data)
                except Exception as ve:
                    logger.error(f"Voyager fallback scraping failed: {ve}")
                    
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

    async def send_direct_message(self, profile_url: str, message: str) -> bool:
        """Find the message button, click to open chat window, type message, and send."""
        logger.info(f"Attempting to send direct message to: {profile_url}")
        await self.page.goto(profile_url, wait_until="domcontentloaded")
        await human_delay(4.0, 7.0)
        
        try:
            # Look for the primary "Message" button on the profile page
            message_btn = None
            buttons = await self.page.query_selector_all("button")
            for btn in buttons:
                text = (await btn.text_content()).strip().lower()
                if text == "message":
                    message_btn = btn
                    break
                    
            if not message_btn:
                # Check for "More" dropdown if Message button is hidden
                more_btn = None
                for btn in buttons:
                    aria_label = await btn.get_attribute("aria-label") or ""
                    text = (await btn.text_content()).strip().lower()
                    if "more actions" in aria_label.lower() or "more" in text:
                        more_btn = btn
                        break
                if more_btn:
                    logger.info("Message button not visible. Clicking 'More' dropdown...")
                    await more_btn.click()
                    await human_delay(1.5, 3.0)
                    
                    dropdown_buttons = await self.page.query_selector_all("div.artdeco-dropdown__content button")
                    for btn in dropdown_buttons:
                        text = (await btn.text_content()).strip().lower()
                        if text == "message":
                            message_btn = btn
                            break
                            
            if not message_btn:
                logger.warning("Could not find a valid 'Message' button on this profile.")
                return False
                
            logger.info("Found Message button. Clicking to open message panel...")
            await message_btn.click()
            await human_delay(3.0, 5.0)
            
            # Find the active message box textbox (e.g. contenteditable="true" or role="textbox")
            textbox = await self.page.wait_for_selector(
                "div.msg-form__contenteditable[contenteditable='true'], textarea.msg-form__textarea",
                timeout=8000
            )
            if not textbox:
                logger.error("Could not locate message input textbox.")
                return False
                
            logger.info("Typing direct message...")
            await textbox.click()
            await human_delay(1.0, 2.0)
            
            # Simulate human typing
            for char in message:
                await textbox.type(char)
                await asyncio.sleep(random.uniform(0.02, 0.08))
                
            await human_delay(2.0, 4.0)
            
            # Click the Send button
            send_btn = await self.page.wait_for_selector("button.msg-form__send-button", timeout=5000)
            if send_btn:
                is_disabled = await send_btn.get_attribute("disabled")
                if is_disabled is not None:
                    logger.warning("Send button is disabled, cannot send message.")
                    return False
                    
                await send_btn.click()
                await human_delay(3.0, 5.0)
                logger.info("Direct message sent successfully.")
                return True
                
        except Exception as e:
            logger.error(f"Failed to send direct message: {e}")
            
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
