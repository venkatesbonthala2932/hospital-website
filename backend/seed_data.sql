-- =============================================================================
-- AADITYAA HOSPITAL — Seed Data
-- Run AFTER supabase_schema.sql.
-- Matches the doctors and specialties visible in the HTML pages.
-- =============================================================================


-- ─────────────────────────────────────────────────────────────────────────────
-- SPECIALTIES
-- ─────────────────────────────────────────────────────────────────────────────
INSERT INTO public.specialties (name, slug, description, icon, conditions, treatments) VALUES

('Cardiology', 'cardiology',
 'Advanced cardiovascular care, comprehensive diagnostics, and pioneering interventional procedures for optimal heart health.',
 'favorite',
 ARRAY['Coronary Artery Disease', 'Heart Failure', 'Arrhythmia', 'Hypertension', 'Valve Disorders', 'Congenital Heart Defects'],
 ARRAY['Echocardiography', 'Angioplasty', 'Bypass Surgery', 'Pacemaker Implantation', 'Cardiac Catheterization', 'Robotic Cardiac Surgery']),

('Neurology', 'neurology',
 'Expert diagnosis and treatment for complex brain, spinal cord, and central nervous system disorders.',
 'neurology',
 ARRAY['Stroke', 'Epilepsy', 'Migraine', 'Parkinson''s Disease', 'Multiple Sclerosis', 'Neuropathy', 'Brain Tumours'],
 ARRAY['EEG', 'MRI / CT Neuroimaging', 'Lumbar Puncture', 'Deep Brain Stimulation', 'Neuro-rehabilitation', 'Botox for Migraine']),

('Orthopedics', 'orthopedics',
 'Comprehensive care for bones, joints, muscles, and ligaments, from sports injuries to complex reconstructive surgery.',
 'accessibility',
 ARRAY['Fractures', 'Osteoarthritis', 'Sports Injuries', 'Scoliosis', 'Ligament Tears', 'Bone Tumours'],
 ARRAY['Joint Replacement', 'Arthroscopy', 'Spinal Fusion', 'Sports Medicine', 'Platelet-Rich Plasma (PRP)', 'Physical Therapy']),

('Pediatrics', 'pediatrics',
 'Specialised healthcare for infants, children, and adolescents in a warm and caring environment.',
 'child_care',
 ARRAY['Asthma', 'Childhood Infections', 'Growth Disorders', 'Neonatal Conditions', 'Developmental Delays', 'Behavioural Disorders'],
 ARRAY['Neonatal ICU', 'Vaccination Programs', 'Growth Monitoring', 'Allergy Testing', 'Nutritional Counselling', 'Behavioural Therapy']),

('Gynecology', 'gynecology',
 'Comprehensive women''s health services covering reproductive health, obstetrics, and advanced gynaecological procedures.',
 'pregnant_woman',
 ARRAY['PCOS', 'Endometriosis', 'Fibroids', 'Infertility', 'Cervical Cancer', 'Menstrual Disorders'],
 ARRAY['Laparoscopy', 'Hysteroscopy', 'IVF Support', 'High-Risk Pregnancy Care', 'Colposcopy', 'Minimal-Access Surgery']),

('Dermatology', 'dermatology',
 'Advanced skin care combining clinical dermatology with cosmetic and aesthetic procedures.',
 'face',
 ARRAY['Acne', 'Psoriasis', 'Eczema', 'Melanoma', 'Rosacea', 'Alopecia', 'Vitiligo'],
 ARRAY['Laser Therapy', 'Chemical Peels', 'Phototherapy', 'Skin Biopsy', 'Botox & Fillers', 'PRP Hair Treatment']),

('ENT', 'ent',
 'Specialist care for ear, nose, and throat conditions including head and neck surgery.',
 'hearing',
 ARRAY['Sinusitis', 'Hearing Loss', 'Tonsillitis', 'Sleep Apnoea', 'Vertigo', 'Voice Disorders'],
 ARRAY['Endoscopic Sinus Surgery', 'Tonsillectomy', 'Cochlear Implants', 'Septoplasty', 'Thyroid Surgery', 'Head & Neck Oncology'])

ON CONFLICT (slug) DO NOTHING;


-- ─────────────────────────────────────────────────────────────────────────────
-- DOCTORS
-- Source: doctors.html, cardiology.html, neurology.html, book-appointment-*.html
-- user_id is NULL until each doctor creates their login account.
-- ─────────────────────────────────────────────────────────────────────────────
INSERT INTO public.doctors
    (specialty_id, full_name, title, qualifications, experience_years, bio, consultation_fee, photo_url)
VALUES

