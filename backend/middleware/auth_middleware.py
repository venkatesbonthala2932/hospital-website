"""
middleware/auth_middleware.py — Role-Based Access Control (RBAC)

ROLE HIERARCHY (Aadityaa Hospital):
    admin   (3)  — full access, can do everything a doctor & patient can
    doctor  (2)  — manages own schedule, sees own patients
    patient (1)  — books appointments, sees own records

Decorators:
    @require_auth                     → any signed-in user
    @require_role('admin')            → STRICT: only admins (no inheritance)
    @require_role('doctor', 'admin')  → STRICT: doctor OR admin
    @require_min_role('doctor')       → HIERARCHY: doctor + everyone above (admin)
    @require_min_role('patient')      → HIERARCHY: anyone signed in (patient/doctor/admin)
    @optional_auth                    → doesn't block; passes None when unauthenticated

The decorated function receives:
    current_user  — dict with .id / ['id'], .email
    current_role  — 'patient' | 'doctor' | 'admin'

Example:
    @bp.route('/profile')
    @require_min_role('patient')
    def profile(current_user, current_role):
        ...  # admin, doctor, patient all allowed
"""
from functools import wraps
from flask import jsonify
from services.auth_service import get_current_user

# Role → numeric level. Higher number = more privileges.
# Admins inherit doctor + patient capabilities; doctors inherit patient.
ROLE_LEVEL = {
    "patient": 1,
    "doctor":  2,
    "admin":   3,
}


def role_level(role: str) -> int:
    """Return the privilege level for a role, or 0 if unknown."""
    return ROLE_LEVEL.get((role or "").lower(), 0)


def has_min_role(user_role: str, required_role: str) -> bool:
    """True if user_role is at or above required_role in the hierarchy."""
    return role_level(user_role) >= role_level(required_role)


def require_auth(f):
    """Allows any authenticated user regardless of role."""
    @wraps(f)
    def decorated(*args, **kwargs):
        user, role = get_current_user()
        if not user:
            return jsonify({"error": "Authentication required. Please log in."}), 401
        return f(*args, **kwargs, current_user=user, current_role=role)
    return decorated


def require_role(*allowed_roles: str):
    """
    STRICT role check — user's role must be one of the listed roles exactly.
    No inheritance. Use when a route is for one specific role only
    (e.g. doctor-only routes shouldn't be exposed to patients).
    """
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            user, role = get_current_user()
            if not user:
                return jsonify({"error": "Authentication required. Please log in."}), 401
            if role not in allowed_roles:
                return jsonify({
                    "error":  "Access denied.",
                    "detail": f"This resource requires one of: {', '.join(allowed_roles)}.",
                }), 403
            return f(*args, **kwargs, current_user=user, current_role=role)
        return decorated
    return decorator


def require_min_role(min_role: str):
    """
    HIERARCHICAL role check — user must have at least `min_role`.
    Admins inherit doctor + patient access; doctors inherit patient access.

        @require_min_role('patient')  → any signed-in user
        @require_min_role('doctor')   → doctor OR admin
        @require_min_role('admin')    → admin only
    """
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            user, role = get_current_user()
            if not user:
                return jsonify({"error": "Authentication required. Please log in."}), 401
            if not has_min_role(role, min_role):
                return jsonify({
                    "error":  "Access denied.",
                    "detail": f"This resource requires '{min_role}' role or higher.",
                }), 403
            return f(*args, **kwargs, current_user=user, current_role=role)
        return decorated
    return decorator


def optional_auth(f):
    """
    Does NOT block unauthenticated requests.
    Injects (current_user=None, current_role=None) when not logged in.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        user, role = get_current_user()
        return f(*args, **kwargs, current_user=user, current_role=role)
    return decorated
