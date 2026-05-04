-- partial_leave_migration.sql
-- Run in Supabase Dashboard → SQL Editor → New Query
--
-- Adds partial-day leave support:
--   doctor_leaves: start_time / end_time / leave_type
--   doctor_blocked_dates: start_time / end_time / block_type
--   Removes the full-day UNIQUE constraint so a doctor can have
--   multiple partial blocks on the same calendar date.

-- ── doctor_leaves ─────────────────────────────────────────────────────────────
ALTER TABLE doctor_leaves
  ADD COLUMN IF NOT EXISTS start_time  TIME,
  ADD COLUMN IF NOT EXISTS end_time    TIME,
  ADD COLUMN IF NOT EXISTS leave_type  TEXT NOT NULL DEFAULT 'full_day'
    CHECK (leave_type IN ('full_day', 'partial'));

-- Remove the old unique constraint that prevented two leave rows on same date
ALTER TABLE doctor_leaves
  DROP CONSTRAINT IF EXISTS doctor_leaves_doctor_id_leave_date_key;

-- New constraint: one full-day leave OR many partials, but no duplicate partial windows
CREATE UNIQUE INDEX IF NOT EXISTS uq_leave_full_day
  ON doctor_leaves (doctor_id, leave_date)
  WHERE leave_type = 'full_day';

CREATE UNIQUE INDEX IF NOT EXISTS uq_leave_partial_window
  ON doctor_leaves (doctor_id, leave_date, start_time, end_time)
  WHERE leave_type = 'partial';

-- ── doctor_blocked_dates ──────────────────────────────────────────────────────
ALTER TABLE doctor_blocked_dates
  ADD COLUMN IF NOT EXISTS start_time  TIME,
  ADD COLUMN IF NOT EXISTS end_time    TIME,
  ADD COLUMN IF NOT EXISTS block_type  TEXT NOT NULL DEFAULT 'full_day'
    CHECK (block_type IN ('full_day', 'partial'));

ALTER TABLE doctor_blocked_dates
  DROP CONSTRAINT IF EXISTS doctor_blocked_dates_doctor_id_blocked_date_key;

CREATE UNIQUE INDEX IF NOT EXISTS uq_block_full_day
  ON doctor_blocked_dates (doctor_id, blocked_date)
  WHERE block_type = 'full_day';

CREATE UNIQUE INDEX IF NOT EXISTS uq_block_partial_window
  ON doctor_blocked_dates (doctor_id, blocked_date, start_time, end_time)
  WHERE block_type = 'partial';
