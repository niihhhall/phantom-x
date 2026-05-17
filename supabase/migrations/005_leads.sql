CREATE TABLE leads (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid REFERENCES workspaces(id) ON DELETE CASCADE NOT NULL,
  campaign_id uuid REFERENCES campaigns(id) ON DELETE SET NULL,
  profile_url text NOT NULL,
  full_name text,
  headline text,
  current_title text,
  company text,
  location text,
  about text,
  recent_posts jsonb DEFAULT '[]',
  email text,
  email_confidence text CHECK (email_confidence IN ('verified','likely','guessed',null)),
  icp_score int DEFAULT 0,
  pipeline_stage text DEFAULT 'queued' CHECK (pipeline_stage IN 
    ('queued','sent','connected','replied','interested','booked','closed','not_interested')),
  sent_at timestamptz,
  connected_at timestamptz,
  replied_at timestamptz,
  message_sent text,
  notes text,
  account_id uuid REFERENCES linkedin_accounts(id),
  created_at timestamptz DEFAULT now(),
  UNIQUE(workspace_id, profile_url)
);

ALTER TABLE leads ENABLE ROW LEVEL SECURITY;

CREATE INDEX idx_leads_workspace ON leads(workspace_id);
CREATE INDEX idx_leads_campaign ON leads(campaign_id);
CREATE INDEX idx_leads_stage ON leads(pipeline_stage);
