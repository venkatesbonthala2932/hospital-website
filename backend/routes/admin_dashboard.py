"""
routes/admin_dashboard.py — Admin-only routes  (role = 'admin')

GET  /api/admin/appointments              all appointments (filterable)
POST /api/admin/appointments/:id/confirm  confirm an appointment
POST /api/admin/appointments/:id/reject   reject an appointment
GET  /api/admin/leaves                    all doctor leave requests
POST /api/admin/leaves/:id/approve        approve a leave
POST /api/admin/leaves/:id/reject         reject a leave
GET  /api/admin/doctors                   all doctors
GET  /api/admin/patients                  all patients

WHY SEPARATE FROM DOCTOR ROUTES:
  @require_role('admin') means only accounts with role='admin' in the
  profiles table can reach these routes. A doctor or patient gets a 403.
  Admins see ALL data across all doctors — doctors only see their own.
"""
from flask import Blueprint, jsonify, request
from middleware.auth_middleware import require_role
from services.appointment_service import get_all_appointments, update_appointment_status
from services.leaves_service import get_all_leaves, approve_leave, reject_leave
from services.supabase_client import get_admin_supabase
from services.firebase_service import create_firebase_user, update_firebase_user
from services import email_service
from datetime import date
import secrets
import string

bp = Blueprint("admin", __name__)


# ── GET /api/admin/appointments ───────────────────────────────────────────────
@bp.route("/appointments", methods=["GET"])
@require_role("admin")
def all_appointments(current_user, current_role):
    """
    Return all appointments across all doctors.

    Optional query params:
      ?status=pending|confirmed|completed|cancelled|rejected
      ?doctor_id=<uuid>
      ?date_from=YYYY-MM-DD
      ?date_to=YYYY-MM-DD

    WHY admins need this:
    Hospitals need a central view to manage scheduling, handle
    cancellations, confirm bookings, and generate daily reports.
    """
    appointments = get_all_appointments(
        status    = request.args.get("status"),
        doctor_id = request.args.get("doctor_id"),
        date_from = request.args.get("date_from"),
        date_to   = request.args.get("date_to"),
    )
    return jsonify({"appointments": appointments, "count": len(appointments)})


# ── POST /api/admin/appointments/:id/confirm ──────────────────────────────────
@bp.route("/appointments/<appointment_id>/confirm", methods=["POST"])
@require_role("admin")
def confirm_appointment(appointment_id: str, current_user, current_role):
    """
    Confirm a pending appointment.

    WHY a separate confirm route (not just a status update):
    A dedicated endpoint is clearer in intent than a generic PATCH.
    It also lets us add confirmation-specific logic later
    (e.g. send SMS to patient, notify doctor).
    """
    # Fetch appointment before updating so we have the patient's email
    db   = get_admin_supabase()
    row  = db.table("appointments") \
        .select("patient_email, patient_name, appointment_date, appointment_time, "
                "doctors(full_name, specialties(name))") \
        .eq("id", appointment_id).single().execute()

    appt, err = update_appointment_status(appointment_id, "confirmed")
    if err:
        return jsonify({"error": err}), 400

    if row.data:
        r       = row.data
        doc     = r.get("doctors", {}) or {}
        email_service.send_appointment_confirmed(
            patient_email = r.get("patient_email", ""),
            patient_name  = r.get("patient_name", "Patient"),
            doctor_name   = doc.get("full_name", "our doctor"),
            specialty     = (doc.get("specialties") or {}).get("name", ""),
            date          = r.get("appointment_date", ""),
            time          = r.get("appointment_time", ""),
        )

    return jsonify({"message": "Appointment confirmed.", "appointment": appt})


