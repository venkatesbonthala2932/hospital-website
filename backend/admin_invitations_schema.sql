-- =============================================================================
-- AADITYAA HOSPITAL — Admin Invitations
-- Run in Supabase SQL Editor to enable email-based admin onboarding.
-- =============================================================================
--
-- Flow:
--   1. Existing admin invites an email via the dashboard
--   2. A row is inserted in admin_invitations
--   3. When that email signs in (Google or email/password) for the first time,
--      auth_service auto-promotes them to 'admin'

CREATE TABLE IF NOT EXISTS public.admin_invitations (
    email       TEXT PRIMARY KEY,
    -- Firebase UIDs are alphanumeric, not UUIDs — must be TEXT
    invited_by  TEXT,
    accepted_at TIMESTAMPTZ,
    created_at  TIMESTAMPTZ DEFAULT now()
);

-- Fix the column type for anyone who already created the table with UUID
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_schema = 'public'
                 AND table_name   = 'admin_invitations'
                 AND column_name  = 'invited_by'
                 AND data_type    = 'uuid') THEN
        ALTER TABLE public.admin_invitations
            ALTER COLUMN invited_by TYPE TEXT USING invited_by::text;
    END IF;
END$$;

CREATE INDEX IF NOT EXISTS idx_admin_invites_pending
    ON public.admin_invitations(email) WHERE accepted_at IS NULL;
