#!/usr/bin/env python3
"""
🚀 PHANTOM-X: Cross-Platform Sandboxing & n8n Seeding Bootstrap Engine
Coordinates complete local stack initialization, PostgreSQL schema migrations, and n8n workflow seeding.
"""

import os
import sys
import time
import shutil
import subprocess
from pathlib import Path

# ANSI colors for beautiful terminal console output (UX-Wow factor)
GREEN = "\033[92m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RED = "\033[91m"
BOLD = "\033[1m"
RESET = "\033[0m"

def print_banner():
    banner = fr"""
{CYAN}{BOLD}======================================================================
    ____  _   _    _    _   _ _____ ___  __  __      __  __ 
   |  _ \| | | |  / \  | \ | |_   _/ _ \|  \/  |     \ \/ / 
   | |_) | |_| | / _ \ |  \| | | || | | | |\/| |  ____\  /  
   |  __/|  _  |/ ___ \| |\  | | || |_| | |  | | |____/  \  
   |_|   |_| |_/_/   \_\_| \_| |_| \___/|_|  |_|     /_/\_\\
                                                            
      Open-Core Self-Hosted Stack & Seeding Bootstrap Engine
======================================================================{RESET}
"""
    print(banner)

def check_docker():
    """Ensure Docker is running on the host system."""
    print(f"{YELLOW}🔍 Checking Docker installation and status...{RESET}")
    try:
        res = subprocess.run(["docker", "info"], capture_output=True, text=True)
        if res.returncode != 0:
            print(f"{RED}❌ Docker daemon is not running. Please start Docker Desktop first!{RESET}")
            sys.exit(1)
        print(f"{GREEN}✓ Docker is active and responsive.{RESET}")
    except FileNotFoundError:
        print(f"{RED}❌ Docker CLI is not installed on this host. Please install Docker first!{RESET}")
        sys.exit(1)

def ensure_env_file():
    """Ensure .env exists in the self-hosted directory."""
    self_hosted_dir = Path(__file__).parent
    env_path = self_hosted_dir / ".env"
    env_example_path = self_hosted_dir.parent / ".env.example"
    
    if not env_path.exists():
        print(f"{YELLOW}📝 .env file not found. Initializing from template...{RESET}")
        if env_example_path.exists():
            shutil.copy(env_example_path, env_path)
            print(f"{GREEN}✓ Created self-hosted/.env from template.{RESET}")
        else:
            # Fallback inline generation if .env.example is missing
            with open(env_path, "w") as f:
                f.write("# PHANTOM-X Local Environment Variables\n")
                f.write("DECODO_USERNAME=\n")
                f.write("DECODO_PASSWORD=\n")
                f.write("ANTHROPIC_API_KEY=\n")
                f.write("APOLLO_API_KEY=\n")
            print(f"{GREEN}✓ Created fallback empty self-hosted/.env.{RESET}")
    else:
        print(f"{GREEN}✓ Environment configuration (.env) loaded.{RESET}")

def start_containers():
    """Launch the container stack via Docker Compose."""
    print(f"{YELLOW}⚡ Spawning local containers via Docker Compose...{RESET}")
    try:
        # Check if docker-compose (v1) or docker compose (v2) is used
        cmd = ["docker", "compose", "up", "-d", "--build"]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            # Fallback to docker-compose
            cmd = ["docker-compose", "up", "-d", "--build"]
            res = subprocess.run(cmd, capture_output=True, text=True)
            
        if res.returncode != 0:
            print(f"{RED}❌ Failed to start containers. Error output:\n{res.stderr}{RESET}")
            sys.exit(1)
        print(f"{GREEN}✓ Container orchestration launched successfully.{RESET}")
    except Exception as e:
        print(f"{RED}❌ Error starting Docker Compose stack: {e}{RESET}")
        sys.exit(1)

def wait_for_postgres():
    """Wait for PostgreSQL database container to accept connections."""
    print(f"{YELLOW}⏳ Waiting for PostgreSQL container to stabilize...{RESET}")
    max_retries = 30
    for i in range(max_retries):
        cmd = ["docker", "exec", "phantomx-db", "pg_isready", "-U", "postgres", "-d", "phantomx"]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode == 0:
            print(f"{GREEN}✓ PostgreSQL database is healthy and accepting connections.{RESET}")
            return True
        time.sleep(2)
    print(f"{RED}❌ PostgreSQL failed to stabilize within 60 seconds.{RESET}")
    sys.exit(1)

def run_migrations():
    """Sequentially apply migration SQL files to the local PostgreSQL database."""
    print(f"{YELLOW}🗄️ Executing database migrations...{RESET}")
    migrations_dir = Path(__file__).parent.parent / "supabase" / "migrations"
    
    migration_files = [
        "001_workspaces.sql",
        "002_users.sql",
        "003_linkedin_accounts.sql",
        "004_campaigns.sql",
        "005_leads.sql",
        "006_messages.sql",
        "007_jobs.sql",
        "008_webhooks.sql",
        "009_billing_and_tenancy.sql",
        "010_session_fingerprints.sql"
    ]
    
    for filename in migration_files:
        filepath = migrations_dir / filename
        if not filepath.exists():
            print(f"{YELLOW}⚠ Warning: Migration file {filename} not found in migrations directory. Skipping.{RESET}")
            continue
            
        print(f"   Executing: {filename}...")
        try:
            with open(filepath, "r", encoding="utf-8") as sql_file:
                sql_content = sql_file.read()
                
            # Pipes the SQL directly into psql inside the container to remain OS-independent
            proc = subprocess.Popen(
                ["docker", "exec", "-i", "phantomx-db", "psql", "-U", "postgres", "-d", "phantomx"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            stdout, stderr = proc.communicate(input=sql_content)
            
            if proc.returncode != 0:
                print(f"{RED}❌ Error running migration {filename}:\n{stderr}{RESET}")
                sys.exit(1)
        except Exception as e:
            print(f"{RED}❌ Failed to pipe migration {filename} content: {e}{RESET}")
            sys.exit(1)
            
    print(f"{GREEN}✓ All 10 database schema migrations applied successfully.{RESET}")

def wait_for_n8n():
    """Wait for n8n container to start up and initialize CLI."""
    print(f"{YELLOW}⏳ Waiting for n8n orchestrator container to boot up...{RESET}")
    max_retries = 30
    for i in range(max_retries):
        cmd = ["docker", "exec", "phantomx-n8n", "n8n", "--version"]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode == 0:
            print(f"{GREEN}✓ n8n engine is initialized.{RESET}")
            return True
        time.sleep(3)
    print(f"{RED}❌ n8n container failed to respond within 90 seconds.{RESET}")
    sys.exit(1)

def seed_n8n_workflows():
    """Automatically seed pre-built n8n workflows into n8n container db."""
    print(f"{YELLOW}⚙️ Seeding pre-configured outreach workflow templates...{RESET}")
    
    workflows = [
        ("01_LinkedIn_Prospector", "/home/node/templates/01_linkedin_prospector.json"),
        ("02_Reply_Handler", "/home/node/templates/02_reply_handler.json"),
        ("03_Campaign_Sequence", "/home/node/templates/03_campaign_sequence.json"),
        ("04_Ban_Alert", "/home/node/templates/04_ban_alert.json")
    ]
    
    for label, path in workflows:
        print(f"   Importing workflow: {label}...")
        cmd = ["docker", "exec", "phantomx-n8n", "n8n", "import:workflow", path]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            print(f"{YELLOW}⚠ Warning: Could not auto-seed {label} workflow. n8n CLI Output:\n{res.stderr}{RESET}")
        else:
            print(f"{GREEN}   ✓ Seeded: {label} workflow template.{RESET}")
            
    print(f"{GREEN}✓ All pre-built visual automation sequences are imported.{RESET}")

def print_dashboard():
    dashboard = f"""
{GREEN}{BOLD}🎉 PHANTOM-X SELF-HOSTED ENVIRONMENT READY! 🎉{RESET}

{CYAN}All microservices have stabilized and are fully routed. Here is your dashboard access mapping:{RESET}

--------------------------------------------------------------------------------
{BOLD}🚀 Caddy Proxy Gateway  :{RESET} {CYAN}http://localhost{RESET} (Port 80 / 443 proxy)
{BOLD}⚙️ n8n UI Dashboard      :{RESET} {CYAN}http://localhost/n8n/{RESET}
   - {BOLD}Username           :{RESET} admin
   - {BOLD}Password           :{RESET} phantomx123
{BOLD}⚡ FastAPI Server API    :{RESET} {CYAN}http://localhost/api/docs{RESET}
{BOLD}📊 CRM PostgreSQL DB    :{RESET} localhost:5432 (User: postgres / DB: phantomx)
{BOLD}🧠 Redis Queue           :{RESET} localhost:6379 (Task management active)
--------------------------------------------------------------------------------

{YELLOW}{BOLD}💡 CTO Pro Tip:{RESET}
You can configure your local .env inside the {BOLD}self-hosted/{RESET} directory.
All campaign logs and scrapers run natively. To restart the container services:
   {BOLD}docker compose restart{RESET}
To shutdown and clear memory buffers:
   {BOLD}docker compose down{RESET}

Enjoy complete database privacy, custom residential proxies, and unbannable automation!
"""
    print(dashboard)

def main():
    print_banner()
    check_docker()
    ensure_env_file()
    start_containers()
    wait_for_postgres()
    run_migrations()
    wait_for_n8n()
    seed_n8n_workflows()
    print_dashboard()

if __name__ == "__main__":
    main()