# ── POST /api/admin/appointments/:id/reject ───────────────────────────────────
@bp.route("/appointments/<appointment_id>/reject", methods=["POST"])
@require_role("admin")
def reject_appointment(appointment_id: str, current_user, current_role):
    """
    Reject / turn down an appointment.

    Optional body: { "reason": "Doctor unavailable on this day." }
    """
    data   = request.get_json(silent=True) or {}
    reason = data.get("reason", "")

    db  = get_admin_supabase()
    row = db.table("appointments") \
        .select("patient_email, patient_name, appointment_date, doctors(full_name)") \
        .eq("id", appointment_id).single().execute()

    appt, err = update_appointment_status(appointment_id, "rejected")
    if err:
        return jsonify({"error": err}), 400

    if row.data:
        r = row.data
        email_service.send_appointment_rejected(
            patient_email = r.get("patient_email", ""),
            patient_name  = r.get("patient_name", "Patient"),
            doctor_name   = (r.get("doctors") or {}).get("full_name", "our doctor"),
            date          = r.get("appointment_date", ""),
            reason        = reason,
        )

    return jsonify({"message": "Appointment rejected.", "appointment": appt})


# ── GET /api/admin/leaves ─────────────────────────────────────────────────────
@bp.route("/leaves", methods=["GET"])
@require_role("admin")
def all_leaves(current_user, current_role):
    """
    Return all doctor leave requests.
    Optional filter: ?status=pending|approved|rejected

    WHY admins review leaves:
    Before approving, the admin checks if any patients are booked on
    that date and arranges rescheduling if needed.
    """
    status = request.args.get("status", "").strip() or None
    leaves = get_all_leaves(status=status)
    return jsonify({"leaves": leaves, "count": len(leaves)})


# ── POST /api/admin/leaves/:id/approve ───────────────────────────────────────
@bp.route("/leaves/<leave_id>/approve", methods=["POST"])
@require_role("admin")
def approve_leave_route(leave_id: str, current_user, current_role):
    """
    Approve a doctor's leave request.

    What happens:
    1. doctor_leaves.status → 'approved'
    2. A row is inserted into doctor_blocked_dates for that date
    3. From now on, GET /api/doctors/:id/slots for that date returns []

    Optional body: { "note": "Approved. Patients rescheduled." }
    """
    data  = request.get_json(silent=True) or {}
    leave, err = approve_leave(leave_id, admin_note=data.get("note", ""))
    if err:
        return jsonify({"error": err}), 400
    return jsonify({"message": "Leave approved. Date is now blocked.", "leave": leave})


# ── POST /api/admin/leaves/:id/reject ────────────────────────────────────────
@bp.route("/leaves/<leave_id>/reject", methods=["POST"])
@require_role("admin")
def reject_leave_route(leave_id: str, current_user, current_role):
    """
    Reject a doctor's leave request.
    The date remains available for bookings.

    Optional body: { "note": "We need you that day, please reschedule." }
    """
    data  = request.get_json(silent=True) or {}
    leave, err = reject_leave(leave_id, admin_note=data.get("note", ""))
    if err:
        return jsonify({"error": err}), 400
    return jsonify({"message": "Leave rejected.", "leave": leave})


# ── GET /api/admin/doctors ────────────────────────────────────────────────────
@bp.route("/doctors", methods=["GET"])
@require_role("admin")
def all_doctors(current_user, current_role):
    """
    Return all doctors (active + inactive) with their specialty.
    Used by the admin panel to manage the doctor roster.
    """
    db = get_admin_supabase()
    result = db.table("doctors") \
        .select("*, specialties(name, slug), profiles(email)") \
        .order("full_name").execute()
    return jsonify({"doctors": result.data or []})


# ── GET /api/admin/patients ───────────────────────────────────────────────────
@bp.route("/patients", methods=["GET"])
@require_role("admin")
def all_patients(current_user, current_role):
    """
    Return all distinct patients who have at least one appointment.

    WHY de-duplicated:
    The same patient might book 5 appointments. The admin panel shows
    a patient list, not an appointment list — one row per person.
    """
    db = get_admin_supabase()
    result = db.table("appointments") \
        .select("patient_id, patient_name, patient_email, patient_phone") \
        .order("patient_name").execute()

    seen, patients = set(), []
    for row in (result.data or []):
        if row["patient_id"] not in seen:
            seen.add(row["patient_id"])
            patients.append(row)

    return jsonify({"patients": patients, "count": len(patients)})