-- Cardiology doctors
(
    (SELECT id FROM public.specialties WHERE slug = 'cardiology'),
    'Dr. Aaditya Varma',
    'Senior Cardiologist',
    'MBBS, MD (Medicine), DM (Cardiology) — AIIMS New Delhi',
    18,
    'Chief Medical Officer at Aadityaa Hospital. A pioneer in minimally invasive heart surgeries and complex robotic cardiac interventions with over 18 years of clinical excellence.',
    1200.00,
    'https://lh3.googleusercontent.com/aida-public/AB6AXuBNoHYg_QS7mVzPOzpClaCcftwz0dhyCSNEnPiv5OFmusIKQVJO_OPacZrYvevBCazrcbX5shYEiTVo9-7LEPrJL5NyXjbgbenbyKnXEeZZ5RLu3OTkOjyNEv8R_t3nxcDBM47Gst8yMLfQeTOw1Flk5MRhBlZjDIzhOP4KYOT6ZTn8Ub_hYx_a7ivMcgC3bkUeRuMwlMgSxGaqAQ82gt4ptytwkG-Ohz8pCu6IzjzleA26ctVsT8DWyZWOsXsnvXSpPtZE4mq2nZl2'
),
(
    (SELECT id FROM public.specialties WHERE slug = 'cardiology'),
    'Dr. Vikram Sharma',
    'Consultant Cardiologist',
    'MBBS, MD Cardiology, DM (Cardiology)',
    18,
    'Specialist in interventional cardiology and complex coronary procedures with extensive experience managing high-risk cardiac patients.',
    1000.00,
    'https://lh3.googleusercontent.com/aida-public/AB6AXuCPGFI-YqXNM84zyuhX71_rahjhD1lT36i_KgViIUJNl-sDxP9ANMxoSZgjYLV8_0pLMo9jyYjofla2DmRA9knG8d5yzW7mDvjJI63DqIebcudqRQf3UwsOcuqLa8l2dXhIdcGqWWzwN4Z-C0GDypQ-6CNHst0Gqu4X0tjRmt57IuKpqf4m-gjdpaXzZjXAgf-eIvWfGAnJC9SgV1ixn7Z9Ub2kES5vOlo9zK78PLWFXuFvxRAaQ6XzHMzRZreGnub7_oLVer7pXcHY'
),

-- Neurology doctors
(
    (SELECT id FROM public.specialties WHERE slug = 'neurology'),
    'Dr. Meera Reddy',
    'Chief Neurosurgeon',
    'MBBS (CMC Vellore), MCh (Neurosurgery), Fellowship in Micro-Neurosurgery (Germany)',
    22,
    'Director of Surgical Excellence. A veteran with 22+ years of experience and over 2,000 successful brain and spine procedures.',
    1500.00,
    'https://lh3.googleusercontent.com/aida-public/AB6AXuDsNcB0MOYYiXrfhMWN8tqSOclb9OOZ4FwDPbiQy2xslViHXnJsYDy_aoWx6aR9Eucx1Vi9nO3m11lWhCfkACni56YiQFcq9dTQRc44pIhFgp08lWWA8CLkQHidYdUSWcMGACfItu3Af5M53KbSBYu5cmEJc87cy06MLw6A3dsOE4B_iwCRnM9vdhzUTtsZw0XC4YewOvpM1rikdjs4PkK3wudE_oqqX8reHhz0WGT1izgumqkVWYP8S79tzBc7nCC5LKuS22CuOwZY'
),
(
    (SELECT id FROM public.specialties WHERE slug = 'neurology'),
    'Dr. Sameer Khan',
    'Senior Neurologist',
    'MBBS, MD, DNB (Neurology)',
    15,
    'Distinguished Neurologist specialising in advanced brain and spine care. Brings a compassionate, evidence-based approach to complex neurological disorders.',
    900.00,
    'https://lh3.googleusercontent.com/aida-public/AB6AXuDlxrj1MG80rHaWOPDNHkTnELS5R5fjLmZe2Q4lKFqaLfl7v61_AOLySGucByn7fJ9hJcfkAdX8cfINJ7g1hhxuu_kEGBPArTWgXVOKfy4cPuD-bMfqjcOAOifslKLWLHIwEtbtMiUT10nU1kNSQNa1dl1pkXsnhmNRVQZ8YccaLAmQcvCG62Cz4Y5GiHYqQXRztVuFgvRHjiHKEo55UAtPPEViGqc2JP_tGb5Zc1yQKnwmoh6BI7uToh0jdFBAarMaUIzL7RngwT6v'
),

-- Orthopedics
(
    (SELECT id FROM public.specialties WHERE slug = 'orthopedics'),
    'Dr. Rohan Das',
    'Orthopedic Specialist',
    'MBBS, MS (Orthopedics), MCh — University of Liverpool',
    12,
    'Senior Consultant with 12+ years expertise in sports medicine and arthroplasty, focusing on advanced rehabilitative joint replacement techniques.',
    800.00,
    'https://lh3.googleusercontent.com/aida-public/AB6AXuDCLnb2cQ4hMqd_PG0JgmcAOBe_HT8uu7S6EeZBY_faBALqnZCd6PyVTx4X2GL8MtcjRM_t9oarg3Y6k6Mw_bHJxSI6x4_m0btyF8D5gGIYSclXuWYGh2ausZsawcn10WRVyMK2S1xV4aDHFbBnTSP7YymTekWwlbgNjKd1j5BMmVKiMTHw7k3_3SoxIYzZA7--sqzpxxwDqcxLaX4lSI_c5R9HNUqFl31r_rSsbBc0at5Z_YfTp6kTWViW-jte-uLbN3-tdhmbb89M'
),

