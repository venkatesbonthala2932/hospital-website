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

    # Get existing profile (use .execute() not .single() — .single() crashes
    # with PGRST116 if 0 rows are returned, which makes every protected
    # request return 500 for brand-new users).
    try:
        result = db.table("profiles").select("role, full_name") \
            .eq("id", uid).execute()
    except Exception as e:
        print(f"[warn] profile lookup failed for {uid}: {e}")
        result = type("_", (), {"data": []})()

    if result.data:
        role = result.data[0].get("role", "patient")
    else:
        # First time this user hits a protected route — auto-create their profile
        role = "patient"
        db.table("profiles").insert({
            "id":        uid,
            "email":     email,
            "full_name": name or email.split("@")[0],
            "role":      role,
        }).execute()

    # If they're still 'patient' but have a pending doctor invitation, promote.
    # This is what makes "Continue with Google" work for invited doctors —
    # no extra UI step needed.
    if role == "patient" and email:
        role = _maybe_accept_invitation(db, email, uid, name) or role

    user = {"id": uid, "email": email, "name": name}
    return user, role


def _maybe_accept_invitation(db, email: str, uid: str, display_name: str) -> str | None:
    """
    Check for a pending doctor OR admin invitation for this email and
    auto-promote the user on first sign-in.

    Admin invitations take precedence over doctor invitations
    (if both somehow exist).

    Returns 'admin' | 'doctor' | None. Best-effort — never raises.
    """
    email = (email or "").lower()
    if not email:
        return None

    # ── Admin invitation first ────────────────────────────────────────────────
    try:
        adm = db.table("admin_invitations") \
            .select("email, accepted_at") \
            .eq("email", email).execute()
        if adm.data and not adm.data[0].get("accepted_at"):
            db.table("profiles").update({
                "role": "admin",
                "full_name": display_name or email.split("@")[0],
            }).eq("id", uid).execute()
            try:
                from services.firebase_service import set_user_role
                set_user_role(uid, "admin")
            except Exception as e:
                print(f"[warn] could not set admin claim for {uid}: {e}")
            db.table("admin_invitations").update({"accepted_at": "now()"}) \
                .eq("email", email).execute()
            return "admin"
    except Exception as e:
        print(f"[warn] admin invitation check failed for {email}: {e}")

    # ── Doctor invitation ─────────────────────────────────────────────────────
    try:
        doc = db.table("doctor_invitations") \
            .select("email, doctor_id, accepted_at") \
            .eq("email", email).execute()
        if not doc.data or doc.data[0].get("accepted_at"):
            return None

        doctor_id = doc.data[0]["doctor_id"]
        db.table("doctors").update({"user_id": uid}).eq("id", doctor_id).execute()
        db.table("profiles").update({
            "role": "doctor",
            "full_name": display_name or email.split("@")[0],
        }).eq("id", uid).execute()
        try:
            from services.firebase_service import set_user_role
            set_user_role(uid, "doctor")
        except Exception as e:
            print(f"[warn] could not set doctor claim for {uid}: {e}")
        db.table("doctor_invitations").update({"accepted_at": "now()"}) \
            .eq("email", email).execute()
        return "doctor"
    except Exception as e:
        print(f"[warn] doctor invitation check failed for {email}: {e}")
        return None


def get_doctor_record(firebase_uid: str) -> dict | None:
    """Return the doctors table row for a doctor-role user, or None."""
    try:
        db = get_admin_supabase()
        result = db.table("doctors").select("*") \
            .eq("user_id", firebase_uid).single().execute()
        return result.data
    except Exception:
        return None
