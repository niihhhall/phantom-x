# 🚀 Markeye Outreach Engine (PHANTOM-X) — Self-Hosted Guide

Welcome to the self-hosted setup for **Markeye Outreach Engine**, the ultimate developer-friendly, open-source alternative to **PhantomBuster**, HeyReach, and Expandi. 

By running Markeye on your own private infrastructure, you pay **zero monthly seat fees**, avoid brittle datacenter IP blocks using residential sticky proxies, and maintain **100% ownership** of your prospect lead databases.

---

## 🏗️ High-Level Architecture
The self-hosted stack orchestrates the following elements within one single networks subnet:
- **FastAPI Application Server**: Receives API actions, triggers campaign runs, and manages workspace schemas.
- **Playwright Worker Node**: Launches headless Chromium using stealth fingerprints, routing through residential proxy nodes.
- **PostgreSQL Database**: Persistent transactional database containing workspace accounts, active leads, and metrics.
- **Redis Queue Server**: Powers background job scheduling and asynchronous Playwright automation sequences.
- **n8n Orchestrator**: Local visual automation manager to schedule workflows, handle responses, and update leads.
- **Caddy Proxy Gateway**: Auto-resolves domain paths, manages SSL security, and acts as the public web server gateway.

---

## 🛠️ Step-by-Step Installation

### 1. Prerequisites
Ensure you have the following installed on your machine or VPS (e.g., Hetzner, DigitalOcean):
*   **Docker** (v20.10+)
*   **Docker Compose** (v2.0+)
*   **Git**

### 2. Clone the Repository
```bash
git clone https://github.com/niihhhall/phantom-x.git
cd phantom-x/self-hosted
```

### 3. Configure Environment Variables
Copy `.env.example` to create your active configurations file:
```bash
cp ../.env.example .env
```
Open `.env` and fill in your details:
*   `ANTHROPIC_API_KEY`: Required for Claude AI-powered connection message writing.
*   `DECODO_USERNAME` / `DECODO_PASSWORD`: To secure high-trust residential proxy routing per account country.
*   `APOLLO_API_KEY`: Required for multi-channel email enrichment waterfall steps.

### 4. Boot Up the Containers
Launch the container orchestration stack:
```bash
docker compose up -d --build
```
This boots all 6 microservices in the background. Caddy is exposed on port `80` (HTTP) and `443` (HTTPS) of your server.

### 5. Seeding the Database (Migrations)
To set up all relational schemas (workspaces, campaigns, leads, and the limits tracker) inside your local Postgres container, connect to the database and run the migration scripts located in the `supabase/migrations/` directory:

```bash
# Execute local database migrations via Docker
docker exec -i phantomx-db psql -U postgres -d phantomx < ../supabase/migrations/001_workspaces.sql
docker exec -i phantomx-db psql -U postgres -d phantomx < ../supabase/migrations/002_users.sql
docker exec -i phantomx-db psql -U postgres -d phantomx < ../supabase/migrations/003_linkedin_accounts.sql
docker exec -i phantomx-db psql -U postgres -d phantomx < ../supabase/migrations/004_campaigns.sql
docker exec -i phantomx-db psql -U postgres -d phantomx < ../supabase/migrations/005_leads.sql
docker exec -i phantomx-db psql -U postgres -d phantomx < ../supabase/migrations/006_messages.sql
docker exec -i phantomx-db psql -U postgres -d phantomx < ../supabase/migrations/007_jobs.sql
docker exec -i phantomx-db psql -U postgres -d phantomx < ../supabase/migrations/008_webhooks.sql
docker exec -i phantomx-db psql -U postgres -d phantomx < ../supabase/migrations/009_billing_and_tenancy.sql
```

---

## 🔒 Session Safety Rules & Settings

### 1. Dedicated Sticky Residential Proxy Country
For each LinkedIn account you bind to your workspace, specify their country of origin in `proxy_country` (e.g. `US`, `IN`, `DE`). The worker will automatically route every subsequent Playwright session through sticky residential IP blocks originating from that exact region.

### 2. Warm-Up Safeguards
Every newly registered LinkedIn account undergoes automatic warmup, starting at 5 daily profile actions and scaling up linearly to 50 daily actions over 14 days. Daily connection limits are strictly enforced on the API layer and cannot be bypassed.

---

## 🚀 Connect Your n8n Flow Templates
Once running, navigate to `http://localhost/n8n/` (credentials: `admin`/`phantomx123`) to access n8n.
You can import the pre-built outreach template files under `n8n-templates/` to instantly get scheduled campaign scrapers and incoming message notifications running.
