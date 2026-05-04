"""
Read operations for doctor listings.
"""
from services.supabase_client import get_admin_supabase


def get_all_doctors(specialty_slug: str | None = None) -> list[dict]:
    """
    Return all active doctors, optionally filtered by specialty slug.
    Each doctor row includes specialty name for display.
    """
    db = get_admin_supabase()

    query = (
        db.table("doctors")
        .select(
            "id, full_name, title, qualifications, experience_years, "
            "bio, photo_url, consultation_fee, is_available, "
            "specialties(id, name, slug)"
        )
        .eq("is_active", True)
        .order("full_name")
    )

    if specialty_slug:
        # First resolve slug → specialty id
        spec_result = (
            db.table("specialties")
            .select("id")
            .eq("slug", specialty_slug)
            .single()
            .execute()
        )
        if spec_result.data:
            query = query.eq("specialty_id", spec_result.data["id"])

    result = query.execute()
    return result.data or []


def get_doctor_by_id(doctor_id: str) -> dict | None:
    db = get_admin_supabase()
    result = (
        db.table("doctors")
        .select(
            "id, full_name, title, qualifications, experience_years, "
            "bio, photo_url, consultation_fee, is_available, "
            "specialties(id, name, slug)"
        )
        .eq("id", doctor_id)
        .eq("is_active", True)
        .single()
        .execute()
    )
    return result.data


def get_doctor_available_days(doctor_id: str) -> list[int]:
    """Return list of weekday integers (0=Mon … 6=Sun) when doctor is scheduled."""
    db = get_admin_supabase()
    result = (
        db.table("doctor_availability")
        .select("day_of_week")
        .eq("doctor_id", doctor_id)
        .eq("is_active", True)
        .execute()
    )
    return [row["day_of_week"] for row in (result.data or [])]
