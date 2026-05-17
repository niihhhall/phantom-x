import sys
import asyncio
from pathlib import Path
import shutil
import os

# Add root folder to python path
sys.path.append(str(Path(__file__).parent.parent.resolve()))

from app.core.database import get_db_client
from app.core.auth import hash_password, create_access_token, encrypt_cookie

async def main():
    print("=========================================================")
    print("        PHANTOM-X DATABASE SEEDER & WORKSPACE SETUP      ")
    print("=========================================================")
    
    client = get_db_client()
    
    # 1. Defined UUIDs for local matching
    workspace_id = "e132924a-0202-4c33-9a23-9c67674d4cfb"
    user_id = "d112924a-0101-4c33-9a23-9c67674d4cfa"
    account_id = "9f925b34-850a-4f67-be21-7e0a0b6ede0a"
    campaign_id = "f0417b24-d905-4c75-a33f-c50ca6b56500"
    
    print("[*] Inserting default workspace...")
    try:
        await client.table("workspaces").upsert({
            "id": workspace_id,
            "name": "Stoic Growth Outreach Workspace",
            "plan": "agency"
        }).execute()
        print("  [+] Workspace seeded successfully.")
    except Exception as e:
        print(f"  [!] Workspace insert error: {e}")
        
    print("[*] Inserting default admin user...")
    try:
        await client.table("users").upsert({
            "id": user_id,
            "workspace_id": workspace_id,
            "email": "nihal@stoicgrowth.com",
            "password_hash": hash_password("StoicGrowth2026!"),
            "role": "owner"
        }).execute()
        print("  [+] User seeded successfully.")
    except Exception as e:
        print(f"  [!] User insert error: {e}")
        
    print("[*] Linking LinkedIn Account in DB...")
    # Encrypt a dummy value because our Playwright worker reads from the file cache, not the cookie injection itself
    encrypted_cookie = encrypt_cookie("dummy-cached-session-placeholder")
    try:
        await client.table("linkedin_accounts").upsert({
            "id": account_id,
            "workspace_id": workspace_id,
            "label": "Personal Outreach (Stealth Cache)",
            "li_at_encrypted": encrypted_cookie,
            "status": "active",
            "proxy_country": "US",
            "actions_today": 0,
            "daily_limit": 50
        }).execute()
        print("  [+] LinkedIn account linked successfully.")
    except Exception as e:
        print(f"  [!] LinkedIn account insert error: {e}")

    print("[*] Creating outbound Campaign...")
    try:
        await client.table("campaigns").upsert({
            "id": campaign_id,
            "workspace_id": workspace_id,
            "name": "LinkedIn B2B Outreach Campaign V1",
            "status": "draft",
            "account_ids": [account_id],
            "daily_limit": 50,
            "icp_description": "Founders, CEOs, and CTOs at early stage SaaS startups."
        }).execute()
        print("  [+] Outbound Campaign created successfully.")
    except Exception as e:
        print(f"  [!] Campaign insert error: {e}")

    # 2. Map the browser profile directory to match this account UUID
    profile_src = Path("app/profiles/profile_personal_outreach")
    profile_dest = Path(f"app/profiles/profile_{account_id}")
    
    print(f"[*] Mapping persistent browser profile...")
    if profile_src.exists():
        if profile_dest.exists():
            shutil.rmtree(profile_dest, ignore_errors=True)
        # Rename profile_personal_outreach to profile_{uuid}
        try:
            os.rename(profile_src, profile_dest)
            print(f"  [+] Profile cleanly mapped to: {profile_dest}")
        except Exception as err:
            print(f"  [!] Profile directory mapping error: {err}")
    elif profile_dest.exists():
        print(f"  [+] Profile already correctly mapped to: {profile_dest}")
    else:
        print("  [!] WARNING: Profile folder 'profile_personal_outreach' was not found. Please re-run init_session.py if missing.")

    # 3. Generate access token for n8n API calls
    print("[*] Generating secure n8n API token...")
    token = create_access_token(data={
        "sub": user_id,
        "workspace_id": workspace_id,
        "role": "owner",
        "email": "nihal@stoicgrowth.com"
    })
    
    print("\n=========================================================")
    print("  SEEDING & SETUP COMPLETED ")
    print("=========================================================")
    print(f"WORKSPACE_ID = {workspace_id}")
    print(f"CAMPAIGN_ID  = {campaign_id}")
    print(f"ACCOUNT_ID   = {account_id}")
    print(f"n8n JWT API TOKEN (Keep safe):\n{token}")
    print("=========================================================\n")

if __name__ == "__main__":
    asyncio.run(main())