# ── PUT /api/admin/users/:id/role ─────────────────────────────────────────────
@bp.route("/users/<user_id>/role", methods=["PUT"])
@require_role("admin")
def set_role(user_id: str, current_user, current_role):
    """
    Change any user's role.
    Body: { "role": "doctor" | "patient" | "admin" }

    Typical use: after a doctor registers as a patient, the admin
    changes their role to 'doctor' and links their doctor record.
    """
    data     = request.get_json(silent=True) or {}
    new_role = data.get("role", "").strip()
    if new_role not in ("patient", "doctor", "admin"):
        return jsonify({"error": "role must be patient, doctor, or admin."}), 400

    db = get_admin_supabase()
    result = db.table("profiles").update({"role": new_role}) \
        .eq("id", user_id).execute()
    if not result.data:
        return jsonify({"error": "User not found."}), 404

    return jsonify({"message": f"Role updated to '{new_role}'."})


# ── POST /api/admin/doctors/:id/link-user ─────────────────────────────────────
@bp.route("/doctors/<doctor_id>/link-user", methods=["POST"])
@require_role("admin")
def link_doctor_user(doctor_id: str, current_user, current_role):
    """
    Link a Firebase UID to a doctor row.
    Body: { "user_id": "<firebase_uid>" }

    Use this after a doctor registers — their profile starts as 'patient'.
    Admin changes their role to 'doctor' and links their doctor record here.
    """
    data    = request.get_json(silent=True) or {}
    user_id = data.get("user_id", "").strip()
    if not user_id:
        return jsonify({"error": "user_id is required."}), 400

    db = get_admin_supabase()
    db.table("doctors").update({"user_id": user_id, "is_active": True}) \
        .eq("id", doctor_id).execute()
    db.table("profiles").update({"role": "doctor"}).eq("id", user_id).execute()

    return jsonify({"message": "Doctor account activated."})


# ── GET /api/admin/stats ──────────────────────────────────────────────────────
@bp.route("/stats", methods=["GET"])
@require_role("admin")
def stats(current_user, current_role):
    """Dashboard summary counts shown in the admin header."""
    today = date.today().isoformat()
    db    = get_admin_supabase()

    def count(table, **filters):
        q = db.table(table).select("id", count="exact")
        for col, val in filters.items():
            q = q.eq(col, val)
        return q.execute().count or 0

    all_apts  = db.table("appointments").select("patient_id").execute().data or []
    patients  = len({r["patient_id"] for r in all_apts})

    return jsonify({
        "total_doctors":      count("doctors", is_active=True),
        "total_patients":     patients,
        "total_appointments": count("appointments"),
        "today":              db.table("appointments").select("id", count="exact").eq("appointment_date", today).execute().count or 0,
        "pending":            count("appointments", status="pending"),
        "confirmed":          count("appointments", status="confirmed"),
        "pending_leaves":     count("doctor_leaves", status="pending"),
    })


