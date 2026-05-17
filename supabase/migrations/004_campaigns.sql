CREATE TABLE campaigns (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid REFERENCES workspaces(id) ON DELETE CASCADE NOT NULL,
  name text NOT NULL,
  status text DEFAULT 'draft' CHECK (status IN ('draft','active','paused','completed','error')),
  account_ids uuid[] DEFAULT '{}',
  sequence jsonb DEFAULT '[]',
  daily_limit int DEFAULT 50,
  icp_description text,
  stats jsonb DEFAULT '{"sent":0,"connected":0,"replied":0,"meetings":0}',
  created_at timestamptz DEFAULT now(),
  started_at timestamptz
);

ALTER TABLE campaigns ENABLE ROW LEVEL SECURITY;
