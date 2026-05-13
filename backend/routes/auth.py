"""
routes/auth.py — Authentication

POST /api/auth/register          create account (server creates Firebase user + Supabase profile)
POST /api/auth/login             verify Firebase token, return role
GET  /api/auth/google            frontend gets the Firebase config to start Google login
GET  /api/auth/google/callback   not used server-side with Firebase (frontend handles redirect)
POST /api/auth/logout            revoke Firebase tokens
GET  /api/auth/me                return current user profile + role

─── HOW GOOGLE LOGIN WORKS WITH FIREBASE ────────────────────────────────────
  1. Frontend calls:  signInWithPopup(auth, new GoogleAuthProvider())
  2. Firebase shows Google popup — user picks their account
  3. Firebase returns a session, frontend calls  user.getIdToken()
  4. Frontend sends POST /api/auth/login  { id_token: "eyJ..." }
  5. Flask verifies token → looks up / creates Supabase profile → returns role

  No callback URL needed — the entire OAuth dance happens inside the popup.
  That is why Firebase Google login is much simpler than raw OAuth.

─── HOW EMAIL/PASSWORD WORKS ────────────────────────────────────────────────
  Register:
    Frontend calls POST /api/auth/register { email, password, full_name }
    Flask creates Firebase user via Admin SDK + creates Supabase profile
    Returns a custom token the frontend can exchange for an ID token

  Login:
    Frontend calls  signInWithEmailAndPassword(auth, email, password)
    Firebase returns session → frontend calls  user.getIdToken()
    Frontend sends POST /api/auth/login { id_token: "..." }
    Flask verifies + returns role
"""
from flask import Blueprint, jsonify, request
from services.firebase_service import (
    create_firebase_user,
    revoke_firebase_tokens,
    verify_firebase_token,
)
from services.supabase_client import get_admin_supabase
from services.auth_service import get_current_user
from middleware.auth_middleware import require_auth

bp = Blueprint("auth", __name__)


# ── POST /api/auth/register ───────────────────────────────────────────────────
@bp.route("/register", methods=["POST"])
def register():
    """
    Create a new patient account.

    Body: { "email": "...", "password": "...", "full_name": "...", "phone": "..." }

    WHY server-side registration (not just Firebase JS SDK on frontend):
    - We can enforce our own password rules and field validation
    - We immediately create the Supabase profile in the same call
    - We control the role (always 'patient' for self-registration)
    - Consistent error messages from one place
    """
    data      = request.get_json(silent=True) or {}
    email     = data.get("email", "").strip().lower()
    password  = data.get("password", "").strip()
    full_name = data.get("full_name", "").strip()
    phone     = data.get("phone", "").strip()

    if not email or not password:
        return jsonify({"error": "email and password are required."}), 400
    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters."}), 400

    try:
        # Step 1: Create the user in Firebase
        firebase_user = create_firebase_user(email, password, full_name)
        uid = firebase_user["uid"]

        # Step 2: Create their profile in Supabase
        db = get_admin_supabase()
        db.table("profiles").insert({
            "id":        uid,
            "email":     email,
            "full_name": full_name or email.split("@")[0],
            "phone":     phone,
            "role":      "patient",
        }).execute()

        # Step 3: Mirror the role into Firebase custom claims so the JWT carries it
        try:
            from services.firebase_service import set_user_role
            set_user_role(uid, "patient")
        except Exception as e:
            print(f"[warn] Could not set initial role claim for {uid}: {e}")

        return jsonify({
            "message":   "Account created. Please log in with your email and password.",
            "user_id":   uid,
            "email":     email,
            "role":      "patient",
        }), 201

    except ValueError as e:
        return jsonify({"error": str(e)}), 409
    except Exception as e:
        return jsonify({"error": "Registration failed.", "detail": str(e)}), 400


