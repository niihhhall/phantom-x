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

### 4. Run the Zero-Setup Bootstrapper
Run our unified cross-platform Python seeding bootstrapper to automatically boot containers, wait for PostgreSQL/n8n services, execute all 10 SQL migrations, and import your out-of-the-box automation templates:

```bash
python bootstrap.py
```

This single command completes the entire sandboxed initialization automatically and prints the links to your local portals!

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
