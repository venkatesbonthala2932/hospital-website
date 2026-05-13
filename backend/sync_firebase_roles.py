"""
sync_firebase_roles.py — One-time backfill

Walks every Supabase profile and copies its role into the user's Firebase
custom claims. Run once after deploying the RBAC change:

    cd backend && source venv/bin/activate && python sync_firebase_roles.py

Safe to re-run. Idempotent.
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from config import Config; Config.validate()
from services.supabase_client import get_admin_supabase
from services.firebase_service import set_user_role

db = get_admin_supabase()
profiles = db.table("profiles").select("id, email, role").execute().data or []

print(f"Syncing {len(profiles)} profile(s) to Firebase custom claims…\n")
ok = err = 0
for p in profiles:
    role = (p.get("role") or "patient").lower()
    try:
        set_user_role(p["id"], role)
        print(f"  ✓ {p['email']:35}  → {role}")
        ok += 1
    except Exception as e:
        print(f"  ✗ {p['email']:35}  ERROR: {e}")
        err += 1

print(f"\nDone. {ok} synced, {err} failed.")
print("Users must sign out + sign in once for the new claims to appear in their JWT.")
