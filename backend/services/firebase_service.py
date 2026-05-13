"""
services/firebase_service.py — Firebase Admin SDK

WHY FIREBASE FOR AUTH:
  Firebase handles the hard parts of authentication:
  - Secure password hashing
  - Google OAuth flow (popup or redirect)
  - Token refresh automatically in the browser
  - Token expiry (1 hour), refresh tokens (unlimited)

HOW IT CONNECTS TO THE REST OF THE APP:
  1. Frontend uses Firebase JS SDK to log in (email OR Google)
  2. Frontend calls  user.getIdToken()  to get a short-lived JWT
  3. Frontend sends that JWT in every API request:
       Authorization: Bearer <firebase_id_token>
  4. Flask calls  verify_firebase_token(token)  here
  5. If valid, we get back the user's Firebase UID + email + name
  6. We use that UID to look up / create their row in Supabase profiles table

WHY NOT SUPABASE FOR AUTH:
  Supabase Auth works, but adding Google OAuth to it requires
  configuring Google Cloud Console + Supabase OAuth settings.
  Firebase makes Google sign-in a 3-line change in the frontend.
"""
import json
import firebase_admin
from firebase_admin import credentials, auth as firebase_auth
from config import Config

_initialized = False


def _init_firebase():
    """Initialize Firebase Admin SDK once at first use."""
    global _initialized
    if _initialized:
        return

    try:
        cred_json = Config.FIREBASE_SERVICE_ACCOUNT_JSON
        if not cred_json or cred_json == "paste-your-firebase-service-account-json-here":
            raise RuntimeError(
                "FIREBASE_SERVICE_ACCOUNT_JSON is not set in .env\n"
                "Go to: Firebase Console → Project Settings → Service Accounts "
                "→ Generate new private key → copy the JSON content"
            )

        cred_dict = json.loads(cred_json)
        cred = credentials.Certificate(cred_dict)

        if not firebase_admin._apps:
            firebase_admin.initialize_app(cred)

        _initialized = True
    except json.JSONDecodeError:
        raise RuntimeError(
            "FIREBASE_SERVICE_ACCOUNT_JSON is not valid JSON. "
            "Make sure you pasted the entire service account file as one line."
        )


def verify_firebase_token(id_token: str) -> dict | None:
    """
    Verify a Firebase ID token and return the decoded payload.

    Called by  auth_service.get_current_user()  on every protected request.

    Returns a dict with at minimum:
        uid   — Firebase user ID (string, e.g. "abc123XYZ")
        email — user's email address
        name  — display name (may be empty for email registrations)

    Returns None if the token is invalid, expired, or revoked.
    """
    _init_firebase()
    try:
        decoded = firebase_auth.verify_id_token(id_token)
        return decoded
    except firebase_admin.exceptions.FirebaseError:
        return None
    except Exception:
        return None


def create_firebase_user(email: str, password: str, display_name: str = "") -> dict:
    """
    Create a Firebase user account via Admin SDK.
    Used by POST /api/auth/register so the server creates the account.

    Returns the created Firebase user record as a dict.
    Raises ValueError if the email is already in use.
    """
    _init_firebase()
    try:
        user = firebase_auth.create_user(
            email=email,
            password=password,
            display_name=display_name or email.split("@")[0],
        )
        return {"uid": user.uid, "email": user.email, "name": user.display_name}
    except firebase_auth.EmailAlreadyExistsError:
        raise ValueError("An account with this email already exists.")
    except firebase_admin.exceptions.FirebaseError as e:
        raise ValueError(f"Could not create account: {e}")


def update_firebase_user(uid: str, email: str | None = None, display_name: str | None = None) -> dict:
    """
    Update a Firebase user's email or display name via Admin SDK.
    Used when admin edits a doctor profile.
    """
    _init_firebase()
    kwargs = {}
    if email:
        kwargs["email"] = email
    if display_name:
        kwargs["display_name"] = display_name
    if not kwargs:
        return {}
    try:
        user = firebase_auth.update_user(uid, **kwargs)
        return {"uid": user.uid, "email": user.email, "name": user.display_name}
    except firebase_auth.EmailAlreadyExistsError:
        raise ValueError("That email is already used by another account.")
    except firebase_admin.exceptions.FirebaseError as e:
        raise ValueError(f"Could not update account: {e}")


def revoke_firebase_tokens(uid: str):
    """
    Revoke all refresh tokens for a user (force logout everywhere).
    Called by POST /api/auth/logout.
    """
    _init_firebase()
    try:
        firebase_auth.revoke_refresh_tokens(uid)
    except Exception:
        pass  # Best-effort; frontend should clear localStorage regardless


def set_user_role(uid: str, role: str):
    """
    Write the user's role into a Firebase custom claim so every
    ID token issued from now on carries it. The frontend can then read
    it via idTokenResult.claims.role without a server roundtrip.

    Supabase profiles.role remains the source of truth — this is a
    fast-path cache for the frontend + JWT verification.

    Note: existing tokens keep the OLD claim until they refresh
    (Firebase ID tokens have a 1-hour TTL).
    """
    _init_firebase()
    role = (role or "patient").lower()
    if role not in ("patient", "doctor", "admin"):
        raise ValueError(f"Unknown role: {role}")
    try:
        firebase_auth.set_custom_user_claims(uid, {"role": role})
    except firebase_admin.exceptions.FirebaseError as e:
        raise ValueError(f"Could not set role claim: {e}")
