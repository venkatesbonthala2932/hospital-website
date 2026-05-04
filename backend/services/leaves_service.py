"""
services/leaves_service.py — Doctor leave request logic

FLOW:
  Doctor submits leave (full-day or partial) → status = 'pending'
  Admin approves  → status = 'approved' + row added to doctor_blocked_dates
  Admin rejects   → status = 'rejected'  (no blocked date created)

Partial leave: doctor supplies start_time + end_time (e.g. "09:00"–"13:00").
When approved, a doctor_blocked_dates row is inserted for that time window only;
the remaining slots on that day stay open for booking.
"""
from datetime import date
from services.supabase_client import get_admin_supabase


def request_leave(
    doctor_id: str,
    leave_date: str,
    reason: str = "",
    start_time: str | None = None,
    end_time: str | None = None,
) -> tuple[dict | None, str | None]:
    """
    Doctor submits a leave request (full-day or partial).
    start_time / end_time are HH:MM strings for partial leaves.
    """
    try:
        leave_dt = date.fromisoformat(leave_date)
    except ValueError:
        return None, "Invalid date format. Use YYYY-MM-DD."

    if leave_dt <= date.today():
        return None, "Leave can only be requested for future dates."

    is_partial = bool(start_time and end_time)
    if is_partial:
        if start_time >= end_time:
            return None, "start_time must be before end_time."

    db = get_admin_supabase()
    row = {
        "doctor_id":  doctor_id,
        "leave_date": leave_date,
        "reason":     reason,
        "status":     "pending",
        "leave_type": "partial" if is_partial else "full_day",
    }
    if is_partial:
        row["start_time"] = start_time
        row["end_time"]   = end_time

    try:
        result = db.table("doctor_leaves").insert(row).execute()
        return result.data[0] if result.data else None, None
    except Exception as e:
        if "unique" in str(e).lower():
            return None, "A leave request for this date/time already exists."
        return None, f"Could not submit leave request: {e}"


def get_doctor_leaves(doctor_id: str) -> list[dict]:
    db = get_admin_supabase()
    result = db.table("doctor_leaves") \
        .select("*") \
        .eq("doctor_id", doctor_id) \
        .order("leave_date", desc=True) \
        .execute()
    return result.data or []


def get_all_leaves(status: str | None = None) -> list[dict]:
    db = get_admin_supabase()
    query = db.table("doctor_leaves") \
        .select("*, doctor_id, doctors(id, full_name, title, specialties(name))") \
        .order("leave_date")
    if status:
        query = query.eq("status", status)
    result = query.execute()
    return result.data or []


def approve_leave(leave_id: str, admin_note: str = "") -> tuple[dict | None, str | None]:
    """
    Admin approves a leave.
    Inserts a doctor_blocked_dates row (full-day or time-ranged).
    """
    db = get_admin_supabase()

    leave = db.table("doctor_leaves").select("*").eq("id", leave_id).single().execute()
    if not leave.data:
        return None, "Leave request not found."
    if leave.data["status"] != "pending":
        return None, f"Leave is already {leave.data['status']}."

    db.table("doctor_leaves").update({
        "status":     "approved",
        "admin_note": admin_note,
    }).eq("id", leave_id).execute()

    is_partial = leave.data.get("leave_type") == "partial"
    block_row = {
        "doctor_id":    leave.data["doctor_id"],
        "blocked_date": leave.data["leave_date"],
        "reason":       f"Approved leave: {leave.data.get('reason', '')}",
        "block_type":   "partial" if is_partial else "full_day",
    }
    if is_partial:
        block_row["start_time"] = leave.data.get("start_time")
        block_row["end_time"]   = leave.data.get("end_time")

    try:
        db.table("doctor_blocked_dates").insert(block_row).execute()
    except Exception:
        pass  # Might already be blocked — not fatal

    updated = db.table("doctor_leaves").select("*").eq("id", leave_id).single().execute()
    return updated.data, None


def reject_leave(leave_id: str, admin_note: str = "") -> tuple[dict | None, str | None]:
    db = get_admin_supabase()

    leave = db.table("doctor_leaves").select("id, status").eq("id", leave_id).single().execute()
    if not leave.data:
        return None, "Leave request not found."
    if leave.data["status"] != "pending":
        return None, f"Leave is already {leave.data['status']}."

    db.table("doctor_leaves").update({
        "status":     "rejected",
        "admin_note": admin_note,
    }).eq("id", leave_id).execute()

    updated = db.table("doctor_leaves").select("*").eq("id", leave_id).single().execute()
    return updated.data, None
