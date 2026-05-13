"""
routes/doctor_dashboard.py — Doctor-only routes  (role = 'doctor')

GET  /api/doctor/appointments    all appointments for this doctor
GET  /api/doctor/patients        distinct patients who booked this doctor
POST /api/doctor/leaves          submit a leave request
GET  /api/doctor/leaves          view own leave requests

WHY SEPARATE FROM PUBLIC ROUTES:
  Every route here is decorated with @require_role('doctor').
  A patient or admin hitting these routes gets a 403 immediately.
  The doctor only sees their OWN data — never other doctors' data.
"""
from flask import Blueprint, jsonify, request
from middleware.auth_middleware import require_role
from services.auth_service import get_doctor_record
from services.appointment_service import get_doctor_appointments, get_doctor_stats, update_appointment_status
from services.leaves_service import request_leave, get_doctor_leaves
from services.analytics_service import get_visit_analytics

bp = Blueprint("doctor", __name__)


def _doctor_or_404(uid: str):
    """Get the doctor record for the logged-in doctor-role user."""
    return get_doctor_record(uid)


# ── GET /api/doctor/appointments ──────────────────────────────────────────────
@bp.route("/appointments", methods=["GET"])
@require_role("doctor")
def appointments(current_user, current_role):
    """
    Return all appointments for this doctor.

    Optional query params:
      ?date=YYYY-MM-DD   filter to a single day (used for today's schedule)
      ?status=pending    filter by status

    WHY doctor can only see their own:
    get_doctor_appointments(doctor_id) filters by the doctor's UUID,
    so even if someone tampered with the token they could only see
    appointments belonging to their own doctor record.
    """
    doctor = _doctor_or_404(current_user["id"])
    if not doctor:
        return jsonify({"error": "Doctor profile not linked to this account. Contact admin."}), 404

    date_filter   = request.args.get("date", "").strip() or None
    status_filter = request.args.get("status", "").strip() or None

    appointments = get_doctor_appointments(
        doctor["id"], date_filter=date_filter, status_filter=status_filter
    )
    stats = get_doctor_stats(doctor["id"])

    return jsonify({
        "appointments": appointments,
        "count":        len(appointments),
        "stats":        stats,
    })


# ── GET /api/doctor/patients ──────────────────────────────────────────────────
@bp.route("/patients", methods=["GET"])
@require_role("doctor")
def patients(current_user, current_role):
    """
    Return distinct patients who have booked this doctor.

    WHY this is useful:
    The doctor dashboard shows a patient list so the doctor can see
    who they've treated or will treat — useful for preparation and records.
    De-duplicated so each patient appears once even with multiple visits.
    """
    doctor = _doctor_or_404(current_user["id"])
    if not doctor:
        return jsonify({"error": "Doctor profile not linked. Contact admin."}), 404

    from services.supabase_client import get_admin_supabase
    db = get_admin_supabase()

    result = db.table("appointments") \
        .select("patient_id, patient_name, patient_email, patient_phone, appointment_date") \
        .eq("doctor_id", doctor["id"]) \
        .neq("status", "cancelled") \
        .order("appointment_date", desc=True) \
        .execute()

    # De-duplicate by patient_id — keep the most recent appointment info
    seen, patients = set(), []
    for row in (result.data or []):
        pid = row["patient_id"]
        if pid not in seen:
            seen.add(pid)
            patients.append({
                "patient_id":    pid,
                "patient_name":  row["patient_name"],
                "patient_email": row["patient_email"],
                "patient_phone": row["patient_phone"],
                "last_visit":    row["appointment_date"],
            })

    return jsonify({"patients": patients, "count": len(patients)})


