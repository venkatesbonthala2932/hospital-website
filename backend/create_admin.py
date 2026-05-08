"""
create_admin.py — Run once to create or promote an admin account.

Usage (from the backend/ directory with venv activated):
    python create_admin.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from config import Config
Config.validate()

from services.supabase_client import get_admin_supabase
from services.firebase_service import create_firebase_user, _init_firebase
import firebase_admin
from firebase_admin import auth as firebase_auth

print("\n=== Aadityaa Hospital — Create Admin Account ===\n")

email    = input("Admin email   : ").strip().lower()
password = input("Admin password: ").strip()
name     = input("Display name  : ").strip() or "Admin"

db = get_admin_supabase()

# Check if a profile already exists for this email
existing = db.table("profiles").select("id, role").eq("email", email).execute()

if existing.data:
    # User already registered — just promote to admin
    uid = existing.data[0]["id"]
    db.table("profiles").update({"role": "admin", "full_name": name}).eq("id", uid).execute()
    print(f"\n✓ Existing account '{email}' promoted to admin.")
    print(f"  Log in at http://localhost:8080/login.html\n")
else:
    # Create Firebase account first
    try:
        fb = create_firebase_user(email=email, password=password, display_name=name)
        uid = fb["uid"]
    except ValueError as e:
        print(f"\n✗ Firebase error: {e}\n")
        sys.exit(1)

    # Create Supabase profile with admin role
    db.table("profiles").upsert({
        "id":        uid,
        "email":     email,
        "full_name": name,
        "role":      "admin",
    }, on_conflict="id").execute()

    print(f"\n✓ Admin account created!")
    print(f"  Email   : {email}")
    print(f"  Password: {password}")
    print(f"  Log in at http://localhost:8080/login.html\n")
