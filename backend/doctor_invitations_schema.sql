-- =============================================================================
-- AADITYAA HOSPITAL — Doctor Invitations
-- Run in Supabase SQL Editor to enable email-based doctor onboarding.
-- =============================================================================
--
-- Flow:
--   1. Admin adds invite via frontend (email + name + specialty + ...)
--   2. A row is inserted here AND a placeholder doctors row is created
--      (user_id will be NULL until the doctor first signs in)
--   3. When the invited person signs in (Google or email) for the first time,
--      auth_service detects their email in pending_invitations and auto-promotes
--      them to 'doctor' role, linking the doctor row to their Firebase UID.

-- The doctors.user_id column must be nullable so we can pre-create the record
-- before the doctor has signed in. (May already be nullable — IF NOT EXISTS is
-- not valid for ALTER COLUMN, so we use DO block to be safe.)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_schema = 'public'
                 AND table_name   = 'doctors'
                 AND column_name  = 'user_id'
                 AND is_nullable  = 'NO') THEN
        ALTER TABLE public.doctors ALTER COLUMN user_id DROP NOT NULL;
    END IF;
END$$;

CREATE TABLE IF NOT EXISTS public.doctor_invitations (
    email          TEXT PRIMARY KEY,
    doctor_id      UUID REFERENCES public.doctors(id) ON DELETE CASCADE,
    -- invited_by stores the inviter's Firebase UID, which is an alphanumeric
    -- string (NOT a UUID). TEXT is the correct type here.
    invited_by     TEXT,
    invited_email  TEXT,
    accepted_at    TIMESTAMPTZ,
    created_at     TIMESTAMPTZ DEFAULT now()
);

-- If you already created the table with UUID typed invited_by, run this once
-- to fix the column type. Safe / idempotent.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_schema = 'public'
                 AND table_name   = 'doctor_invitations'
                 AND column_name  = 'invited_by'
                 AND data_type    = 'uuid') THEN
        ALTER TABLE public.doctor_invitations
            ALTER COLUMN invited_by TYPE TEXT USING invited_by::text;
    END IF;
END$$;

CREATE INDEX IF NOT EXISTS idx_invites_doctor  ON public.doctor_invitations(doctor_id);
CREATE INDEX IF NOT EXISTS idx_invites_pending ON public.doctor_invitations(email) WHERE accepted_at IS NULL;
