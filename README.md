# 🌌 Phantom-X
> **The Ultimate Self-Hostable, Multi-Tenant LinkedIn Automation & AI Lead-Generation Engine.** 
> An open-core, high-fidelity alternative to PhantomBuster and Waalaxy.

---

## 💡 The Thesis

Generic outreach templates are dying, and traditional SaaS platforms are fragile:
*   **Datacenter IPs are blocked instantly** — LinkedIn flags standard cloud server pools immediately.
*   **Arbitrary limitations** — You are billed for "execution hours" rather than outreach conversions.
*   **Fragile sessions** — Cookie disconnections happen silently, killing outbound pipelines.

**Phantom-X is the cure.** We provide an enterprise-grade, containerized growth-hacking infrastructure that you can self-host locally for free, or scale multi-tenant accounts as a managed cloud service (SaaS) under your own white-labeled brand.

---

## ⚡ Key Capabilities

*   **🕵️ Stealth Browser Automation (Playwright)**: Features out-of-the-box stealth patches, randomized human action delays (3s–8s), progressive 14-day progressive warming schedules, and custom residential proxy bindings per profile.
*   **🧠 Contextual AI outreach (Claude API)**: Ingests prospects' complete histories to score them against your exact ICP criteria and draft hyper-personalized 280-character connection requests.
*   **💧 Apollo & Hunter Email Waterfalls**: Automatically falls back to secondary B2B search APIs to enrich LinkedIn profiles with verified corporate emails when social connections fail.
*   **🔄 Multi-Account Rotation Pools**: Dynamically rotates sending loads across multiple LinkedIn accounts in a campaign pool to bypass individual daily volume ceilings.
*   **💳 SaaS Multi-Tenancy & Subscriptions**: Pre-configured database-level limits (`starter`, `pro`, `agency`) and API middleware ready to hook directly into Stripe subscriptions.

---

## 🏗️ Architecture Stack

```
                     ┌──────────────────────────────────┐
                     │          Caddy Gateway           │
                     └────────────────┬─────────────────┘
                                      │
             ┌────────────────────────┼────────────────────────┐
             ▼                        ▼                        ▼
┌────────────────────────┐  ┌────────────────────────┐  ┌─────────────┐
│  React App (Frontend)  │  │  FastAPI Backend (API)  │  │ n8n Flows   │
└────────────────────────┘  └───────────┬────────────┘  └─────────────┘
                                        │
                               ┌────────┴────────┐
                               ▼                 ▼
                       ┌──────────────┐  ┌──────────────┐
                       │ Redis Queues │  │ PostgreSQL/  │
                       │   (BullMQ)   │  │   Supabase   │
                       └──────┬───────┘  └──────────────┘
                              │
                              ▼
                       ┌──────────────┐
                       │ Playwright   │
                       │ Scraping     │
                       │ Workers      │
                       └──────────────┘
```

---

## 🛠️ Quick Start (Self-Hosted Sandbox)

Run the complete platform, including n8n workflow queues and a local database sandbox, with a single command:

### 1. Prerequisites
Ensure you have [Docker](https://docs.docker.com/get-docker/) and [Docker Compose](https://docs.docker.com/compose/install/) installed.

### 2. Launch Stack
Clone the repository and spin up the sandbox:
```bash
git clone https://github.com/niihhhall/phantom-x.git
cd phantom-x/self-hosted
docker compose up -d
```

This starts:
*   **FastAPI API Gateway** on `http://localhost:8000`
*   **n8n Workflow Dashboards** on `http://localhost:5678`
*   **Redis Queue Monitor** on `http://localhost:6379`
*   **Local PostgreSQL Database** on `port 5432`

---

## 📊 Multi-Tenant Plan Model

If you are running the platform in a managed cloud multi-tenant environment, the built-in `verify_*` middleware automatically enforces limits per workspace:

| Pricing Tier | Cost / Month | LinkedIn Profiles | Daily Actions Limit | Email Enrichment? | Campaign Rotation? |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Starter (OS)** | **Free / Self-Hosted** | **1 Account** | **50 / account** | ❌ (Local CLI only) | ❌ |
| **Pro** | **$49 / mo** | **5 Accounts** | **100 / account** | ✓ (Apollo Waterfall) | ✓ (Round-Robin Pool) |
| **Agency** | **$149 / mo** | **Unlimited (999)** | **150 / account** | ✓ (Apollo Waterfall) | ✓ (Round-Robin Pool) |

---

## 🧪 Quota & Verification Suite
Verify your limits middleware is acting perfectly before going live. Execute our validated mock unit tests:
```bash
# Verify API quota bounds
python test_billing.py
```
Output:
```
Running Billing Quota Test Suite...

test_get_workspace_quota_limits_success: PASSED
test_verify_linkedin_account_quota_breach: PASSED
test_verify_outreach_rotation_quota_breach: PASSED
test_verify_email_enrichment_quota_breach: PASSED
test_verify_leads_quota_breach: PASSED

ALL BILLING QUOTA TESTS PASSED SUCCESSFULLY!
```

---

## 📂 Repository Layout

*   `app/core/billing.py` — Multi-tenant plan capacity enforcement middleware.
*   `app/api/routes/` — Endpoint gateways (`/accounts`, `/campaigns`, `/leads`, `/scrape`).
*   `supabase/migrations/` — SQL table constraints and RLS limit resolution functions.
*   `self-hosted/` — Docker configurations, local seeds, and Caddy reverse proxies.
*   `test_billing.py` — Plan quota unit test assertions.

---

## 📜 License
Phantom-X is open-core software under the **MIT License**. Check out `LICENSE` for details. Fully customizable for your own SaaS startup or corporate outbound teams.
