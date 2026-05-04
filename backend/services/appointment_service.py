"""
Core appointment logic: slot generation, availability, booking, and queries.

Key rules enforced here (NOT just at the route level):
  - Only future dates accepted
  - Slot must belong to the selected doctor's schedule
  - Slot must not already be booked (UNIQUE constraint in DB is a second guard)
  - Doctor must not have a blocked date for that day
"""
from datetime import date, datetime, time, timedelta
from services.supabase_client import get_admin_supabase


# ─────────────────────────────────────────────────────────────────────────────
# Slot generation helpers
# ─────────────────────────────────────────────────────────────────────────────

def _parse_time(value) -> time:
    """Accept 'HH:MM', 'HH:MM:SS', or a time object."""
    if isinstance(value, time):
        return value
    return time.fromisoformat(str(value)[:5])   # take first 5 chars for "HH:MM"


def _generate_slots(start: time, end: time, duration_minutes: int) -> list[str]:
    """Return list of 'HH:MM' slot strings from start up to (but not including) end."""
    slots = []
    current = datetime.combine(date.today(), start)
    finish = datetime.combine(date.today(), end)
    delta = timedelta(minutes=duration_minutes)

    while current + delta <= finish:
        slots.append(current.strftime("%H:%M"))
        current += delta

    return slots


# ─────────────────────────────────────────────────────────────────────────────
# Public: available slots for a doctor on a given date
# ─────────────────────────────────────────────────────────────────────────────

def get_available_slots(doctor_id: str, date_str: str) -> dict:
    """
    Returns:
      { "slots": ["09:00", "09:30", ...], "date": "YYYY-MM-DD" }
      OR
      { "slots": [], "message": "<reason>" }
      OR
      { "error": "<validation error>" }
    """
    # Validate date format
    try:
        requested_date = date.fromisoformat(date_str)
    except ValueError:
        return {"error": "Invalid date format. Use YYYY-MM-DD."}

    # Only allow future dates (not today, not past)
    if requested_date <= date.today():
        return {"error": "Only future dates are allowed for booking."}

    # Sunday (weekday 6) is always a day off
    if requested_date.weekday() == 6:
        return {"slots": [], "message": "Doctor does not work on Sundays.", "date": date_str}

    db = get_admin_supabase()

    # Check blocked dates (full-day blocks have start_time IS NULL or block_type='full_day')
    blocked = (
        db.table("doctor_blocked_dates")
        .select("id, start_time, end_time, block_type")
        .eq("doctor_id", doctor_id)
        .eq("blocked_date", date_str)
        .execute()
    )
    full_day_blocked = any(
        (row.get("block_type") == "full_day" or row.get("start_time") is None)
        for row in (blocked.data or [])
    )
    if full_day_blocked:
        return {"slots": [], "message": "Doctor is not available on this date.", "date": date_str}

    # Collect partial blocked windows for this date
    partial_blocks = [
        (str(row["start_time"])[:5], str(row["end_time"])[:5])
        for row in (blocked.data or [])
        if row.get("block_type") == "partial" and row.get("start_time") and row.get("end_time")
    ]

    # day_of_week: Python weekday() gives 0=Mon, 6=Sun — same convention as our schema
    day_of_week = requested_date.weekday()

    schedule = (
        db.table("doctor_availability")
        .select("start_time, end_time, slot_duration_minutes")
        .eq("doctor_id", doctor_id)
        .eq("day_of_week", day_of_week)
        .eq("is_active", True)
        .execute()
    )
    if not schedule.data:
        return {"slots": [], "message": "Doctor does not work on this day.", "date": date_str}

    avail = schedule.data[0]
    all_slots = _generate_slots(
        _parse_time(avail["start_time"]),
        _parse_time(avail["end_time"]),
        avail["slot_duration_minutes"],
    )

    # Fetch already booked (non-cancelled) slots for that doctor on that date
    booked_result = (
        db.table("appointments")
        .select("appointment_time")
        .eq("doctor_id", doctor_id)
        .eq("appointment_date", date_str)
        .neq("status", "cancelled")
        .execute()
    )
    booked_times = {
        str(row["appointment_time"])[:5]        # normalise to "HH:MM"
        for row in (booked_result.data or [])
    }

    def _in_partial_block(slot: str) -> bool:
        for blk_start, blk_end in partial_blocks:
            if blk_start <= slot < blk_end:
                return True
        return False

    available = [s for s in all_slots if s not in booked_times and not _in_partial_block(s)]
    return {"slots": available, "date": date_str, "total": len(available)}


# ─────────────────────────────────────────────────────────────────────────────
# Public: available calendar dates for a doctor (next 60 days)
# ─────────────────────────────────────────────────────────────────────────────

def get_available_dates(doctor_id: str, days_ahead: int = 60) -> list[str]:
    """
    Returns ISO date strings (YYYY-MM-DD) for the next `days_ahead` days
    on which the doctor has at least one free slot.
    Excludes blocked dates and fully-booked days.
    """
    db = get_admin_supabase()

    # Working weekdays for this doctor
    schedule_result = (
        db.table("doctor_availability")
        .select("day_of_week")
        .eq("doctor_id", doctor_id)
        .eq("is_active", True)
        .execute()
    )
    working_days = {row["day_of_week"] for row in (schedule_result.data or [])}
    if not working_days:
        return []

    # Blocked dates in range
    today = date.today()
    future_limit = today + timedelta(days=days_ahead)
    blocked_result = (
        db.table("doctor_blocked_dates")
        .select("blocked_date")
        .eq("doctor_id", doctor_id)
        .gte("blocked_date", today.isoformat())
        .lte("blocked_date", future_limit.isoformat())
        .execute()
    )
    blocked_dates = {row["blocked_date"] for row in (blocked_result.data or [])}

    available_dates: list[str] = []
    check = today + timedelta(days=1)   # start from tomorrow

    while check <= future_limit:
        # weekday 6 = Sunday — always off regardless of doctor_availability entries
        if check.weekday() != 6 and check.weekday() in working_days and check.isoformat() not in blocked_dates:
            available_dates.append(check.isoformat())
        check += timedelta(days=1)

    return available_dates


