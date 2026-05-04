"""
services/auth_service.py — Token validation + user resolution

FLOW FOR EVERY PROTECTED REQUEST:
  1. Browser sends:  Authorization: Bearer <firebase_id_token>
  2. get_current_user() extracts the token from the header
  3. Calls firebase_service.verify_firebase_token(token)
  4. Gets back Firebase UID + email
  5. Looks up the user's row in Supabase profiles table
  6. Returns (user_dict, role_string) to the middleware decorator
  7. Middleware injects current_user + current_role into the route function

WHY WE STORE PROFILES IN SUPABASE (not just Firebase):
  Firebase only stores UID, email, name, photo.
  Our app needs: role (patient/doctor/admin), phone, created_at.
  Supabase is the source of truth for roles and app-specific data.
"""
from flask import request
from services.firebase_service import verify_firebase_token
from services.supabase_client import get_admin_supabase


def get_bearer_token() -> str | None:
    header = request.headers.get("Authorization", "")
    if header.startswith("Bearer "):
        return header.split(" ", 1)[1].strip()
    return None


def get_current_user() -> tuple[dict | None, str | None]:
    """
    Validate the Bearer token and return (user, role).

    user  = { "id": firebase_uid, "email": "...", "name": "..." }
    role  = "patient" | "doctor" | "admin"

    Returns (None, None) if no token or token is invalid.
    """
    token = get_bearer_token()
    if not token:
        return None, None

    decoded = verify_firebase_token(token)
    if not decoded:
        return None, None

    uid   = decoded["uid"]
    email = decoded.get("email", "")
    name  = decoded.get("name", "") or decoded.get("display_name", "")

    db = get_admin_supabase()

    # Get existing profile
    result = db.table("profiles").select("role, full_name") \
        .eq("id", uid).single().execute()

    if result.data:
        role = result.data.get("role", "patient")
    else:
        # First time this user hits a protected route — auto-create their profile
        role = "patient"
        db.table("profiles").insert({
            "id":        uid,
            "email":     email,
            "full_name": name or email.split("@")[0],
            "role":      role,
        }).execute()

    user = {"id": uid, "email": email, "name": name}
    return user, role


def get_doctor_record(firebase_uid: str) -> dict | None:
    """Return the doctors table row for a doctor-role user, or None."""
    try:
        db = get_admin_supabase()
        result = db.table("doctors").select("*") \
            .eq("user_id", firebase_uid).single().execute()
        return result.data
    except Exception:
        return None