-- Pediatrics
(
    (SELECT id FROM public.specialties WHERE slug = 'pediatrics'),
    'Dr. Ananya Iyer',
    'Senior Pediatrician',
    'MBBS, MD (Pediatrics) — AIIMS',
    20,
    'Head of Pediatrics. 20+ years of clinical practice specialising in neonatal intensive care and behavioural pediatrics with several international research publications.',
    700.00,
    'https://lh3.googleusercontent.com/aida-public/AB6AXuCsouJ83LJP0GfdMLrXEpnA3iQMY-tLlqPnIHotWnSeOAntWsGq0MqxuSJ-KP6Lm89ZNUyawPpXQ_DWR961kwhaReXIuTb00za2rN_dhQu4AUqkY6IIp07y4dQNWK9gphB1jArgbtmMo_I3YNCxkoi4NAjMBWAs2z3iHu2hkwaaWKb6Fry-uVv5CO1T09kvdTRxIUPKtPVRK0RFmzL1Ovzd_z_LCExqq5O3Y26iDeZfsVSzK6TQ_PDfZ3OGjjJbMPhEl9eQpvJoTdFP'
),

-- Gynecology
(
    (SELECT id FROM public.specialties WHERE slug = 'gynecology'),
    'Dr. Shalini Gupta',
    'Chief Gynecologist',
    'MBBS, MS (Obstetrics & Gynecology), FRCOG',
    16,
    'Chief Gynecologist with 16+ years of experience in advanced laparoscopic surgery, high-risk pregnancy management, and women''s wellness.',
    850.00,
    'https://lh3.googleusercontent.com/aida-public/AB6AXuAYNyB7JA5b6CiPl3b03tJM5wAabV2vf21iOnIv17O44HgUYntSW_psTtXgblwZ5X1A1d_F2epB4HS2p8v6tKM5_opnrIIFgNqL8wxBeg3jBolTiqE37k-Z36kOPpf9GtZaB6Gbdi-h6obdqr0NIyAfMHOKDDSCoJGgoeZp1jQi592zcD9Ne-8ilv9BAeIFBTCCcQlssfe3JboMKRpN69QEKTR2UTJXg8kfeznafuH9KdQ-KCDC7dRa20hiLOR3ZCE8Dzsf4xoM9j9v'
),

-- Dermatology
(
    (SELECT id FROM public.specialties WHERE slug = 'dermatology'),
    'Dr. Vikram Malhotra',
    'Consultant Dermatologist',
    'MBBS, MD (Dermatology), Fellow of the American Academy of Dermatology',
    15,
    'Senior Dermatologist with a 15+ year career focusing on clinical and aesthetic medicine, laser therapies, and complex skin conditions.',
    750.00,
    'https://lh3.googleusercontent.com/aida-public/AB6AXuDwaGtEbdAPn02lF532lgiSLmAiOdBjyMf94s0_ZWawDDnmg34Q2PulntAlVYAownaJbh3Gcl7nQqsTQdbw2SxZ4c2z9KNfsAxHQY5b_abWhHueR8Kl1UjSPpkbao8Tw1Vmm8E-QiIEnQRN87bcp1MMPCF0Fqr_qAgbE0TLhsEwC77uIUWKLcmeFPiWq8Gp486yRtElz-dNgMbaLjHbvsWRDCq2aau_A7g0UWjoPk-xi8Cx4hf-QG_ThONzYys44idhqk3GoVyonyQJ'
)

ON CONFLICT DO NOTHING;


-- ─────────────────────────────────────────────────────────────────────────────
-- DEFAULT AVAILABILITY (Mon–Sat, 09:00–17:00, 30-min slots)
-- Applied to every doctor just inserted.
-- Adjust per doctor later via the doctor dashboard or directly in Supabase.
-- Day index: 0=Mon, 1=Tue, 2=Wed, 3=Thu, 4=Fri, 5=Sat
-- ─────────────────────────────────────────────────────────────────────────────
INSERT INTO public.doctor_availability (doctor_id, day_of_week, start_time, end_time, slot_duration_minutes)
SELECT
    d.id,
    days.day,
    '09:00'::TIME,
    '17:00'::TIME,
    30
FROM public.doctors d
CROSS JOIN (
    SELECT unnest(ARRAY[0,1,2,3,4,5]) AS day
) AS days
ON CONFLICT (doctor_id, day_of_week) DO NOTHING;
