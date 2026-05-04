"""
Role-based access control decorators for Flask routes.

Usage:
    @require_auth                → any logged-in user
    @require_role('patient')     → only patients
    @require_role('doctor')      → only doctors
    @require_role('admin')       → only admins
    @require_role('doctor', 'admin')  → doctors OR admins

The decorated function receives two extra kwargs injected by the decorator:
    current_user  — supabase auth User object  (has .id, .email)
    current_role  — string: 'patient' | 'doctor' | 'admin'

Example:
    @bp.route('/my-appointments')
    @require_role('patient')
    def my_appointments(current_user, current_role):
        ...
"""
from functools import wraps
from flask import jsonify
from services.auth_service import get_current_user


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
    """Restricts access to specific roles only."""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            user, role = get_current_user()
            if not user:
                return jsonify({"error": "Authentication required. Please log in."}), 401
            if role not in allowed_roles:
                return jsonify({
                    "error": "Access denied.",
                    "detail": f"This resource requires one of these roles: {', '.join(allowed_roles)}."
                }), 403
            return f(*args, **kwargs, current_user=user, current_role=role)
        return decorated
    return decorator


def optional_auth(f):
    """
    Does NOT block unauthenticated requests.
    Injects (current_user=None, current_role=None) when not logged in.
    Useful for public pages that behave slightly differently when logged in.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        user, role = get_current_user()
        return f(*args, **kwargs, current_user=user, current_role=role)
    return decorated
