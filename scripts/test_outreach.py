import sys
import asyncio
from pathlib import Path

# Add root folder to python path
sys.path.append(str(Path(__file__).parent.parent.resolve()))

from app.workers.browser_engine import LinkedInBrowser

async def main():
    print("=========================================================")
    print("      PHANTOM-X HEADLESS OUTREACH TEST                  ")
    print("=========================================================")
    
    account_id = "personal_outreach"
    workspace_id = "default_workspace"
    target_url = "https://www.linkedin.com/in/williamhgates/"
    
    print(f"[*] Booting browser in HEADLESS mode using account: {account_id}")
    
    # Initialize the browser engine in headless mode (default)
    browser = LinkedInBrowser(
        workspace_id=workspace_id,
        account_id=account_id,
        headless=True
    )

    try:
        await browser.init_browser()
        
        print(f"[*] Navigating silently to target profile: {target_url}")
        await browser.page.goto(target_url, wait_until="domcontentloaded")
        
        # Adding a slight delay to allow React hydration and rendering
        await asyncio.sleep(3)
        
        print("[*] Extracting profile data...")
        
        # Scrape Name (LinkedIn's generic h1 class for profiles)
        name_locator = browser.page.locator('h1').first
        name = await name_locator.inner_text() if await name_locator.count() > 0 else "Unknown Name"
        
        # Scrape Headline (LinkedIn's generic text-body-medium class right under the name)
        headline_locator = browser.page.locator('div[data-generated-suggestion-target]').first
        headline = await headline_locator.inner_text() if await headline_locator.count() > 0 else "Unknown Headline"
        
        # If the specific headline locator fails, fallback to the text-body-medium class
        if headline == "Unknown Headline":
            fallback_locator = browser.page.locator('.text-body-medium').first
            if await fallback_locator.count() > 0:
                headline = await fallback_locator.inner_text()

        print("\n=========================================================")
        print(" DATA EXTRACTION SUCCESSFUL ")
        print("=========================================================")
        print(f"Name     : {name.strip()}")
        print(f"Headline : {headline.strip()}")
        print("=========================================================\n")
        
    except Exception as e:
        cleaned_error = str(e).encode('ascii', 'ignore').decode('ascii')
        print(f"\n[Error] Test failed: {cleaned_error}")
    finally:
        print("[*] Shutting down headless browser...")
        await browser.close()
        print("[*] Complete.")

if __name__ == "__main__":
    asyncio.run(main())
