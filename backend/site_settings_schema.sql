-- =============================================================================
-- AADITYAA HOSPITAL — Site Settings (CMS)
-- Run this in Supabase SQL Editor to enable admin-editable home page content.
-- =============================================================================

CREATE TABLE IF NOT EXISTS public.site_settings (
    key        TEXT PRIMARY KEY,
    value      TEXT NOT NULL DEFAULT '',
    label      TEXT NOT NULL DEFAULT '',
    group_name TEXT NOT NULL DEFAULT 'general',
    input_type TEXT NOT NULL DEFAULT 'text',   -- text | textarea | url | tel | email
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- ─────────────────────────────────────────────────────────────────────────────
-- BRANDING
-- ─────────────────────────────────────────────────────────────────────────────
INSERT INTO public.site_settings (key, value, label, group_name, input_type) VALUES
('hospital_name',    'Aadityaa Hospital',   'Hospital Name',  'branding', 'text'),
('hospital_logo_letter', 'A',              'Logo Letter',    'branding', 'text'),
('nav_address',      'PI/466, 8, ZP Rd, Phase 4, Teachers Colony, Hastinapuram, Hyderabad, 500070',
                                             'Top Bar Address','branding', 'text'),
('nav_hours',        'Mon-Sat: 10:00 AM – 6:00 PM', 'Top Bar Hours', 'branding', 'text'),
('nav_phone',        '+91 40 1234 5678',    'Top Bar Phone',  'branding', 'tel')
ON CONFLICT (key) DO NOTHING;

-- ─────────────────────────────────────────────────────────────────────────────
-- HERO
-- ─────────────────────────────────────────────────────────────────────────────
INSERT INTO public.site_settings (key, value, label, group_name, input_type) VALUES
('hero_badge',        'Multispeciality Excellence', 'Hero Badge Text', 'hero', 'text'),
('hero_headline_1',   'Where Excellence',           'Hero Headline Line 1', 'hero', 'text'),
('hero_headline_2',   'Meets Compassionate Care',   'Hero Headline Line 2 (coloured)', 'hero', 'text'),
('hero_subtitle',     'Redefining healthcare through clinical precision, world-class medical expertise, and a patient-centric approach that treats you like family.',
                                                    'Hero Subtitle',  'hero', 'textarea'),
('hero_doctor1_name',  'Dr. Aaditya Varma',         'Hero Card 1 – Name',  'hero', 'text'),
('hero_doctor1_role',  'Lead Cardiologist',          'Hero Card 1 – Role (alt text)', 'hero', 'text'),
('hero_doctor1_title', 'Chief Medical Officer',      'Hero Card 1 – Title (below name)', 'hero', 'text'),
('hero_doctor1_photo', 'https://images.unsplash.com/photo-1612349317150-e413f6a5b16d?w=600&q=80&fit=crop',
                                                    'Hero Card 1 – Photo URL', 'hero', 'url'),
('hero_doctor2_name',  'Dr. Meera Reddy',            'Hero Card 2 – Name',  'hero', 'text'),
('hero_doctor2_role',  'Senior Surgeon',             'Hero Card 2 – Role (alt text)', 'hero', 'text'),
('hero_doctor2_title', 'Director of Surgical Excellence', 'Hero Card 2 – Title (below name)', 'hero', 'text'),
('hero_doctor2_photo', 'https://lh3.googleusercontent.com/aida-public/AB6AXuB4tBz033TqpfhHfxDp49v5NVFEGbk3MaToixFSU3dODzX-KCl04u_Jv1CUNh_tBzdrcBYIarBjNdvgByqIYpX9cC-GYx6aD10bcIrD2VZ55b9ilkG6YPQ2-5dcZHwwt4YBeVKgQyqoPsBm9W0GhlvRFFh308pkVwDtYvCdti_uITDjZBKo7OOBV0NJXEMpMyL8Z2LsSVAYkfPEs7Y_S_fqy2-QZcRhqT0IxTpOf1vvYD90KPd8sL-KVVJLm3nv0zjwX-p3nEm4GuFk',
                                                    'Hero Card 2 – Photo URL', 'hero', 'url')
ON CONFLICT (key) DO NOTHING;

-- ─────────────────────────────────────────────────────────────────────────────
-- ABOUT
-- ─────────────────────────────────────────────────────────────────────────────
INSERT INTO public.site_settings (key, value, label, group_name, input_type) VALUES
('about_headline',    'Your Health, Our Commitment.', 'About Headline', 'about', 'text'),
('about_years',       '15+',                          'Years Badge Number', 'about', 'text'),
('about_years_label', 'Years of Clinical Excellence', 'Years Badge Label',  'about', 'text'),
('about_quote',       'At Aadityaa Hospital, we believe healing starts with a calm heart and a clear mind. We have created a sanctuary where technology meets human touch.',
                                                      'About Quote (italic)', 'about', 'textarea'),
('about_description', 'Located in the heart of Hyderabad, Aadityaa Hospital has emerged as a beacon of medical excellence. Our facility is designed to provide comprehensive care across a spectrum of specialties, ensuring that every patient receives personalized attention from our expert team of consultants and caring staff.',
                                                      'About Description', 'about', 'textarea'),
('about_photo',       'https://lh3.googleusercontent.com/aida-public/AB6AXuAFC_GVhK6cGnnJHDO5Wfz5_fxxPxZeOPr8qf0Gw0Hs4OTIU_L4f1QTsQO2TtI14uGYC87HwLkjqIWoMTa8jTpxREsdM88StxTd45AfeIwpJli8ZoqSsWVJrbDPFEM59wm9CFUieBsloUpm7qQPwNi7zXKQLiV9KIVidi3c7JSQdQcYGxUizwfo4IS0a_4p_TzYnNJkvz3t9ghoWINLRUNU1cef3PyPiWc13S5Q_b2rBp9kcLTfHgcpQuSylrlhlbJCU8YdNa8420OM',
                                                      'About Section Photo URL', 'about', 'url')
ON CONFLICT (key) DO NOTHING;

-- ─────────────────────────────────────────────────────────────────────────────
-- CONTACT
-- ─────────────────────────────────────────────────────────────────────────────
INSERT INTO public.site_settings (key, value, label, group_name, input_type) VALUES
('contact_address',   'PI/466, 8, ZP Rd, Phase 4, Teachers Colony, Hastinapuram, Hyderabad, Telangana 500070',
                                                      'Full Address', 'contact', 'text'),
('contact_phone',     '+91 40 1234 5678 / +91 98765 43210', 'Contact Phone', 'contact', 'tel'),
('contact_email',     'info@aadityaahospital.com',    'Contact Email', 'contact', 'email'),
('contact_hours',     'Mon-Sat: 10:00 AM – 6:00 PM', 'Working Hours', 'contact', 'text'),
('emergency_phone',   '+91 40 9999 9999',             'Emergency Phone', 'contact', 'tel')
ON CONFLICT (key) DO NOTHING;

-- ─────────────────────────────────────────────────────────────────────────────
-- FOOTER
-- ─────────────────────────────────────────────────────────────────────────────
INSERT INTO public.site_settings (key, value, label, group_name, input_type) VALUES
('footer_description', 'Providing high-end editorial care and world-class medical excellence to our community for over 15 years.',
                                                      'Footer Description', 'footer', 'textarea')
ON CONFLICT (key) DO NOTHING;