# ── POST /api/admin/doctors ───────────────────────────────────────────────────
@bp.route("/doctors", methods=["POST"])
@require_role("admin")
def create_doctor(current_user, current_role):
    """
    Create a new doctor: Firebase account + Supabase profile + doctor record.
    Body: { email, full_name, specialty_id, title, qualifications,
            experience_years, consultation_fee, bio }
    Returns the new doctor record + temporary password.
    """
    data = request.get_json(silent=True) or {}
    email    = data.get("email", "").strip().lower()
    name     = data.get("full_name", "").strip()
    spec_id  = data.get("specialty_id", "").strip()

    if not email or not name or not spec_id:
        return jsonify({"error": "email, full_name, and specialty_id are required."}), 400

    # Generate a temp password the admin can share with the doctor
    alphabet = string.ascii_letters + string.digits + "!@#$"
    temp_pw  = "".join(secrets.choice(alphabet) for _ in range(12))

    # 1. Create Firebase account
    try:
        fb = create_firebase_user(email=email, password=temp_pw, display_name=name)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    uid = fb["uid"]
    db  = get_admin_supabase()

    # 2. Create/update Supabase profile
    db.table("profiles").upsert({
        "id": uid, "email": email, "full_name": name, "role": "doctor",
    }, on_conflict="id").execute()

    # 3. Create doctor record
    doctor_row = {
        "user_id":          uid,
        "specialty_id":     spec_id,
        "full_name":        name,
        "title":            data.get("title", "").strip(),
        "qualifications":   data.get("qualifications", "").strip(),
        "experience_years": int(data.get("experience_years", 0) or 0),
        "consultation_fee": float(data.get("consultation_fee", 0) or 0),
        "bio":              data.get("bio", "").strip(),
        "is_active":        True,
        "is_available":     True,
    }
    result = db.table("doctors").insert(doctor_row).execute()
    if not result.data:
        return jsonify({"error": "Failed to create doctor record."}), 500

    # 4. Auto-insert Mon-Sat (0–5) availability: 9:00-17:00, 30-min slots
    #    Sunday (6) is deliberately excluded — always a day off
    new_doctor_id = result.data[0]["id"]
    avail_rows = [
        {
            "doctor_id":             new_doctor_id,
            "day_of_week":           day,
            "start_time":            "09:00",
            "end_time":              "17:00",
            "slot_duration_minutes": 30,
            "is_active":             True,
        }
        for day in range(6)
    ]
    db.table("doctor_availability").insert(avail_rows).execute()

    return jsonify({
        "message":          "Doctor account created.",
        "doctor":           result.data[0],
        "temp_password":    temp_pw,
        "login_email":      email,
    }), 201


# ── PUT /api/admin/doctors/:id ────────────────────────────────────────────────
@bp.route("/doctors/<doctor_id>", methods=["PUT"])
@require_role("admin")
def update_doctor(doctor_id: str, current_user, current_role):
    """
    Update an existing doctor's details.
    Allowed fields: full_name, title, qualifications, experience_years,
      consultation_fee, bio, photo_url, is_active, is_available, specialty_id, email
    When email changes: Firebase Auth + Supabase profiles are also updated.
    """
    data = request.get_json(silent=True) or {}
    doctor_fields = {"full_name", "title", "qualifications", "experience_years",
                     "consultation_fee", "bio", "photo_url", "is_active",
                     "is_available", "specialty_id"}
    update = {k: v for k, v in data.items() if k in doctor_fields}

    db  = get_admin_supabase()
    doc = db.table("doctors").select("id, user_id, full_name").eq("id", doctor_id).single().execute()
    if not doc.data:
        return jsonify({"error": "Doctor not found."}), 404

    # Handle email change separately
    new_email = data.get("email", "").strip().lower()
    if new_email:
        uid = doc.data.get("user_id")
        if uid:
            try:
                update_firebase_user(uid, email=new_email,
                                     display_name=data.get("full_name") or doc.data["full_name"])
            except ValueError as e:
                return jsonify({"error": str(e)}), 400
            db.table("profiles").update({"email": new_email}).eq("id", uid).execute()

    # Sync display_name to Firebase if name changed
    if "full_name" in update and doc.data.get("user_id"):
        try:
            update_firebase_user(doc.data["user_id"], display_name=update["full_name"])
        except ValueError:
            pass

    if not update:
        return jsonify({"message": "No doctor fields to update — only profile fields changed."})

    result = db.table("doctors").update(update).eq("id", doctor_id).execute()
    if not result.data:
        return jsonify({"error": "Update failed."}), 500
    return jsonify({"message": "Doctor updated.", "doctor": result.data[0]})


