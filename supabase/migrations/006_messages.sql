CREATE TABLE messages (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  lead_id uuid REFERENCES leads(id) ON DELETE CASCADE NOT NULL,
  direction text CHECK (direction IN ('outbound','inbound')),
  content text NOT NULL,
  sent_via uuid REFERENCES linkedin_accounts(id),
  created_at timestamptz DEFAULT now()
);

ALTER TABLE messages ENABLE ROW LEVEL SECURITY;
