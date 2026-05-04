-- =============================================================================
-- AADITYAA HOSPITAL — Health Packages Seed Data
-- Run AFTER supabase_schema.sql and seed_data.sql.
-- These are realistic Indian private-hospital style health checkup packages.
-- =============================================================================

-- Create the health_packages table if it doesn't exist yet
CREATE TABLE IF NOT EXISTS public.health_packages (
    id             UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
    name           TEXT    NOT NULL,
    slug           TEXT    NOT NULL UNIQUE,
    tagline        TEXT,
    description    TEXT,
    price          NUMERIC(10,2) NOT NULL,
    original_price NUMERIC(10,2),
    target_group   TEXT,           -- 'General' | 'Women' | 'Men' | 'Senior' | 'Children'
    tests          TEXT[],         -- list of tests / procedures included
    duration       TEXT,           -- '1 Day' | 'Half Day' | '2 Days'
    icon           TEXT,           -- Material Symbol name
    is_active      BOOLEAN NOT NULL DEFAULT TRUE,
    sort_order     INT     NOT NULL DEFAULT 0,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Clear and re-seed
DELETE FROM public.health_packages;

INSERT INTO public.health_packages
  (name, slug, tagline, description, price, original_price,
   target_group, tests, duration, icon, sort_order)
VALUES

(
  'Basic Health Checkup',
  'basic-health',
  'Start your wellness journey',
  'A comprehensive starter package covering the most important routine investigations for adults of all ages. Ideal for annual health monitoring.',
  999.00, 1499.00,
  'General',
  ARRAY[
    'Complete Blood Count (CBC)',
    'Blood Sugar (Fasting & PP)',
    'Lipid Profile',
    'Liver Function Test (LFT)',
    'Kidney Function Test (KFT)',
    'Urine Routine & Microscopy',
    'Thyroid Profile (TSH)',
    'Chest X-Ray (PA View)',
    'ECG',
    'Doctor Consultation'
  ],
  'Half Day', 'health_and_safety', 1
),

(
  'Women''s Wellness Package',
  'womens-wellness',
  'Comprehensive care crafted for women',
  'Designed specifically for women aged 21–60. Covers hormonal health, reproductive wellness, bone density, and cancer screenings relevant to women.',
  2499.00, 3499.00,
  'Women',
  ARRAY[
    'Complete Blood Count (CBC)',
    'Blood Sugar & HbA1c',
    'Lipid Profile',
    'Thyroid Panel (T3, T4, TSH)',
    'Hormonal Profile (FSH, LH, Prolactin, Estrogen)',
    'Pap Smear',
    'Mammography (Bilateral)',
    'Bone Mineral Density (BMD)',
    'Vitamin D & B12',
    'Iron Studies',
    'Urine Routine',
    'Gynaecologist Consultation'
  ],
  '1 Day', 'pregnant_woman', 2
),

(
  'Men''s Health Package',
  'mens-health',
  'Stay ahead, stay strong',
  'Tailored for men aged 25–60. Focused on cardiovascular health, prostate screening, metabolic fitness, and lifestyle disease prevention.',
  1999.00, 2799.00,
  'Men',
  ARRAY[
    'Complete Blood Count (CBC)',
    'Blood Sugar & HbA1c',
    'Lipid Profile (Full)',
    'Liver & Kidney Function',
    'PSA (Prostate Specific Antigen)',
    'Testosterone Level',
    'Thyroid Profile (TSH)',
    'Vitamin D & B12',
    'Uric Acid',
    'ECG + Treadmill Test (TMT)',
    'Chest X-Ray',
    'Physician Consultation'
  ],
  '1 Day', 'fitness_center', 3
),

(
  'Senior Citizen Package',
  'senior-citizen',
  'Complete care for our elders',
  'A thorough package for those above 60. Covers cardiac function, diabetes management, bone health, eye checkup, and neurological baseline screening.',
  3499.00, 4999.00,
  'Senior',
  ARRAY[
    'Complete Blood Count & ESR',
    'Blood Sugar & HbA1c',
    'Lipid Profile',
    'Liver & Kidney Function',
    'Thyroid Panel (T3, T4, TSH)',
    'Vitamin D, B12 & Calcium',
    '2D Echo + ECG',
    'Carotid Doppler',
    'Bone Mineral Density (BMD)',
    'Eye Examination (Slit Lamp)',
    'Hearing Test (Audiometry)',
    'Urine Routine + Culture',
    'Chest X-Ray + Abdomen USG',
    'Geriatric Physician Consultation'
  ],
  '2 Days', 'elderly', 4
),

(
  'Heart Care Package',
  'heart-care',
  'Protect the heart that keeps you going',
  'Advanced cardiac screening for anyone with family history of heart disease, chest pain, hypertension, or simply wanting a thorough heart assessment.',
  3999.00, 5499.00,
  'General',
  ARRAY[
    'Lipid Profile (Full)',
    'hs-CRP (High-Sensitivity C-Reactive Protein)',
    'Homocysteine',
    'Lipoprotein(a)',
    'BNP / NT-proBNP',
    'Blood Sugar & HbA1c',
    'ECG (12-Lead)',
    'TMT (Treadmill Stress Test)',
    '2D Echocardiogram',
    'Holter Monitoring (24 hr)',
    'Chest X-Ray (PA View)',
    'Cardiologist Consultation'
  ],
  '1 Day', 'favorite', 5
),

(
  'Diabetes Management Package',
  'diabetes-care',
  'Control, prevent, and monitor diabetes',
  'Comprehensive diabetes assessment for both newly diagnosed and long-term diabetic patients. Covers complications monitoring and lifestyle counselling.',
  1799.00, 2499.00,
  'General',
  ARRAY[
    'Blood Glucose (Fasting, PP, Random)',
    'HbA1c (3-month average)',
    'Insulin Fasting',
    'C-Peptide',
    'Kidney Function Test',
    'Microalbumin (Urine)',
    'Lipid Profile',
    'Liver Function Test',
    'Thyroid Profile (TSH)',
    'Fundus Examination (Diabetic Retinopathy)',
    'Foot Examination (Neuropathy Check)',
    'Nutritionist Consultation',
    'Diabetologist Consultation'
  ],
  '1 Day', 'glucose', 6
),

(
  'Child Health Package',
  'child-health',
  'A healthy start for your little ones',
  'Designed for children aged 5–18. Tracks growth, nutritional status, vaccination history review, and common paediatric health markers.',
  1299.00, 1799.00,
  'Children',
  ARRAY[
    'Complete Blood Count (CBC)',
    'Blood Group & Rh Typing',
    'Blood Sugar (Fasting)',
    'Haemoglobin & Iron Studies',
    'Vitamin D & B12',
    'Calcium & Phosphorus',
    'Urine Routine',
    'Stool Routine',
    'Vision & Eye Test',
    'Hearing Screening',
    'Height, Weight, BMI Chart',
    'Vaccination Status Review',
    'Paediatrician Consultation'
  ],
  'Half Day', 'child_care', 7
),

(
  'Full Body Master Checkup',
  'full-body-master',
  'The most comprehensive checkup we offer',
  'Our flagship health package. Over 80 tests across all major organ systems. Recommended annually for executives, high-stress professionals, and anyone who wants full peace of mind.',
  6999.00, 9999.00,
  'General',
  ARRAY[
    'Complete Blood Count + ESR',
    'Blood Sugar & HbA1c',
    'Lipid Profile (Full)',
    'Liver Function (LFT)',
    'Kidney Function (KFT)',
    'Thyroid Panel (T3, T4, TSH)',
    'Vitamin D, B12, Folate',
    'Iron Studies',
    'Uric Acid & Calcium',
    'PSA (Men) / PAP Smear (Women)',
    'CEA + CA-125 + CA 19-9 (Cancer Markers)',
    'ECG + 2D Echo + TMT',
    'Chest X-Ray + Abdomen USG',
    'Pulmonary Function Test (PFT)',
    'Bone Mineral Density (BMD)',
    'Eye & Dental Examination',
    'Physician + Specialist Consultation'
  ],
  '2 Days', 'biotech', 8
);
