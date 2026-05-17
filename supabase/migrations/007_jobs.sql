CREATE TABLE jobs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid REFERENCES workspaces(id) ON DELETE CASCADE,
  type text CHECK (type IN ('scrape','connect','message','enrich','health_check')),
  status text DEFAULT 'queued' CHECK (status IN ('queued','running','done','failed','retrying')),
  payload jsonb DEFAULT '{}',
  result jsonb DEFAULT '{}',
  retries int DEFAULT 0,
  created_at timestamptz DEFAULT now(),
  completed_at timestamptz
);

ALTER TABLE jobs ENABLE ROW LEVEL SECURITY;

CREATE INDEX idx_jobs_status ON jobs(status);
CREATE INDEX idx_jobs_type ON jobs(type);