# ── POST /api/auth/login ──────────────────────────────────────────────────────
@bp.route("/login", methods=["POST"])
def login():
    """
    Verify a Firebase ID token and return the user's role + profile.

    Frontend flow BEFORE calling this:
      const cred = await signInWithEmailAndPassword(auth, email, password)
      const idToken = await cred.user.getIdToken()
      POST /api/auth/login  { id_token: idToken }

    WHY this route exists even though Firebase already logged them in:
    Firebase doesn't know about roles (patient/doctor/admin) — that's in
    Supabase. The frontend needs the role immediately after login to know
    which dashboard to redirect to.
    """
    data     = request.get_json(silent=True) or {}
    id_token = data.get("id_token", "").strip()

    # Also accept token from Authorization: Bearer <token> header
    if not id_token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            id_token = auth_header[7:].strip()

    if not id_token:
        return jsonify({"error": "id_token is required."}), 400

    decoded = verify_firebase_token(id_token)
    if not decoded:
        return jsonify({"error": "Invalid or expired token."}), 401

    uid   = decoded["uid"]
    email = decoded.get("email", "")

    db = get_admin_supabase()
    # Use .execute() not .single() — .single() raises an exception when
    # 0 rows are returned, which is the normal case for first-time Google
    # sign-in (no profile yet).
    profile = db.table("profiles").select("role, full_name, phone") \
        .eq("id", uid).execute()

    if profile.data:
        row       = profile.data[0]
        role      = row.get("role", "patient")
        full_name = row.get("full_name", "")
        phone     = row.get("phone", "")
    else:
        # Google login — user may not have a profile yet, create it
        role      = "patient"
        full_name = decoded.get("name", email.split("@")[0])
        db.table("profiles").insert({
            "id": uid, "email": email,
            "full_name": full_name, "role": role,
        }).execute()
        phone = ""

    # Auto-promote if a doctor invitation is pending for this email
    if role == "patient" and email:
        from services.auth_service import _maybe_accept_invitation
        promoted = _maybe_accept_invitation(db, email, uid, full_name)
        if promoted == "doctor":
            role = "doctor"

    # For doctors: also return their doctor_id so the dashboard loads in one call
    extra = {}
    if role == "doctor":
        doc = db.table("doctors").select("id, full_name, title") \
            .eq("user_id", uid).execute()
        if doc.data:
            extra["doctor"] = doc.data[0]

    return jsonify({
        "message":   "Login successful.",
        "role":      role,
        "user": {
            "id":        uid,
            "email":     email,
            "full_name": full_name,
            "phone":     phone,
            "role":      role,
            **extra,
        }
    })


# ── GET /api/auth/google ──────────────────────────────────────────────────────
@bp.route("/google", methods=["GET"])
def google_info():
    """
    Returns the Firebase project config the frontend needs to initialise
    Firebase and start the Google sign-in popup.

    WHY: Instead of hardcoding Firebase config in every HTML file, the
    frontend can fetch it once from here and cache it. This also means
    you only update one place (the .env) when the project changes.

    NOTE: These values are safe to expose — they are public identifiers,
    not secrets. The actual security is Firebase's server-side token validation.
    """
    from config import Config
    try:
        import json
        sa = json.loads(Config.FIREBASE_SERVICE_ACCOUNT_JSON)
        project_id = sa.get("project_id", "")
    except Exception:
        project_id = ""

    return jsonify({
        "message":    "Use Firebase JS SDK on the frontend for Google login.",
        "project_id": project_id,
        "instructions": [
            "1. Add Firebase JS SDK to your HTML page",
            "2. Call signInWithPopup(auth, new GoogleAuthProvider())",
            "3. Get the token: await user.getIdToken()",
            "4. Send POST /api/auth/login  { id_token: '<token>' }",
        ]
    })


# ── GET /api/auth/google/callback ─────────────────────────────────────────────
@bp.route("/google/callback", methods=["GET"])
def google_callback():
    """
    Not used with Firebase (Firebase handles the callback internally in the popup).
    Kept for API completeness — returns a helpful explanation.
    """
    return jsonify({
        "message": "Google OAuth callback is handled by Firebase JS SDK on the frontend. "
                   "No server callback needed."
    })


# ── POST /api/auth/logout ─────────────────────────────────────────────────────
@bp.route("/logout", methods=["POST"])
@require_auth
def logout(current_user, current_role):
    """
    Revoke the user's Firebase refresh tokens.

    WHY server-side logout matters:
    Firebase ID tokens are valid for 1 hour even after the frontend
    deletes them from localStorage. By revoking refresh tokens, we ensure
    the user cannot get a new ID token after logout.

    The frontend should ALSO call  firebase.auth().signOut()  to clear
    the local session immediately.
    """
    revoke_firebase_tokens(current_user["id"])
    return jsonify({"message": "Logged out successfully."})


# ── GET /api/auth/me ──────────────────────────────────────────────────────────
@bp.route("/me", methods=["GET"])
@require_auth
def me(current_user, current_role):
    """
    Return full profile of the currently logged-in user.

    Frontend calls this on every page load to check if still logged in
    and to get the role for conditional navigation (Show/hide dashboards).

    Returns doctor record too if role = 'doctor'.
    """
    db  = get_admin_supabase()
    row = db.table("profiles").select("*").eq("id", current_user["id"]).single().execute()

    result = {
        "id":         current_user["id"],
        "email":      current_user["email"],
        "role":       current_role,
        "full_name":  row.data.get("full_name", "") if row.data else "",
        "phone":      row.data.get("phone", "")     if row.data else "",
        "created_at": row.data.get("created_at", "") if row.data else "",
    }

    if current_role == "doctor":
        doc = db.table("doctors") \
            .select("id, full_name, title, photo_url, specialties(name, slug)") \
            .eq("user_id", current_user["id"]).single().execute()
        result["doctor"] = doc.data

    return jsonify({"user": result})
