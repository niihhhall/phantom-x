# 🌐 n8n Automation Templates for Phantom-X

This directory contains production-ready, fully importable **n8n workflow JSON templates** designed to orchestrate and scale your autonomous LinkedIn outreach campaign cycles.

---

## 📂 Workflow Inventory

| Template | File | Trigger | Key Steps & Actions |
| :--- | :--- | :--- | :--- |
| **01** | `01_linkedin_prospector.json` | ⏰ Schedule (Daily 9 AM) | `POST /scrape/trigger` ➔ Wait 30m ➔ `POST /campaigns/{id}/start` ➔ Slack success report |
| **02** | `02_reply_handler.json` | ⚓ Webhook (`lead.replied`) | Claude 3.5 Sonnet Intent Classification ➔ Match `interested` ➔ `PUT /leads/{id}/stage` to `booked` ➔ Slack alert |
| **03** | `03_campaign_sequence.json` | ⚓ Webhook (`lead.connected`) | Wait 3 days ➔ send first follow-up message ➔ Wait 7 days ➔ send final message |
| **04** | `04_ban_alert.json` | ⚓ Webhook (`account.restricted`) | Automatically fetch campaigns ➔ Pauses all using flagged account ➔ Slack emergency alert ➔ ClickUp task |

---

## ⚡ How to Import Workflows into n8n

For each template JSON file:
1. Open your **n8n Instance Editor**.
2. Click the **`+ Add Workflow`** button or open an empty workspace.
3. In the top-right corner, open the menu (three dots icon) and click **`Import from File`**.
4. Select the target template JSON file (e.g., `01_linkedin_prospector.json`).
5. Double-click nodes to configure environment variables and click **`Save`**.

---

## 🔑 Required Credentials & n8n Env Variables

Ensure the following variables are defined in your n8n environment configuration (or mapped inside n8n's **Global Variables / Credentials** tab):

| Variable / Env Name | Description | Example Value |
| :--- | :--- | :--- |
| `PHANTOM_X_API_URL` | Base endpoint of your FastAPI production instance | `https://api.phantom-x.stoicgrowth.com` |
| `PHANTOM_X_API_TOKEN` | Bearer authorization token generated for n8n API | `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...` |
| `ANTHROPIC_API_KEY` | Secret api key used to invoke Claude 3.5 Sonnet | `sk-ant-api03-...` |
| `SLACK_CHANNEL` | Slack channel ID to send workflow updates and alerts | `#outreach-activity` or `C12345678` |
| `CAMPAIGN_ID` | Main campaign ID to run prospector cycles | `f0417b24-d905-4c75-a33f-c50ca6b56500` |
| `SALES_NAVIGATOR_ICP_URL` | Sales Navigator search query targeting ideal clients | `https://www.linkedin.com/sales/search/people?query=...` |
| `CLICKUP_API_TOKEN` | clickup authorization token to create support tickets | `pk_123456_abcdef...` |
| `CLICKUP_LIST_ID` | ClickUp task list ID for emergency restrictions recovery | `9014013456` |

---

## 🔗 How to Activate Webhooks in Phantom-X

For Event-driven triggers (**02_Reply_Handler**, **03_Campaign_Sequence**, **04_Ban_Alert**):

1. **Get n8n Production Webhook URL**:
   * Open the target workflow in n8n.
   * Double-click the **`Webhook Trigger`** node.
   * Copy the **Production URL** (avoid using Test URL in live production cycles).
     * *Example*: `https://n8n.yourdomain.com/webhook/lead-replied-hook`

2. **Register URL in Phantom-X CRM**:
   * Make an HTTP POST call to register the endpoint subscription:
     ```bash
     curl -X POST "https://api.phantom-x.stoicgrowth.com/webhooks/register" \
          -H "Authorization: Bearer <PHANTOM_X_TOKEN>" \
          -H "Content-Type: application/json" \
          -d '{
            "url": "https://n8n.yourdomain.com/webhook/lead-replied-hook",
            "events": ["lead.replied"]
          }'
     ```
   * Event triggers map to subscriptions automatically:
     * Set `events: ["lead.replied"]` for reply handler.
     * Set `events: ["lead.connected"]` for sequence progression.
     * Set `events: ["account.restricted"]` for safety ban alert isolations.

---

## 🛡️ Senior Architect Best Practices

* **Stealth and Safety**: Maintain human-like wait delays. The built-in schedules and sequence wait nodes simulate organic intervals, aligning cleanly with safety limits (5-25 actions/day).
* **Environment Isolation**: Always utilize production-grade HTTPS URLs.
* **API Rate Limits**: The intent classifier model `claude-3-5-sonnet-20241022` utilizes 0 temperature for absolute consistency and low-token output constraints (`max_tokens: 10`) to control latency and API cost.
