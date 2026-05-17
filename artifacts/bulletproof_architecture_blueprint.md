# 🏛️ Phantom-X: Bulletproof Zero-Budget Architecture Blueprint
> **CTO Technical Decision Document (TDD)**
> A master plan to launch a secure, global, zero-cost-overhead outreach engine operating out of India.

---

## 🗺️ Roadmap at a Glance

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       STAGE 1: GLOBAL BILLING (Paddle MoR)                  │
│  • India RBI Compliant   • Zero LLC Fees   • Auto SaaS Quotas Enabled       │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                     STAGE 2: ZERO-COST PROXIES (Home Bridge)                │
│  • Squid SOCKS5 Tunnel   • 100% Free       • High-Trust ISP IP Range        │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    STAGE 3: COOKIE HEALER (Fingerprint Sync)                │
│  • Extension Clones      • Heartbeat cron  • Cookie auto-rotation save      │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                     STAGE 4: SEEDED N8N (Out-of-the-Box Engine)             │
│  • Auto-import flows     • Local Postgres  • 1-Click Sandbox Execution      │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 💳 STAGE 1: India-Compliant International Billing
*   **The Challenge**: RBI (Reserve Bank of India) imposes strict e-mandate rules that block standard Stripe recurring international cards. Stripe has also suspended new individual registration accounts in India. Setting up a US Stripe account requires an expensive US LLC shell ($300–$500 setup + yearly maintenance).
*   **The Solution**: Standardize on a **Merchant of Record (MoR)** like **Lemon Squeezy** or **Paddle**.

### Why This is Bulletproof
*   **Zero Initial Fees**: Lemon Squeezy/Paddle take a small cut per transaction—meaning you pay **$0** until you actually make a sale.
*   **100% Compliant**: They act as the "seller of record," collecting and paying global VAT/taxes and processing payments securely, then wire your earnings cleanly to your Indian bank account via international bank transfer (SWIFT/wire) with zero local RBI regulatory issues.
*   **FastAPI Integration Architecture**:
    *   We map a single generic webhook handler `/api/webhooks/billing` that validates Lemon Squeezy signature tokens.
    *   On a `subscription_created` or `subscription_cancelled` event, the webhook parses the custom client payload containing the `workspace_id` and immediately updates the `subscription_status` and tier configurations in your Supabase `workspaces` table.

---

## 🕵️ STAGE 2: Zero-Cost Bulletproof Proxies (The "Home-Bridge" Tunnel)
*   **The Challenge**: Commercial proxy services (Decodo, Webshare, Bright Data) are expensive recurring costs. However, running scrapers on default cloud server IPs (AWS/DigitalOcean) triggers immediate account restrictions on LinkedIn.
*   **The Solution**: The **SQUID SOCKS5 Home-Bridge Network**.

### The Architecture
Every home internet connection has a dynamic residential IP address with **maximum trust authority** from local ISPs (e.g., Airtel, Comcast, Jio). We build a zero-cost local gateway tunnel:

1.  **The Local Gateway**: We bundle a small open-source **Squid Proxy/Wireguard SOCKS5 server** inside your self-hosted docker configurations.
2.  **The Tunnel**: When a user registers, they run a simple local command (or install a lightweight desktop helper app) that exposes a secure, encrypted SOCKS5 port from their local computer using a free tunnel utility like **Localtunnel** or **Tailscale** (free tier).
3.  **The Routing**:
    ```
    ┌──────────────────────────┐          ┌──────────────────────────┐
    │  Playwright Cloud Worker │ ───────> │  Localtunnel SOCKS5 Port  │
    └──────────────────────────┘          └─────────────┬────────────┘
                                                        │ (Encrypted Tunnel)
                                                        ▼
    ┌──────────────────────────┐          ┌──────────────────────────┐
    │  LinkedIn Secure Target  │ <─────── │   Client's Home Wi-Fi    │
    └──────────────────────────┘          └──────────────────────────┘
    ```
4.  **Why it is Unbannable**: Playwright runs in the cloud, but the actual network packets route through the client's own home Wi-Fi. To LinkedIn, the automation appears *identical* to a legitimate browser session originating from their home computer. It is **100% free** and utilizes the highest-scoring residential IP possible.

---

## 🧠 STAGE 3: Cookie Session Preservation & Fingerprint Cloning
*   **The Challenge**: If an automated browser profile uses a different user-agent, canvas fingerprint, or screen resolution than the user's active browser, LinkedIn detects a "hardware mismatch" and invalidates the session cookie (`li_at`), forcing the account into a verification checkpoint.
*   **The Solution**: **Browser Hardware Twin Sync & Refreshed Heartbeat cron**.

### 1. Hardware Fingerprint Clones (Browser Twin)
We create a lightweight open-source browser extension. When the user logs in and extracts their session cookie, the extension also captures:
*   `navigator.userAgent` (Exact browser version)
*   `window.screen.width` & `window.screen.height`
*   Canvas and WebGL parameters

We store this complete profile payload in Supabase and inject it dynamically into our Playwright container:
```python
# Playwright twin initialization
context = await browser.new_context(
    user_agent=profile["user_agent"],
    viewport={"width": profile["screen_width"], "height": profile["screen_height"]},
    device_scale_factor=1,
    is_mobile=False
)
```

### 2. The Heartbeat & Refresh Cron (Keep-Alive)
LinkedIn cookies degrade if left idle. We run a background heartbeat task every 4 hours:
*   Perform a low-overhead, headless LinkedIn internal API call (e.g., `GET /feed`).
*   **Cookie Auto-Rotation**: Every time LinkedIn validates a session, it returns refreshed session headers. Our heartbeat catches these new response headers and automatically overwrites the stored `li_at` cookie in Supabase.
*   **Active Status**: This maintains an unbroken keep-alive connection, extending cookie lifespans indefinitely without requiring user re-authentication.

---

## 🚀 STAGE 4: Seeds & Out-of-the-Box Setup (n8n & Postgres Local Orchestration)
*   **The Challenge**: Self-hosted developers download the code but face friction manual-configuring databases and blank n8n dashboards.
*   **The Solution**: **Dynamic SQLite/Postgres Seeds & Auto-Import CLI**.

### The Setup
We bundle a complete out-of-the-box local setup within the `/self-hosted` folder:
1.  **Local Database Seed**: Pre-populates the local PostgreSQL container with migrations `001_initial.sql` through `009_billing_and_tenancy.sql` instantly.
2.  **n8n Workflow Seeding**:
    *   We store your master production workflows as JSON templates inside the repository: `self-hosted/n8n/workflows/linkedin_outreach.json`.
    *   During the container initialization, a lightweight Python bootstrap script queries the n8n API (`POST /api/v1/workflows/import`) to automatically populate the n8n container with active, connected workflows.
3.  **Local Dev Experience**: The developer runs `docker compose up -d` and is presented with a fully active, functioning database, API server, Playwright scraper, and preloaded n8n UI—all running locally for **$0**.

---

## 💡 CTO Business & ROI Recommendation
By opting for **Paddle/Lemon Squeezy** and the **Home-Bridge Proxy Network**, you get a complete, robust enterprise SaaS stack with **zero operational overhead**:

*   **Hosting cost**: $0 (if self-hosted) or ~$10/mo for a base VPS (if deployed on cloud).
*   **Proxy cost**: **$0** (routed through home internet).
*   **Taxes/Billing overhead**: **$0** (Paddle acts as Merchant of Record).
*   **User retention**: **Near-100% safety** via hardware fingerprint clones.
