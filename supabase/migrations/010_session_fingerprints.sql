-- 010_session_fingerprints.sql
-- Database Migration: Session Preservation, Fingerprint Cloning & Validation Logs

ALTER TABLE linkedin_accounts
ADD COLUMN IF NOT EXISTS session_valid boolean DEFAULT true,
ADD COLUMN IF NOT EXISTS fingerprint jsonb DEFAULT '{
  "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
  "screen_width": 1920,
  "screen_height": 1080,
  "canvas_hash": null,
  "webgl_vendor": "Google Inc. (Intel)"
}'::jsonb,
ADD COLUMN IF NOT EXISTS session_state jsonb DEFAULT '{}'::jsonb;

-- Create an index to quickly scan expired/restricted accounts for keep-alive validation crons
CREATE INDEX IF NOT EXISTS idx_linkedin_accounts_health 
ON linkedin_accounts (status, session_valid);
