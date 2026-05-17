-- 009_billing_and_tenancy.sql
-- Database Migration: Open-Core SaaS Stripe Billing & Multi-Tenant Quotas

-- 1. Extend workspaces table with Stripe billing fields
ALTER TABLE workspaces 
ADD COLUMN IF NOT EXISTS stripe_customer_id text UNIQUE,
ADD COLUMN IF NOT EXISTS stripe_subscription_id text UNIQUE,
ADD COLUMN IF NOT EXISTS subscription_status text DEFAULT 'active' 
  CHECK (subscription_status IN ('active', 'trialing', 'past_due', 'canceled', 'unpaid')),
ADD COLUMN IF NOT EXISTS quota_limits jsonb DEFAULT '{
  "max_linkedin_accounts": 1,
  "max_daily_actions_per_account": 50,
  "max_leads_per_month": 500,
  "allow_ai_personalization": true,
  "allow_email_enrichment": false,
  "allow_multi_account_rotation": false
}'::jsonb;

-- 2. Create custom functions to retrieve current active limits per workspace
CREATE OR REPLACE FUNCTION get_workspace_limits(p_workspace_id uuid)
RETURNS jsonb AS $$
DECLARE
  v_plan text;
  v_limits jsonb;
  v_status text;
BEGIN
  SELECT plan, quota_limits, subscription_status 
  INTO v_plan, v_limits, v_status 
  FROM workspaces 
  WHERE id = p_workspace_id;
  
  -- If subscription is canceled or unpaid, revoke execution privileges
  IF v_status IN ('canceled', 'unpaid') THEN
    RETURN '{
      "max_linkedin_accounts": 0,
      "max_daily_actions_per_account": 0,
      "max_leads_per_month": 0,
      "allow_ai_personalization": false,
      "allow_email_enrichment": false,
      "allow_multi_account_rotation": false
    }'::jsonb;
  END IF;

  -- Default dynamic limits if quota_limits json is empty
  IF v_limits IS NULL OR v_limits = '{}'::jsonb THEN
    IF v_plan = 'starter' THEN
      RETURN '{
        "max_linkedin_accounts": 1,
        "max_daily_actions_per_account": 50,
        "max_leads_per_month": 500,
        "allow_ai_personalization": true,
        "allow_email_enrichment": false,
        "allow_multi_account_rotation": false
      }'::jsonb;
    ELSIF v_plan = 'pro' THEN
      RETURN '{
        "max_linkedin_accounts": 5,
        "max_daily_actions_per_account": 100,
        "max_leads_per_month": 2000,
        "allow_ai_personalization": true,
        "allow_email_enrichment": true,
        "allow_multi_account_rotation": true
      }'::jsonb;
    ELSIF v_plan = 'agency' THEN
      RETURN '{
        "max_linkedin_accounts": 999,
        "max_daily_actions_per_account": 150,
        "max_leads_per_month": 10000,
        "allow_ai_personalization": true,
        "allow_email_enrichment": true,
        "allow_multi_account_rotation": true
      }'::jsonb;
    END IF;
  END IF;

  RETURN v_limits;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- 3. Add index on Stripe tracking IDs for rapid webhook resolution
CREATE INDEX IF NOT EXISTS idx_workspaces_stripe_customer ON workspaces(stripe_customer_id);
CREATE INDEX IF NOT EXISTS idx_workspaces_stripe_sub ON workspaces(stripe_subscription_id);
