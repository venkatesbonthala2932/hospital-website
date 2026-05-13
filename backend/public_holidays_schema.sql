-- =============================================================================
-- AADITYAA HOSPITAL — Public Holidays
-- Run in Supabase SQL Editor to let admin block hospital-wide holidays.
-- Booking logic skips any date that appears here.
-- =============================================================================

CREATE TABLE IF NOT EXISTS public.public_holidays (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    holiday_date DATE NOT NULL UNIQUE,
    name         TEXT NOT NULL,
    description  TEXT,
    created_at   TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_holidays_date ON public.public_holidays(holiday_date);

-- Seed a few common Indian holidays for the current year (optional)
INSERT INTO public.public_holidays (holiday_date, name, description) VALUES
('2026-01-26', 'Republic Day',     'National holiday — hospital closed for outpatient services.'),
('2026-08-15', 'Independence Day', 'National holiday — hospital closed for outpatient services.'),
('2026-10-02', 'Gandhi Jayanti',   'National holiday — hospital closed for outpatient services.')
ON CONFLICT (holiday_date) DO NOTHING;
