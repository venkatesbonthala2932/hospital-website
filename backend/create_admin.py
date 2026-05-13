"""
create_admin.py — Bootstrap the first admin

Run once when there's no admin in the system yet:
    cd backend && source venv/bin/activate && python create_admin.py

Two onboarding modes:
  1. Google sign-in only (no password needed)
     → pre-authorises the email, then the user just clicks
       "Continue with Google" on /login.html and becomes admin automatically.
  2. Email + password
     → creates a Firebase account on the spot.

Requires:
  - public.admin_invitations table (run admin_invitations_schema.sql once)
  - public.profiles table (created by supabase_schema.sql)
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from config import Config; Config.validate()
from services.supabase_client import get_admin_supabase
from services.firebase_service import (
    create_firebase_user, set_user_role, _init_firebase,
)
import firebase_admin
from firebase_admin import auth as firebase_auth


def prompt_email() -> str:
    email = input("Admin email   : ").strip().lower()
    if "@" not in email:
        print("✗ That doesn't look like an email.")
        sys.exit(1)
    return email


def google_mode(email: str):
    """Pre-authorise the email — they sign in with Google later."""
    db = get_admin_supabase()

    # If a Firebase account already exists (e.g. they already signed in once
    # as a patient), promote it now and bypass the invitation step.
    _init_firebase()
    try:
        fb_user = firebase_auth.get_user_by_email(email)
        uid     = fb_user.uid
        print(f"\n· Firebase account already exists for {email} (uid {uid[:8]}…)")

        existing = db.table("profiles").select("id, role").eq("id", uid).execute()
        if existing.data:
            db.table("profiles").update({"role": "admin"}).eq("id", uid).execute()
        else:
            db.table("profiles").upsert({
                "id":        uid,
                "email":     email,
                "full_name": fb_user.display_name or email.split("@")[0],
                "role":      "admin",
            }, on_conflict="id").execute()

        set_user_role(uid, "admin")
        print(f"\n✓ {email} is now an admin (existing account promoted).")
        print(f"  IMPORTANT: this user must sign out + sign back in once for their")
        print(f"  Firebase token to refresh and pick up the admin role.\n")
        return

    except firebase_auth.UserNotFoundError:
        pass  # Email never signed in — proceed to invitation
    except Exception as e:
        print(f"\n[warn] Could not look up existing Firebase user: {e}")

    # No Firebase user yet — drop an admin_invitations row.
    # The next time this email signs in (Google or email/password), auth_service
    # automatically promotes them.
    try:
        db.table("admin_invitations").upsert({
            "email":      email,
            "invited_by": None,
            "accepted_at": None,
        }, on_conflict="email").execute()
    except Exception as e:
        if "admin_invitations" in str(e):
            print(f"\n✗ The admin_invitations table doesn't exist yet.")
            print(f"  Run backend/admin_invitations_schema.sql in Supabase SQL Editor first.\n")
        else:
            print(f"\n✗ Could not create invitation: {e}\n")
        sys.exit(1)

    print(f"\n✓ {email} is pre-authorised as admin.")
    print(f"  Next steps for that user:")
    print(f"    1. Go to http://localhost:8080/login.html")
    print(f"    2. Click  'Continue with Google'  and choose this Gmail account")
    print(f"    3. They'll land on the admin dashboard automatically.\n")


def password_mode(email: str):
    """Create a Firebase account with email + password, set role=admin."""
    password = input("Admin password: ").strip()
    name     = input("Display name  : ").strip() or "Admin"
    if len(password) < 6:
        print("\n✗ Password must be at least 6 characters.\n")
        sys.exit(1)

    db = get_admin_supabase()
    existing = db.table("profiles").select("id, role").eq("email", email).execute()

    if existing.data:
        uid = existing.data[0]["id"]
        db.table("profiles").update({"role": "admin", "full_name": name}).eq("id", uid).execute()
        try: set_user_role(uid, "admin")
        except Exception: pass
        print(f"\n✓ Existing account '{email}' promoted to admin.")
    else:
        try:
            fb = create_firebase_user(email=email, password=password, display_name=name)
            uid = fb["uid"]
        except ValueError as e:
            print(f"\n✗ Firebase error: {e}\n"); sys.exit(1)

        db.table("profiles").upsert({
            "id": uid, "email": email, "full_name": name, "role": "admin",
        }, on_conflict="id").execute()
        try: set_user_role(uid, "admin")
        except Exception: pass

        print(f"\n✓ Admin account created!")
        print(f"  Email   : {email}")
        print(f"  Password: {password}")
    print(f"  Log in at http://localhost:8080/login.html\n")


def main():
    print("\n=== Aadityaa Hospital — Bootstrap First Admin ===\n")
    print("How will this admin sign in?")
    print("  1. Continue with Google  (no password, recommended)")
    print("  2. Email + password")
    choice = input("\nChoice [1/2]: ").strip() or "1"

    email = prompt_email()

    if choice == "1":
        google_mode(email)
    elif choice == "2":
        password_mode(email)
    else:
        print("\n✗ Invalid choice. Pick 1 or 2.\n"); sys.exit(1)


if __name__ == "__main__":
    main()
