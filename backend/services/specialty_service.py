"""
Read-only operations for specialties.
All functions use the admin client so they work without a user JWT.
"""
from services.supabase_client import get_admin_supabase


def get_all_specialties() -> list[dict]:
    db = get_admin_supabase()
    result = (
        db.table("specialties")
        .select("id, name, slug, description, icon, conditions, treatments")
        .eq("is_active", True)
        .order("name")
        .execute()
    )
    return result.data or []


def get_specialty_by_slug(slug: str) -> dict | None:
    db = get_admin_supabase()
    result = (
        db.table("specialties")
        .select("*")
        .eq("slug", slug)
        .eq("is_active", True)
        .single()
        .execute()
    )
    return result.data


def get_doctors_for_specialty(specialty_id: str) -> list[dict]:
    """Return all active doctors belonging to a specialty."""
    db = get_admin_supabase()
    result = (
        db.table("doctors")
        .select(
            "id, full_name, title, qualifications, experience_years, "
            "bio, photo_url, consultation_fee, is_available"
        )
        .eq("specialty_id", specialty_id)
        .eq("is_active", True)
        .order("full_name")
        .execute()
    )
    return result.data or []
