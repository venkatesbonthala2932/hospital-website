#!/usr/bin/env python3
"""
create_test_accounts.py — One-time setup: create Firebase + Supabase test users

Run ONCE from the backend/ directory after running supabase_schema.sql + seed_data.sql:
    source venv/bin/activate
    python3 create_test_accounts.py

What this creates
─────────────────
  ADMIN
    admin@aadityaa.com           / Admin@123

  DOCTORS  (one Firebase account per doctor — linked to their doctor DB row)
    draaditya@aadityaa.com       / Doctor@123   → Dr. Aaditya Varma   (Cardiology)
    drvikram@aadityaa.com        / Doctor@123   → Dr. Vikram Sharma   (Cardiology)
    drmeera@aadityaa.com         / Doctor@123   → Dr. Meera Reddy     (Neurology)
    drsameer@aadityaa.com        / Doctor@123   → Dr. Sameer Khan     (Neurology)
    drrohan@aadityaa.com         / Doctor@123   → Dr. Rohan Das       (Orthopedics)
    drananya@aadityaa.com        / Doctor@123   → Dr. Ananya Iyer     (Pediatrics)
    drshalini@aadityaa.com       / Doctor@123   → Dr. Shalini Gupta   (Gynecology)
    drvmalhotra@aadityaa.com     / Doctor@123   → Dr. Vikram Malhotra (Dermatology)

  PATIENTS  (test patient accounts for booking)
    patient1@test.com            / Patient@123  Rahul Sharma
    patient2@test.com            / Patient@123  Priya Nair
    patient3@test.com            / Patient@123  Arjun Reddy

Safe to re-run — existing accounts are skipped, not duplicated.
"""

import sys
import os
import json

# Make sure we can import from the backend package
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import Config
Config.validate()

import firebase_admin
from firebase_admin import credentials, auth as firebase_auth
from services.supabase_client import get_admin_supabase

# ── Initialise Firebase Admin SDK ─────────────────────────────────────────────
cred_dict = json.loads(Config.FIREBASE_SERVICE_ACCOUNT_JSON)
cred = credentials.Certificate(cred_dict)
if not firebase_admin._apps:
    firebase_admin.initialize_app(cred)

db = get_admin_supabase()


def create_user(email: str, password: str, full_name: str, role: str, phone: str = "") -> str | None:
    """
    Create a Firebase account + matching Supabase profile.
    Returns the Firebase UID on success, None on failure.
    """
    try:
        fb_user = firebase_auth.create_user(
            email=email,
            password=password,
            display_name=full_name,
        )
        uid = fb_user.uid

        # Insert profile row in Supabase (role stored here, not in Firebase)
        db.table("profiles").upsert({
            "id":        uid,
            "email":     email,
            "full_name": full_name,
            "phone":     phone,
            "role":      role,
        }, on_conflict="id").execute()

        print(f"  ✓  Created {role:8s}  {email}  (uid: {uid[:12]}…)")
        return uid

    except firebase_admin.auth.EmailAlreadyExistsError:
        # Account already exists — fetch UID and ensure profile row exists
        fb_user = firebase_auth.get_user_by_email(email)
        uid = fb_user.uid
        db.table("profiles").upsert({
            "id":        uid,
            "email":     email,
            "full_name": full_name,
            "phone":     phone,
            "role":      role,
        }, on_conflict="id").execute()
        print(f"  →  Already exists: {email}  (uid: {uid[:12]}…)")
        return uid

    except Exception as exc:
        print(f"  ✗  FAILED {email}: {exc}")
        return None


def link_doctor(uid: str, doctor_name: str) -> None:
    """Set doctors.user_id so the doctor can log in to the doctor dashboard."""
    result = (
        db.table("doctors")
        .update({"user_id": uid, "is_active": True})
        .eq("full_name", doctor_name)
        .execute()
    )
    if result.data:
        print(f"       → Linked to doctor record: {doctor_name}")
    else:
        print(f"       ⚠  Doctor record not found for: {doctor_name} (run seed_data.sql first)")


# ─────────────────────────────────────────────────────────────────────────────
# Admin
# ─────────────────────────────────────────────────────────────────────────────
print("\n── Admin ────────────────────────────────────────────────────────────")
create_user(
    email     = "admin@aadityaa.com",
    password  = "Admin@123",
    full_name = "Hospital Admin",
    role      = "admin",
    phone     = "+91 40 1234 5678",
)

# ─────────────────────────────────────────────────────────────────────────────
# Doctors  (name must exactly match doctors.full_name in seed_data.sql)
# ─────────────────────────────────────────────────────────────────────────────
print("\n── Doctors ──────────────────────────────────────────────────────────")
DOCTOR_ACCOUNTS = [
    ("draaditya@aadityaa.com",   "Doctor@123", "Dr. Aaditya Varma",   "Dr. Aaditya Varma"),
    ("drvikram@aadityaa.com",    "Doctor@123", "Dr. Vikram Sharma",   "Dr. Vikram Sharma"),
    ("drmeera@aadityaa.com",     "Doctor@123", "Dr. Meera Reddy",     "Dr. Meera Reddy"),
    ("drsameer@aadityaa.com",    "Doctor@123", "Dr. Sameer Khan",     "Dr. Sameer Khan"),
    ("drrohan@aadityaa.com",     "Doctor@123", "Dr. Rohan Das",       "Dr. Rohan Das"),
    ("drananya@aadityaa.com",    "Doctor@123", "Dr. Ananya Iyer",     "Dr. Ananya Iyer"),
    ("drshalini@aadityaa.com",   "Doctor@123", "Dr. Shalini Gupta",   "Dr. Shalini Gupta"),
    ("drvmalhotra@aadityaa.com", "Doctor@123", "Dr. Vikram Malhotra", "Dr. Vikram Malhotra"),
]

for email, password, full_name, db_name in DOCTOR_ACCOUNTS:
    uid = create_user(email, password, full_name, "doctor")
    if uid:
        link_doctor(uid, db_name)

# ─────────────────────────────────────────────────────────────────────────────
# Test Patients
# ─────────────────────────────────────────────────────────────────────────────
print("\n── Test Patients ────────────────────────────────────────────────────")
create_user("patient1@test.com", "Patient@123", "Rahul Sharma",  "patient", "+91 98765 43210")
create_user("patient2@test.com", "Patient@123", "Priya Nair",   "patient", "+91 87654 32109")
create_user("patient3@test.com", "Patient@123", "Arjun Reddy",  "patient", "+91 76543 21098")

# ─────────────────────────────────────────────────────────────────────────────
print("""
─────────────────────────────────────────────────────
✓  Test accounts ready. Login credentials:

  ADMIN
    Email:    admin@aadityaa.com
    Password: Admin@123
    URL:      http://localhost:8080/admin-dashboard.html

  DOCTOR (example)
    Email:    draaditya@aadityaa.com
    Password: Doctor@123
    URL:      http://localhost:8080/doctor-dashboard.html

  PATIENT (example)
    Email:    patient1@test.com
    Password: Patient@123
    URL:      http://localhost:8080/patient-dashboard.html

  Full list in this script's header comment.
─────────────────────────────────────────────────────
""")
