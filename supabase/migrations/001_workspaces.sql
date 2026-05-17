CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE workspaces (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text NOT NULL,
  owner_id uuid,
  branding jsonb DEFAULT '{}',
  plan text DEFAULT 'starter' CHECK (plan IN ('starter','pro','agency')),
  created_at timestamptz DEFAULT now()
);

ALTER TABLE workspaces ENABLE ROW LEVEL SECURITY;
