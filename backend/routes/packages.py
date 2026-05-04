"""
routes/packages.py — Health packages (public, no auth required)

GET /api/packages               list all active packages
GET /api/packages/:slug         single package detail
"""
from flask import Blueprint, jsonify, request
from services.supabase_client import get_admin_supabase

bp = Blueprint("packages", __name__)


@bp.route("", methods=["GET"])
def list_packages():
    db     = get_admin_supabase()
    target = request.args.get("target", "").strip()

    query = db.table("health_packages") \
        .select("id, name, slug, tagline, description, price, original_price, "
                "target_group, tests, duration, icon, sort_order") \
        .eq("is_active", True) \
        .order("sort_order")

    if target:
        query = query.eq("target_group", target)

    result = query.execute()
    return jsonify({"packages": result.data or [], "count": len(result.data or [])})


@bp.route("/<slug>", methods=["GET"])
def package_detail(slug: str):
    db     = get_admin_supabase()
    result = db.table("health_packages").select("*") \
        .eq("slug", slug).eq("is_active", True).single().execute()

    if not result.data:
        return jsonify({"error": "Package not found."}), 404

    return jsonify({"package": result.data})
