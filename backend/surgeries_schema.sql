-- surgeries_schema.sql
-- Run this in Supabase SQL Editor (Dashboard → SQL Editor → New Query)

CREATE TABLE IF NOT EXISTS surgeries (
    id               UUID        DEFAULT gen_random_uuid() PRIMARY KEY,
    doctor_id        UUID        NOT NULL REFERENCES doctors(id) ON DELETE CASCADE,
    patient_name     TEXT        NOT NULL DEFAULT '',
    patient_phone    TEXT        NOT NULL DEFAULT '',
    operation_type   TEXT        NOT NULL,
    surgery_date     DATE        NOT NULL,
    surgery_time     TIME        NOT NULL,
    duration_minutes INTEGER     NOT NULL DEFAULT 120,
    theater          TEXT        NOT NULL DEFAULT '',
    notes            TEXT        NOT NULL DEFAULT '',
    status           TEXT        NOT NULL DEFAULT 'scheduled'
                                 CHECK (status IN ('scheduled','completed','cancelled','postponed')),
    created_by       TEXT        NOT NULL DEFAULT '',
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Index for fast lookups by doctor
CREATE INDEX IF NOT EXISTS surgeries_doctor_id_idx ON surgeries(doctor_id);
CREATE INDEX IF NOT EXISTS surgeries_date_idx      ON surgeries(surgery_date);

-- Auto-update updated_at
CREATE OR REPLACE FUNCTION update_surgeries_updated_at()
RETURNS TRIGGER AS $$
BEGIN NEW.updated_at = now(); RETURN NEW; END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS set_surgeries_updated_at ON surgeries;
CREATE TRIGGER set_surgeries_updated_at
    BEFORE UPDATE ON surgeries
    FOR EACH ROW EXECUTE FUNCTION update_surgeries_updated_at();