# ── DELETE /api/admin/doctors/:id ─────────────────────────────────────────────
@bp.route("/doctors/<doctor_id>", methods=["DELETE"])
@require_role("admin")
def delete_doctor(doctor_id: str, current_user, current_role):
    """
    Deactivate a doctor (soft-delete: is_active = False).
    Hard delete on ?hard=true — also removes Firebase account.
    """
    hard = request.args.get("hard", "").lower() == "true"
    db   = get_admin_supabase()

    doc = db.table("doctors").select("id, user_id, full_name").eq("id", doctor_id).single().execute()
    if not doc.data:
        return jsonify({"error": "Doctor not found."}), 404

    if hard:
        db.table("doctors").delete().eq("id", doctor_id).execute()
        # Also remove Supabase profile
        if doc.data.get("user_id"):
            db.table("profiles").delete().eq("id", doc.data["user_id"]).execute()
        return jsonify({"message": f"Doctor '{doc.data['full_name']}' permanently deleted."})

    db.table("doctors").update({"is_active": False, "is_available": False}).eq("id", doctor_id).execute()
    return jsonify({"message": f"Doctor '{doc.data['full_name']}' deactivated."})


# ── POST /api/admin/surgeries ─────────────────────────────────────────────────
@bp.route("/surgeries", methods=["POST"])
@require_role("admin")
def schedule_surgery(current_user, current_role):
    """
    Schedule a surgery for a doctor.
    Body: { doctor_id, patient_name, operation_type, surgery_date,
            surgery_time, duration_minutes, theater, notes, patient_phone }
    """
    data = request.get_json(silent=True) or {}
    required = ["doctor_id", "patient_name", "operation_type", "surgery_date", "surgery_time"]
    missing  = [f for f in required if not data.get(f)]
    if missing:
        return jsonify({"error": f"Missing: {', '.join(missing)}"}), 400

    db  = get_admin_supabase()
    row = {
        "doctor_id":        data["doctor_id"],
        "patient_name":     data["patient_name"].strip(),
        "patient_phone":    data.get("patient_phone", "").strip(),
        "operation_type":   data["operation_type"].strip(),
        "surgery_date":     data["surgery_date"],
        "surgery_time":     data["surgery_time"],
        "duration_minutes": int(data.get("duration_minutes", 120) or 120),
        "theater":          data.get("theater", "").strip(),
        "notes":            data.get("notes", "").strip(),
        "status":           "scheduled",
        "created_by":       current_user["email"],
    }
    result = db.table("surgeries").insert(row).execute()
    if not result.data:
        return jsonify({"error": "Failed to schedule surgery."}), 500

    return jsonify({"message": "Surgery scheduled.", "surgery": result.data[0]}), 201


# ── GET /api/admin/surgeries ──────────────────────────────────────────────────
@bp.route("/surgeries", methods=["GET"])
@require_role("admin")
def list_surgeries(current_user, current_role):
    """List all surgeries. Optional ?doctor_id=, ?status=, ?date_from=, ?date_to="""
    db     = get_admin_supabase()
    query  = db.table("surgeries") \
        .select("*, doctors(full_name, specialties(name))") \
        .order("surgery_date").order("surgery_time")

    if request.args.get("doctor_id"):
        query = query.eq("doctor_id", request.args["doctor_id"])
    if request.args.get("status"):
        query = query.eq("status", request.args["status"])
    if request.args.get("date_from"):
        query = query.gte("surgery_date", request.args["date_from"])
    if request.args.get("date_to"):
        query = query.lte("surgery_date", request.args["date_to"])

    result = query.execute()
    return jsonify({"surgeries": result.data or [], "count": len(result.data or [])})


# ── PUT /api/admin/surgeries/:id/status ──────────────────────────────────────
@bp.route("/surgeries/<surgery_id>/status", methods=["PUT"])
@require_role("admin")
def update_surgery_status(surgery_id: str, current_user, current_role):
    data   = request.get_json(silent=True) or {}
    status = data.get("status", "").strip()
    if status not in ("scheduled", "completed", "cancelled", "postponed"):
        return jsonify({"error": "Invalid status."}), 400
    db     = get_admin_supabase()
    result = db.table("surgeries").update({"status": status}).eq("id", surgery_id).execute()
    if not result.data:
        return jsonify({"error": "Surgery not found."}), 404
    return jsonify({"message": "Status updated.", "surgery": result.data[0]})