# ── POST /api/doctor/leaves ───────────────────────────────────────────────────
@bp.route("/leaves", methods=["POST"])
@require_role("doctor")
def create_leave(current_user, current_role):
    """
    Submit a leave request.

    Body: { "date": "YYYY-MM-DD", "reason": "optional" }

    Status starts as 'pending' — admin must approve for the date to be blocked.
    WHY admin approval is required (not auto-blocked):
    The admin may need to check if patients are already booked on that day
    and reschedule them before approving the leave.
    """
    doctor = _doctor_or_404(current_user["id"])
    if not doctor:
        return jsonify({"error": "Doctor profile not linked. Contact admin."}), 404

    data       = request.get_json(silent=True) or {}
    leave_date  = data.get("date", "").strip()
    reason      = data.get("reason", "").strip()
    start_time  = data.get("start_time", "").strip() or None
    end_time    = data.get("end_time", "").strip() or None

    if not leave_date:
        return jsonify({"error": "date is required (YYYY-MM-DD)."}), 400
    if (start_time and not end_time) or (end_time and not start_time):
        return jsonify({"error": "Provide both start_time and end_time for a partial leave."}), 400

    leave, error = request_leave(doctor["id"], leave_date, reason, start_time, end_time)
    if error:
        return jsonify({"error": error}), 400

    return jsonify({"message": "Leave request submitted. Awaiting admin approval.", "leave": leave}), 201


# ── GET /api/doctor/leaves ────────────────────────────────────────────────────
@bp.route("/leaves", methods=["GET"])
@require_role("doctor")
def list_leaves(current_user, current_role):
    """
    Return all leave requests submitted by this doctor.
    The doctor can see which are pending, approved, or rejected.
    """
    doctor = _doctor_or_404(current_user["id"])
    if not doctor:
        return jsonify({"error": "Doctor profile not linked. Contact admin."}), 404

    leaves = get_doctor_leaves(doctor["id"])
    return jsonify({"leaves": leaves, "count": len(leaves)})


# ── PUT /api/doctor/appointments/:id/status ───────────────────────────────────
@bp.route("/appointments/<appointment_id>/status", methods=["PUT"])
@require_role("doctor")
def update_status(appointment_id: str, current_user, current_role):
    """
    Doctor marks an appointment as completed or cancelled.
    Body: { "status": "completed" | "cancelled" }

    WHY doctors can mark completed but not confirmed:
    'confirmed' is set by the admin workflow.
    Doctors mark visits as done after the patient attends.
    """
    doctor = _doctor_or_404(current_user["id"])
    if not doctor:
        return jsonify({"error": "Doctor profile not linked. Contact admin."}), 404

    data       = request.get_json(silent=True) or {}
    new_status = data.get("status", "").strip()
    if new_status not in ("completed", "cancelled"):
        return jsonify({"error": "status must be 'completed' or 'cancelled'."}), 400

    from services.supabase_client import get_admin_supabase
    db = get_admin_supabase()

    existing = db.table("appointments").select("doctor_id") \
        .eq("id", appointment_id).single().execute()
    if not existing.data:
        return jsonify({"error": "Appointment not found."}), 404
    if existing.data["doctor_id"] != doctor["id"]:
        return jsonify({"error": "You can only update your own appointments."}), 403

    appt, err = update_appointment_status(appointment_id, new_status)
    if err:
        return jsonify({"error": err}), 400

    return jsonify({"message": "Status updated.", "appointment": appt})


# ── GET /api/doctor/surgeries ─────────────────────────────────────────────────
@bp.route("/surgeries", methods=["GET"])
@require_role("doctor")
def list_surgeries(current_user, current_role):
    """Return all surgeries scheduled for this doctor."""
    doctor = _doctor_or_404(current_user["id"])
    if not doctor:
        return jsonify({"error": "Doctor profile not linked. Contact admin."}), 404

    from services.supabase_client import get_admin_supabase
    db    = get_admin_supabase()
    query = db.table("surgeries") \
        .select("*") \
        .eq("doctor_id", doctor["id"]) \
        .order("surgery_date").order("surgery_time")

    if request.args.get("status"):
        query = query.eq("status", request.args["status"])

    result = query.execute()
    return jsonify({"surgeries": result.data or [], "count": len(result.data or [])})


# ── GET /api/doctor/analytics ─────────────────────────────────────────────────
@bp.route("/analytics", methods=["GET"])
@require_role("doctor")
def doctor_analytics(current_user, current_role):
    """
    Visit analytics for the logged-in doctor.
    Same payload shape as /api/admin/analytics, scoped to this doctor only.
    """
    doctor = _doctor_or_404(current_user["id"])
    if not doctor:
        return jsonify({"error": "Doctor profile not linked. Contact admin."}), 404
    return jsonify(get_visit_analytics(doctor_id=doctor["id"]))
