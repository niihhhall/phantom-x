CREATE TABLE linkedin_accounts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid REFERENCES workspaces(id) ON DELETE CASCADE NOT NULL,
  label text NOT NULL,
  li_at_encrypted text NOT NULL,
  status text DEFAULT 'warming_up' CHECK (status IN ('active','warming_up','restricted','expired')),
  warmup_day int DEFAULT 1,
  daily_limit int DEFAULT 50,
  actions_today int DEFAULT 0,
  proxy_country text DEFAULT 'US',
  safety_score int DEFAULT 100,
  last_health_check timestamptz,
  created_at timestamptz DEFAULT now()
);

ALTER TABLE linkedin_accounts ENABLE ROW LEVEL SECURITY;
