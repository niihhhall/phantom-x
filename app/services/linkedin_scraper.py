import asyncio
import logging
import random
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse, parse_qs
from app.core.database import upsert_lead
from app.workers.browser_engine import human_delay, LinkedInBrowser

logger = logging.getLogger("phantomx.scraper")
logger.setLevel(logging.INFO)

async def scroll_to_load(page):
    """Gradually scroll down the page to trigger lazy-loaded elements."""
    logger.info("Scrolling page to trigger lazy loading...")
    for i in range(4):
        scroll_height = await page.evaluate("document.body.scrollHeight")
        await page.evaluate(f"window.scrollTo(0, {scroll_height} * {i+1} / 4)")
        await asyncio.sleep(random.uniform(0.8, 1.5))

async def scrape_full_profile(browser: LinkedInBrowser, profile_url: str, campaign_id: Optional[str] = None) -> dict:
    """
    Navigate to a single profile page, scrape key properties, score fit against campaign ICP, and upsert to database.
    """
    logger.info(f"Triggering deep scrape for single profile: {profile_url}")
    profile_data = await browser.scrape_profile(profile_url)
    
    # Enrich with workspace/account metadata
    profile_data["workspace_id"] = browser.workspace_id
    profile_data["account_id"] = browser.account_id
    if campaign_id:
        profile_data["campaign_id"] = campaign_id
        
        # Calculate Claude AI ICP Fit Score
        try:
            from app.core.database import get_campaign_by_id
            from app.services.ai_service import score_lead_icp
            campaign = await get_campaign_by_id(campaign_id)
            if campaign and campaign.get("icp_description"):
                fit_score = await score_lead_icp(profile_data, campaign["icp_description"])
                profile_data["icp_score"] = fit_score
        except Exception as e:
            logger.error(f"Failed to calculate ICP fit score: {e}")
            
    saved_lead = await upsert_lead(profile_data)
    logger.info(f"Successfully scraped and stored profile: {profile_data.get('full_name')} (ID: {saved_lead.get('id')})")
    return saved_lead

async def scrape_search_results(
    browser: LinkedInBrowser, 
    search_url: str, 
    max_leads: int = 200, 
    campaign_id: Optional[str] = None
) -> List[dict]:
    """
    Navigate to a standard search or Sales Navigator search URL, handle pagination,
    extract profile URLs, run full profile scraping for each lead, and save/upsert results.
    """
    logger.info(f"Beginning search results scraping. Max Leads = {max_leads}. URL: {search_url}")
    page = browser.page
    await page.goto(search_url, wait_until="domcontentloaded")
    await human_delay(5.0, 8.0)
    
    scraped_leads = []
    page_num = 1
    
    # Detect if we are scraping standard Search vs Sales Navigator
    is_sales_nav = "linkedin.com/sales" in search_url
    logger.info(f"Target layout detected: {'Sales Navigator' if is_sales_nav else 'Standard Search'}")
    
    while len(scraped_leads) < max_leads:
        logger.info(f"Processing search results page #{page_num}...")
        await scroll_to_load(page)
        await human_delay(2.0, 4.0)
        
        lead_urls = []
        
        if is_sales_nav:
            # Sales Navigator Selectors
            selectors = [
                "li.search-results__result-item",
                "li.artdeco-list__item",
                "[data-view-name='search-results-lead-item']"
            ]
            items = []
            for selector in selectors:
                items = await page.query_selector_all(selector)
                if items:
                    logger.info(f"Found {len(items)} lead list items using Sales Nav selector '{selector}'")
                    break
                    
            for item in items:
                try:
                    # Look for profile link
                    link_el = await item.query_selector("a[data-control-name='view_profile']")
                    if not link_el:
                        # Fallback
                        link_el = await item.query_selector("a.ember-view[href*='/sales/profile/']")
                    
                    if link_el:
                        href = await link_el.get_attribute("href")
                        if href:
                            if not href.startswith("http"):
                                href = "https://www.linkedin.com" + href
                            # Clean the Sales Navigator URL or extract ID
                            lead_urls.append(href)
                except Exception as e:
                    logger.warning(f"Error parsing Sales Nav search item: {e}")
                    
        else:
            # Standard Search Selectors
            selectors = [
                "li.reusable-search__result-container",
                ".entity-result",
                ".search-results-container li"
            ]
            items = []
            for selector in selectors:
                items = await page.query_selector_all(selector)
                if items:
                    logger.info(f"Found {len(items)} lead list items using Standard Search selector '{selector}'")
                    break
                    
            for item in items:
                try:
                    # Look for anchor tag
                    link_el = await item.query_selector("a.app-aware-link")
                    if not link_el:
                        link_el = await item.query_selector("span.entity-result__title-text a")
                        
                    if link_el:
                        href = await link_el.get_attribute("href")
                        if href and "/in/" in href:
                            # Clean query parameters
                            clean_url = href.split("?")[0]
                            lead_urls.append(clean_url)
                except Exception as e:
                    logger.warning(f"Error parsing standard search item: {e}")
                    
        # Remove duplicate profiles discovered on current page
        lead_urls = list(dict.fromkeys(lead_urls))
        logger.info(f"Discovered {len(lead_urls)} unique lead URLs on current page.")
        
        if not lead_urls:
            logger.warning("No lead profile links could be extracted from this page. Ending scraper loop.")
            break
            
        # Process each URL sequentially to ensure safe delay pacing and safety metrics
        for url in lead_urls:
            if len(scraped_leads) >= max_leads:
                break
                
            try:
                # To prevent rate limits, we execute standard deep profile page scrapings
                lead = await scrape_full_profile(browser, url, campaign_id)
                scraped_leads.append(lead)
                # Random interaction delays between lead visits
                await human_delay(4.0, 9.0)
            except Exception as e:
                logger.error(f"Failed scraping profile url {url}: {e}")
                
        # Check if we should paginate to the next page
        if len(scraped_leads) >= max_leads:
            logger.info("Scraped lead target limit reached.")
            break
            
        logger.info("Looking for the pagination Next button...")
        next_button = None
        
        if is_sales_nav:
            next_button = await page.query_selector("button.search-results__pagination-next-button")
            if not next_button:
                next_button = await page.query_selector("button.artdeco-pagination__button--next")
        else:
            next_button = await page.query_selector("button.artdeco-pagination__button--next")
            
        if next_button:
            # Check if disabled
            is_disabled = await next_button.get_attribute("disabled")
            if is_disabled is not None:
                logger.info("Pagination Next button is disabled. No more results.")
                break
                
            logger.info("Clicking Next page button...")
            await next_button.click()
            page_num += 1
            await human_delay(5.0, 9.0)
        else:
            logger.info("Could not find the pagination Next button. Exiting.")
            break
            
    logger.info(f"Search results processing fully completed. Total Scraped leads: {len(scraped_leads)}")
    return scraped_leads