# ─────────────────────────────────────────────────────────────────────────────
# Authenticated: create appointment
# ─────────────────────────────────────────────────────────────────────────────

def create_appointment(
    patient_id: str,
    patient_name: str,
    patient_email: str,
    patient_phone: str,
    doctor_id: str,
    specialty_id: str,
    appointment_date: str,
    appointment_time: str,
    notes: str = "",
) -> tuple[dict | None, str | None]:
    """
    Validate + insert an appointment.
    Returns (appointment_dict, None) on success.
    Returns (None, error_message) on failure.
    """
    # Re-validate date on the backend — never trust frontend alone
    try:
        apt_date = date.fromisoformat(appointment_date)
    except ValueError:
        return None, "Invalid date format."

    if apt_date <= date.today():
        return None, "Only future dates are allowed."

    # Normalise time to HH:MM
    apt_time = appointment_time[:5]

    # Verify the slot is actually available
    slot_check = get_available_slots(doctor_id, appointment_date)
    if "error" in slot_check:
        return None, slot_check["error"]

    if apt_time not in slot_check.get("slots", []):
        return None, "The selected time slot is no longer available. Please choose another."

    db = get_admin_supabase()
    try:
        result = (
            db.table("appointments")
            .insert({
                "patient_id": patient_id,
                "doctor_id": doctor_id,
                "specialty_id": specialty_id,
                "appointment_date": appointment_date,
                "appointment_time": apt_time,
                "status": "pending",
                "patient_name": patient_name,
                "patient_email": patient_email,
                "patient_phone": patient_phone,
                "notes": notes,
            })
            .execute()
        )
        if result.data:
            return result.data[0], None
        return None, "Failed to save appointment. Please try again."
    except Exception as e:
        msg = str(e)
        # Catch unique constraint violation from DB (double-booking guard)
        if "no_double_booking" in msg or "unique" in msg.lower():
            return None, "That slot was just booked by someone else. Please pick another time."
        return None, "Booking failed. Please try again."


# ─────────────────────────────────────────────────────────────────────────────
# Authenticated: fetch appointments
# ─────────────────────────────────────────────────────────────────────────────

def get_patient_appointments(patient_id: str) -> list[dict]:
    db = get_admin_supabase()
    result = (
        db.table("appointments")
        .select(
            "id, appointment_date, appointment_time, status, notes, "
            "patient_name, created_at, "
            "doctors(id, full_name, title, photo_url, specialties(name))"
        )
        .eq("patient_id", patient_id)
        .order("appointment_date", desc=True)
        .execute()
    )
    return result.data or []


def get_doctor_appointments(doctor_id: str, date_filter: str | None = None,
                            status_filter: str | None = None) -> list[dict]:
    db = get_admin_supabase()
    query = (
        db.table("appointments")
        .select("id, appointment_date, appointment_time, status, notes, "
                "patient_name, patient_email, patient_phone, created_at")
        .eq("doctor_id", doctor_id)
        .order("appointment_date")
        .order("appointment_time")
    )
    if date_filter:
        query = query.eq("appointment_date", date_filter)
    if status_filter:
        query = query.eq("status", status_filter)

    result = query.execute()
    return result.data or []


def get_doctor_stats(doctor_id: str) -> dict:
    """Summary counts for the doctor dashboard header."""
    today_str = date.today().isoformat()
    db = get_admin_supabase()

    all_apts = (
        db.table("appointments")
        .select("id, appointment_date, status")
        .eq("doctor_id", doctor_id)
        .neq("status", "cancelled")
        .execute()
    )
    rows = all_apts.data or []

    total = len(rows)
    today_count = sum(1 for r in rows if r["appointment_date"] == today_str)
    upcoming = sum(1 for r in rows if r["appointment_date"] > today_str)
    completed = sum(1 for r in rows if r["status"] == "completed")

    return {
        "total_patients": total,
        "today": today_count,
        "upcoming": upcoming,
        "completed": completed,
    }


def get_all_appointments(
    status: str | None = None,
    doctor_id: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> list[dict]:
    """Admin-only: returns all appointments with optional filters."""
    db = get_admin_supabase()
    query = (
        db.table("appointments")
        .select(
            "id, doctor_id, appointment_date, appointment_time, status, notes, "
            "patient_name, patient_email, patient_phone, created_at, "
            "doctors(id, full_name, title, specialties(name))"
        )
        .order("appointment_date", desc=True)
    )
    if status:
        query = query.eq("status", status)
    if doctor_id:
        query = query.eq("doctor_id", doctor_id)
    if date_from:
        query = query.gte("appointment_date", date_from)
    if date_to:
        query = query.lte("appointment_date", date_to)

    result = query.execute()
    return result.data or []


def update_appointment_status(appointment_id: str, new_status: str) -> tuple[dict | None, str | None]:
    valid = {"pending", "confirmed", "completed", "cancelled", "rejected"}
    if new_status not in valid:
        return None, f"Invalid status. Must be one of: {', '.join(valid)}"

    db = get_admin_supabase()
    result = (
        db.table("appointments")
        .update({"status": new_status})
        .eq("id", appointment_id)
        .execute()
    )
    if result.data:
        return result.data[0], None
    return None, "Appointment not found or update failed."
