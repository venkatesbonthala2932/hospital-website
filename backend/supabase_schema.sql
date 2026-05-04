-- =============================================================================
-- AADITYAA HOSPITAL — Supabase Schema (v2)
-- Auth handled by Firebase. Supabase is the database only.
-- Run this in: Supabase Dashboard → SQL Editor → New Query
-- Run ONCE on a fresh project. Re-running drops and recreates all tables.
-- =============================================================================

-- Drop in reverse dependency order if re-running
DROP TABLE IF EXISTS public.doctor_leaves        CASCADE;
DROP TABLE IF EXISTS public.appointments         CASCADE;
DROP TABLE IF EXISTS public.doctor_blocked_dates CASCADE;
DROP TABLE IF EXISTS public.doctor_availability  CASCADE;
DROP TABLE IF EXISTS public.doctors              CASCADE;
DROP TABLE IF EXISTS public.specialties          CASCADE;
DROP TABLE IF EXISTS public.profiles             CASCADE;

-- Drop old Supabase-auth trigger if it exists
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
DROP FUNCTION IF EXISTS public.handle_new_user();


-- ─────────────────────────────────────────────────────────────────────────────
-- 1. PROFILES
--    id = Firebase UID (string, not UUID) — this is the single source of truth
--    for who is logged in and what their role is.
--    WHY TEXT not UUID: Firebase UIDs are alphanumeric strings, not UUIDs.
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE public.profiles (
    id         TEXT PRIMARY KEY,              -- Firebase UID
    email      TEXT NOT NULL UNIQUE,
    full_name  TEXT NOT NULL DEFAULT '',
    phone      TEXT,
    role       TEXT NOT NULL DEFAULT 'patient'
               CHECK (role IN ('patient', 'doctor', 'admin')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);


-- ─────────────────────────────────────────────────────────────────────────────
-- 2. SPECIALTIES
--    slug is used in URLs: /api/specialties/cardiology
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE public.specialties (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        TEXT NOT NULL UNIQUE,
    slug        TEXT NOT NULL UNIQUE,
    description TEXT,
    icon        TEXT,                          -- Material Symbol name e.g. 'favorite'
    conditions  TEXT[],                        -- Common conditions treated
    treatments  TEXT[],                        -- Common procedures offered
    is_active   BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);


-- ─────────────────────────────────────────────────────────────────────────────
-- 3. DOCTORS
--    user_id links to profiles.id (Firebase UID). NULL until doctor activates
--    their account — the admin sets this after the doctor registers.
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE public.doctors (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id          TEXT UNIQUE REFERENCES public.profiles(id) ON DELETE SET NULL,
    specialty_id     UUID NOT NULL REFERENCES public.specialties(id),
    full_name        TEXT NOT NULL,
    title            TEXT NOT NULL,            -- 'Senior Cardiologist'
    qualifications   TEXT NOT NULL,
    experience_years INT  NOT NULL CHECK (experience_years >= 0),
    bio              TEXT,
    photo_url        TEXT,
    consultation_fee NUMERIC(10,2) NOT NULL DEFAULT 500.00,
    is_available     BOOLEAN NOT NULL DEFAULT TRUE,
    is_active        BOOLEAN NOT NULL DEFAULT TRUE,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);


-- ─────────────────────────────────────────────────────────────────────────────
-- 4. DOCTOR AVAILABILITY  (weekly recurring schedule)
--    day_of_week: 0 = Monday … 6 = Sunday  (Python weekday() convention)
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE public.doctor_availability (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    doctor_id             UUID NOT NULL REFERENCES public.doctors(id) ON DELETE CASCADE,
    day_of_week           INT  NOT NULL CHECK (day_of_week BETWEEN 0 AND 6),
    start_time            TIME NOT NULL,
    end_time              TIME NOT NULL,
    slot_duration_minutes INT  NOT NULL DEFAULT 30 CHECK (slot_duration_minutes > 0),
    is_active             BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT valid_time_range CHECK (end_time > start_time),
    UNIQUE (doctor_id, day_of_week)
);


-- ─────────────────────────────────────────────────────────────────────────────
-- 5. DOCTOR BLOCKED DATES  (ad-hoc holidays)
--    When a date is here, zero slots are returned for that doctor.
--    Rows are inserted here automatically when admin approves a leave request.
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE public.doctor_blocked_dates (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    doctor_id    UUID NOT NULL REFERENCES public.doctors(id) ON DELETE CASCADE,
    blocked_date DATE NOT NULL,
    reason       TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (doctor_id, blocked_date)
);


-- ─────────────────────────────────────────────────────────────────────────────
-- 6. DOCTOR LEAVES  (formal leave requests)
--    Doctor submits → Admin approves/rejects.
--    On approval a row is also inserted into doctor_blocked_dates automatically.
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE public.doctor_leaves (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    doctor_id   UUID NOT NULL REFERENCES public.doctors(id) ON DELETE CASCADE,
    leave_date  DATE NOT NULL,
    reason      TEXT,
    status      TEXT NOT NULL DEFAULT 'pending'
                CHECK (status IN ('pending', 'approved', 'rejected')),
    admin_note  TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (doctor_id, leave_date)
);


-- ─────────────────────────────────────────────────────────────────────────────
-- 7. APPOINTMENTS
--    patient_id = Firebase UID (TEXT) — who booked.
--    UNIQUE constraint is the second guard against double-booking
--    (the first is the slot availability check in appointment_service.py).
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE public.appointments (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id       TEXT NOT NULL REFERENCES public.profiles(id),
    doctor_id        UUID NOT NULL REFERENCES public.doctors(id),
    specialty_id     UUID NOT NULL REFERENCES public.specialties(id),
    appointment_date DATE NOT NULL,
    appointment_time TIME NOT NULL,
    status           TEXT NOT NULL DEFAULT 'pending'
                     CHECK (status IN ('pending', 'confirmed', 'completed', 'cancelled', 'rejected')),
    patient_name     TEXT NOT NULL,
    patient_phone    TEXT,
    patient_email    TEXT,
    notes            TEXT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT no_double_booking UNIQUE (doctor_id, appointment_date, appointment_time)
);

-- Auto-update updated_at on every change
CREATE OR REPLACE FUNCTION public.set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN NEW.updated_at = now(); RETURN NEW; END; $$;

CREATE TRIGGER appointments_updated_at
    BEFORE UPDATE ON public.appointments
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


-- ─────────────────────────────────────────────────────────────────────────────
-- 8. INDEXES  (speed up the most common queries)
-- ─────────────────────────────────────────────────────────────────────────────
CREATE INDEX idx_appointments_doctor_date ON public.appointments (doctor_id, appointment_date);
CREATE INDEX idx_appointments_patient     ON public.appointments (patient_id);
CREATE INDEX idx_appointments_status      ON public.appointments (status);
CREATE INDEX idx_doctors_specialty        ON public.doctors (specialty_id);
CREATE INDEX idx_availability_doctor_day  ON public.doctor_availability (doctor_id, day_of_week);
CREATE INDEX idx_leaves_doctor            ON public.doctor_leaves (doctor_id, status);
