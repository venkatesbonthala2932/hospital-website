"""
routes/public.py — Public browsing (no login required)

GET /api/specialties                    list all active specialties
GET /api/specialties/:id/doctors        doctors in a specialty (by UUID or slug)
GET /api/doctors                        all doctors  (?specialty=slug to filter)
GET /api/doctors/:id                    single doctor profile
GET /api/doctors/:id/slots?date=YYYY-MM-DD   available time slots

WHY NO AUTH:
  Patients browse doctors and specialties before deciding to book.
  Forcing login before browsing would drive users away.
  Auth is only asked when the patient clicks "Book Appointment".
"""
from datetime import date, timedelta
from flask import Blueprint, jsonify, request
from services.supabase_client import get_admin_supabase
from services.appointment_service import get_available_slots, get_available_dates
from services.doctor_service import get_doctor_available_days

bp = Blueprint("public", __name__)


# ── GET /api/server-time ──────────────────────────────────────────────────────
@bp.route("/server-time", methods=["GET"])
def server_time():
    """
    Returns the authoritative server date so the frontend can set min-date
    constraints using server time, not the client's (potentially spoofed) clock.
    """
    today    = date.today()
    tomorrow = today + timedelta(days=1)
    return jsonify({
        "today":    today.isoformat(),
        "tomorrow": tomorrow.isoformat(),
    })


# ── GET /api/site-settings ────────────────────────────────────────────────────
@bp.route("/site-settings", methods=["GET"])
def get_site_settings():
    """Return all site settings as a flat key→value dict. Public, no auth."""
    db = get_admin_supabase()
    result = db.table("site_settings").select("key, value").execute()
    settings = {row["key"]: row["value"] for row in (result.data or [])}
    return jsonify({"settings": settings})


# ── GET /api/specialties ──────────────────────────────────────────────────────
@bp.route("/specialties", methods=["GET"])
def list_specialties():
    """
    Return all active specialties.
    Used by: departments.html to render the specialties grid.
    """
    db = get_admin_supabase()
    result = db.table("specialties") \
        .select("id, name, slug, description, icon, conditions, treatments") \
        .eq("is_active", True).order("name").execute()

    return jsonify({"specialties": result.data or [], "count": len(result.data or [])})


# ── GET /api/specialties/:id/doctors ─────────────────────────────────────────
@bp.route("/specialties/<specialty_ref>/doctors", methods=["GET"])
def specialty_doctors(specialty_ref: str):
    """
    Return a specialty + all its doctors.
    specialty_ref can be either a UUID  or  a slug (e.g. 'cardiology').

    Used by: cardiology.html, neurology.html etc. to show specialty details
    and list the doctors under that specialty.

    WHY support both UUID and slug:
    The HTML pages link by slug (/api/specialties/cardiology/doctors).
    The appointments dropdown may reference by UUID.
    One route handles both.
    """
    db = get_admin_supabase()

    # Detect whether it looks like a UUID (contains hyphens, length 36)
    is_uuid = len(specialty_ref) == 36 and specialty_ref.count("-") == 4

    if is_uuid:
        spec = db.table("specialties").select("*") \
            .eq("id", specialty_ref).eq("is_active", True).single().execute()
    else:
        spec = db.table("specialties").select("*") \
            .eq("slug", specialty_ref).eq("is_active", True).single().execute()

    if not spec.data:
        return jsonify({"error": "Specialty not found."}), 404

    doctors = db.table("doctors") \
        .select("id, full_name, title, qualifications, experience_years, "
                "bio, photo_url, consultation_fee, is_available") \
        .eq("specialty_id", spec.data["id"]) \
        .eq("is_active", True).order("full_name").execute()

    return jsonify({
        "specialty": spec.data,
        "doctors":   doctors.data or [],
        "count":     len(doctors.data or []),
    })


# ── GET /api/doctors ──────────────────────────────────────────────────────────
@bp.route("/doctors", methods=["GET"])
def list_doctors():
    """
    Return all active doctors.
    Optional filter: ?specialty=cardiology  (uses slug)

    Used by: doctors.html to render all doctor cards.
    Includes specialty name + slug so the card can link to the right page.
    """
    db = get_admin_supabase()
    specialty_slug = request.args.get("specialty", "").strip()

    query = db.table("doctors") \
        .select("id, full_name, title, qualifications, experience_years, "
                "bio, photo_url, consultation_fee, is_available, "
                "specialties(id, name, slug)") \
        .eq("is_active", True).order("full_name")

    if specialty_slug:
        spec = db.table("specialties").select("id") \
            .eq("slug", specialty_slug).single().execute()
        if spec.data:
            query = query.eq("specialty_id", spec.data["id"])

    result = query.execute()
    return jsonify({"doctors": result.data or [], "count": len(result.data or [])})


# ── GET /api/doctors/:id ──────────────────────────────────────────────────────
@bp.route("/doctors/<doctor_id>", methods=["GET"])
def doctor_detail(doctor_id: str):
    """
    Full profile for a single doctor.
    Used by: the Book Now page to show the selected doctor's details.
    """
    db = get_admin_supabase()
    result = db.table("doctors") \
        .select("*, specialties(id, name, slug)") \
        .eq("id", doctor_id).eq("is_active", True).single().execute()

    if not result.data:
        return jsonify({"error": "Doctor not found."}), 404

    return jsonify({"doctor": result.data})


# ── GET /api/doctors/:id/slots?date=YYYY-MM-DD ────────────────────────────────
@bp.route("/doctors/<doctor_id>/slots", methods=["GET"])
def doctor_slots(doctor_id: str):
    """
    Return available time slots for a doctor on a specific date.

    Query params:
      date=YYYY-MM-DD   (required)

    Used by: booking calendar — when the patient picks a date, this
    endpoint returns which time buttons to show as selectable.

    Returns [] slots (with a message) if:
      - Date is today or in the past
      - Doctor doesn't work on that weekday
      - Doctor has a blocked date / approved leave on that day
      - All slots are already booked

    Also returns available_dates so the calendar can grey out unavailable days.
    """
    date_str = request.args.get("date", "").strip()
    if not date_str:
        return jsonify({"error": "date query parameter is required (YYYY-MM-DD)."}), 400

    db = get_admin_supabase()
    doc = db.table("doctors").select("id").eq("id", doctor_id).eq("is_active", True).single().execute()
    if not doc.data:
        return jsonify({"error": "Doctor not found."}), 404

    result = get_available_slots(doctor_id, date_str)
    if "error" in result:
        return jsonify(result), 400

    return jsonify(result)


# ── GET /api/doctors/:id/available-dates ──────────────────────────────────────
@bp.route("/doctors/<doctor_id>/available-dates", methods=["GET"])
def doctor_available_dates(doctor_id: str):
    """
    Return all bookable dates for a doctor over the next 60 days.
    Used by the booking calendar to highlight which days are selectable.
    """
    db = get_admin_supabase()
    doc = db.table("doctors").select("id").eq("id", doctor_id).eq("is_active", True).single().execute()
    if not doc.data:
        return jsonify({"error": "Doctor not found."}), 404

    dates       = get_available_dates(doctor_id)
    working_days = get_doctor_available_days(doctor_id)

    return jsonify({
        "doctor_id":       doctor_id,
        "available_dates": dates,
        "working_days":    working_days,
        "count":           len(dates),
    })
