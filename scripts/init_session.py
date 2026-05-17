import os
import sys
import asyncio
from pathlib import Path

# Add root folder to python path to resolve app modules correctly
sys.path.append(str(Path(__file__).parent.parent.resolve()))

from app.workers.browser_engine import LinkedInBrowser
from app.config import settings

async def main():
    print("=========================================================")
    print("      PHANTOM-X PERSISTENT SESSION INITIALIZER          ")
    print("=========================================================")
    print("This utility will launch a visible (headful) browser to")
    print("allow you to manually log into your LinkedIn profile.")
    print("Once logged in, your session state will be saved securely")
    print("to your local persistent cache directory.")
    print("=========================================================\n")

    account_id = "personal_outreach"
    workspace_id = "default_workspace"
    
    # 1. Output directory info
    profile_dir = Path(settings.PROFILE_STORAGE_PATH) / f"profile_{account_id}"
    print(f"[*] Persistent Profile Cache: {profile_dir.resolve()}")
    print("[*] Launching visible browser context...")

    # 2. Initialize LinkedInBrowser in visible (headless=False) mode
    browser = LinkedInBrowser(
        workspace_id=workspace_id,
        account_id=account_id,
        headless=False  # Make it visible on screen
    )

    try:
        await browser.init_browser()
        
        # Navigate to LinkedIn login page
        print("[*] Navigating to LinkedIn login page...")
        await browser.page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded")
        
        print("\n[!] ACTION REQUIRED:")
        print("1. In the open Chrome window, log into your target LinkedIn account.")
        print("2. Solve any CAPTCHAs, enter your MFA/OTP code if prompted.")
        print("3. Verify you can see your home feed (e.g. www.linkedin.com/feed/).")
        print("\n[?] Once fully logged in, return to this terminal.")
        
        # Wait for user confirmation in terminal
        input("\n[?] Press ENTER here when you are fully logged in to save your session... ")
        
        # 3. Verify session was successfully authenticated
        print("\n[*] Validating session authentication...")
        is_authenticated = await browser.login_via_cookie(li_at="")
        
        if is_authenticated:
            print("\n=========================================================")
            print(" SUCCESS! Session authenticated and saved successfully.")
            print(f"Target Folder: {profile_dir.resolve()}")
            print("You can now safely run headless background campaigns.")
            print("=========================================================")
        else:
            print("\n=========================================================")
            print(" WARNING: Session verification failed.")
            print("We did not detect a logged-in home feed URL or search bar.")
            print("Make sure you logged in fully before hitting ENTER.")
            print("=========================================================")

    except Exception as e:
        cleaned_error = str(e).encode('ascii', 'ignore').decode('ascii')
        print(f"\n[Error] An unexpected error occurred: {cleaned_error}")
    finally:
        # 4. Clean up context to ensure everything is flushed to disk
        print("[*] Flushing session cache and closing browser context...")
        await browser.close()
        print("[*] Browser closed cleanly.")

if __name__ == "__main__":
    asyncio.run(main())
