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


def find_conflicting_appointments(doctor_id: str, leave_date: str,
                                  start_time: str | None,
                                  end_time:   str | None) -> list[dict]:
    """
    Return any non-cancelled appointments that overlap with the proposed
    leave window. Used to warn the admin before approving a leave.

    For full-day leaves: every non-cancelled appointment on that date conflicts.
    For partial leaves: only appointments whose time falls in [start, end) conflict.
    """
    db = get_admin_supabase()
    q  = (
        db.table("appointments")
        .select("id, appointment_time, status, patient_name, patient_email")
        .eq("doctor_id", doctor_id)
        .eq("appointment_date", leave_date)
        .neq("status", "cancelled")
    )
    rows = q.execute().data or []
    if not start_time or not end_time:
        # full-day leave — every booking conflicts
        return rows
    # partial leave — filter to the time range
    def _hhmm(t):
        return str(t)[:5] if t else ""
    s, e = _hhmm(start_time), _hhmm(end_time)
    return [r for r in rows if s <= _hhmm(r.get("appointment_time")) < e]


def approve_leave(leave_id: str, admin_note: str = "",
                  force: bool = False) -> tuple[dict | None, str | None, list | None]:
    """
    Admin approves a leave.

    If non-cancelled appointments fall inside the leave window AND `force`
    is False, returns (None, "<conflict message>", [conflicting_appointments])
    so the admin UI can show the conflicts and let the admin decide:
       • Cancel anyway: call again with force=True (auto-cancels those bookings).
       • Reject leave : admin clicks Reject instead.

    With force=True, the conflicting appointments are auto-cancelled before
    the leave is approved. Patients can be notified separately via email.
    """
    db = get_admin_supabase()

    leave_q = db.table("doctor_leaves").select("*").eq("id", leave_id).execute()
    if not leave_q.data:
        return None, "Leave request not found.", None
    leave = leave_q.data[0]
    if leave["status"] != "pending":
        return None, f"Leave is already {leave['status']}.", None

    is_partial = leave.get("leave_type") == "partial"
    s_time = leave.get("start_time") if is_partial else None
    e_time = leave.get("end_time")   if is_partial else None

    # ── Conflict check ───────────────────────────────────────────────────────
    conflicts = find_conflicting_appointments(
        leave["doctor_id"], leave["leave_date"], s_time, e_time,
    )
    if conflicts and not force:
        msg = (f"{len(conflicts)} confirmed/pending appointment(s) overlap this leave. "
               f"Approving will cancel them. Reject the leave, or approve with force.")
        return None, msg, conflicts

    # ── Cancel overlapping appointments (force mode) ─────────────────────────
    for apt in conflicts:
        db.table("appointments").update({"status": "cancelled"}).eq("id", apt["id"]).execute()
        # Best-effort email notify the patient
        try:
            from services import email_service
            email_service.send_appointment_rejected(
                patient_email = apt.get("patient_email", ""),
                patient_name  = apt.get("patient_name", "Patient"),
                doctor_name   = "your doctor",
                date          = leave["leave_date"],
                reason        = "Doctor became unavailable due to an approved leave. Please rebook.",
            )
        except Exception:
            pass

    # ── Approve the leave + add the block row ────────────────────────────────
    db.table("doctor_leaves").update({
        "status":     "approved",
        "admin_note": admin_note,
    }).eq("id", leave_id).execute()

    block_row = {
        "doctor_id":    leave["doctor_id"],
        "blocked_date": leave["leave_date"],
        "reason":       f"Approved leave: {leave.get('reason', '')}",
        "block_type":   "partial" if is_partial else "full_day",
    }
    if is_partial:
        block_row["start_time"] = s_time
        block_row["end_time"]   = e_time

    try:
        db.table("doctor_blocked_dates").insert(block_row).execute()
    except Exception:
        pass  # Already blocked — not fatal

    updated_q = db.table("doctor_leaves").select("*").eq("id", leave_id).execute()
    updated = updated_q.data[0] if updated_q.data else None
    return updated, None, conflicts if conflicts else None


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
