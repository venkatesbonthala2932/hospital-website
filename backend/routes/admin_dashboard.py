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
from services.analytics_service import get_visit_analytics
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
    force = bool(data.get("force"))
    leave, err, conflicts = approve_leave(
        leave_id,
        admin_note=data.get("note", ""),
        force=force,
    )
    if err:
        # 409 = conflict — admin needs to confirm with ?force
        return jsonify({"error": err, "conflicts": conflicts or []}), 409
    msg = "Leave approved. Date is now blocked."
    if conflicts:
        msg += f" {len(conflicts)} appointment(s) were auto-cancelled."
    return jsonify({"message": msg, "leave": leave, "cancelled": conflicts or []})


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
    doctors = result.data or []

    # For pre-invited doctors (no profile yet) include their pending
    # invitation email so the admin edit form can show + change it.
    invites = db.table("doctor_invitations") \
        .select("email, doctor_id, accepted_at") \
        .is_("accepted_at", "null").execute()
    invite_by_doc = {row["doctor_id"]: row["email"] for row in (invites.data or [])
                     if row.get("doctor_id")}
    for d in doctors:
        if (not d.get("profiles") or not d.get("profiles", {}).get("email")) \
           and d["id"] in invite_by_doc:
            d["pending_email"] = invite_by_doc[d["id"]]

    return jsonify({"doctors": doctors})


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

    # Mirror the role into Firebase custom claims so the frontend's JWT
    # carries it without an extra /me lookup. Best-effort: Supabase is the
    # source of truth, so we don't fail the request if this errors.
    try:
        from services.firebase_service import set_user_role
        set_user_role(user_id, new_role)
    except Exception as e:
        # Log only — the role still updated in Supabase
        print(f"[warn] Could not sync Firebase claim for {user_id}: {e}")

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
    try:
        from services.firebase_service import set_user_role
        set_user_role(user_id, "doctor")
    except Exception as e:
        print(f"[warn] Could not sync doctor role claim for {user_id}: {e}")

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

    # Mirror role into Firebase claims
    try:
        from services.firebase_service import set_user_role
        set_user_role(uid, "doctor")
    except Exception as e:
        print(f"[warn] Could not set doctor claim for {uid}: {e}")

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

    # 4. Auto-insert full-week availability (Mon-Sun, 0–6): 9:00-17:00, 30-min slots.
    #    Admin can later deactivate specific weekdays per doctor if needed.
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
        for day in range(7)
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
    # .execute() not .single() — .single() crashes if doctor doesn't exist
    doc_q = db.table("doctors").select("id, user_id, full_name").eq("id", doctor_id).execute()
    if not doc_q.data:
        return jsonify({"error": "Doctor not found."}), 404
    doc_row = doc_q.data[0]
    uid     = doc_row.get("user_id")

    # ── Handle email change (the powerful admin action) ──────────────────────
    new_email = (data.get("email") or "").strip().lower()
    if new_email:
        # 1. Make sure no other account already uses this email
        clash_profile = db.table("profiles").select("id, email, role") \
            .eq("email", new_email).execute()
        clash = [r for r in (clash_profile.data or []) if r["id"] != (uid or "")]
        if clash:
            return jsonify({
                "error": f"That email is already used by another '{clash[0]['role']}' account.",
            }), 409

        if uid:
            # Doctor has already signed in — change Firebase login email + profile
            try:
                update_firebase_user(
                    uid,
                    email=new_email,
                    display_name=data.get("full_name") or doc_row["full_name"],
                )
            except ValueError as e:
                return jsonify({"error": f"Firebase rejected the email: {e}"}), 400
            db.table("profiles").update({"email": new_email}).eq("id", uid).execute()
        else:
            # Doctor was only invited (no Firebase account yet) — update the
            # invitation so the email-only auth flow recognises the new address.
            try:
                # Find the existing invitation row and move it to the new email.
                inv = db.table("doctor_invitations").select("email, accepted_at") \
                    .eq("doctor_id", doctor_id).execute()
                if inv.data and not inv.data[0].get("accepted_at"):
                    old_email = inv.data[0]["email"]
                    # Re-key the invitation: delete old + insert new
                    db.table("doctor_invitations").delete().eq("email", old_email).execute()
                    db.table("doctor_invitations").insert({
                        "email":      new_email,
                        "doctor_id":  doctor_id,
                        "invited_by": None,  # Firebase UIDs aren't UUIDs — see ALTER in invitations_fix.sql to enable audit
                    }).execute()
                else:
                    # No pending invite — create one so the new email can sign in
                    db.table("doctor_invitations").upsert({
                        "email":      new_email,
                        "doctor_id":  doctor_id,
                        "invited_by": None,  # Firebase UIDs aren't UUIDs — see ALTER in invitations_fix.sql to enable audit
                    }, on_conflict="email").execute()
            except Exception as e:
                return jsonify({"error": f"Could not update invitation: {e}"}), 400

    # ── Sync display_name to Firebase if name changed ────────────────────────
    if "full_name" in update and uid:
        try:
            update_firebase_user(uid, display_name=update["full_name"])
        except ValueError:
            pass  # display_name sync is best-effort
        # Keep profile name in sync too
        db.table("profiles").update({"full_name": update["full_name"]}).eq("id", uid).execute()

    # ── Apply doctor-table updates ──────────────────────────────────────────
    if not update:
        return jsonify({
            "message": "Doctor updated." if new_email else "No changes detected.",
            "email_changed": bool(new_email),
        })

    result = db.table("doctors").update(update).eq("id", doctor_id).execute()
    if not result.data:
        return jsonify({"error": "Update failed."}), 500
    return jsonify({
        "message": "Doctor updated.",
        "doctor":  result.data[0],
        "email_changed": bool(new_email),
    })


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


# ── GET /api/admin/site-settings ─────────────────────────────────────────────
@bp.route("/site-settings", methods=["GET"])
@require_role("admin")
def admin_get_site_settings(current_user, current_role):
    """Return all site settings with full metadata for the admin CMS editor."""
    db = get_admin_supabase()
    result = db.table("site_settings") \
        .select("key, value, label, group_name, input_type") \
        .order("group_name").execute()
    return jsonify({"settings": result.data or []})


# ── PUT /api/admin/site-settings ─────────────────────────────────────────────
@bp.route("/site-settings", methods=["PUT"])
@require_role("admin")
def admin_update_site_settings(current_user, current_role):
    """
    Upsert one or more site settings.
    Body: { "settings": { "hospital_name": "New Name", ... } }
    """
    data    = request.get_json(silent=True) or {}
    updates = data.get("settings", {})
    if not updates:
        return jsonify({"error": "No settings provided."}), 400
    db   = get_admin_supabase()
    rows = [{"key": k, "value": str(v)} for k, v in updates.items()]
    db.table("site_settings").upsert(rows, on_conflict="key").execute()
    return jsonify({"message": f"Updated {len(rows)} setting(s).", "updated": list(updates.keys())})


# ── GET /api/admin/analytics ──────────────────────────────────────────────────
@bp.route("/analytics", methods=["GET"])
@require_role("admin")
def admin_analytics(current_user, current_role):
    """
    Hospital-wide visit analytics for the admin dashboard.
    Counts every non-cancelled / non-rejected appointment across all doctors.
    """
    return jsonify(get_visit_analytics(doctor_id=None))


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC HOLIDAYS
# ─────────────────────────────────────────────────────────────────────────────

@bp.route("/holidays", methods=["GET"])
@require_role("admin")
def list_holidays(current_user, current_role):
    """Return all upcoming + recent public holidays."""
    db = get_admin_supabase()
    result = db.table("public_holidays") \
        .select("id, holiday_date, name, description") \
        .order("holiday_date").execute()
    return jsonify({"holidays": result.data or []})


@bp.route("/holidays", methods=["POST"])
@require_role("admin")
def add_holiday(current_user, current_role):
    """
    Add a hospital-wide closure date.
    Body: { "holiday_date": "YYYY-MM-DD", "name": "Diwali", "description": "..." }
    """
    data        = request.get_json(silent=True) or {}
    holiday_date = (data.get("holiday_date") or "").strip()
    name        = (data.get("name") or "").strip()
    description = (data.get("description") or "").strip()

    if not holiday_date or not name:
        return jsonify({"error": "holiday_date and name are required."}), 400

    db = get_admin_supabase()
    try:
        result = db.table("public_holidays").insert({
            "holiday_date": holiday_date,
            "name":         name,
            "description":  description or None,
        }).execute()
    except Exception as e:
        # Most likely a unique-constraint violation
        return jsonify({"error": f"Could not add holiday: {e}"}), 400

    return jsonify({"message": "Holiday added.", "holiday": result.data[0]}), 201


@bp.route("/holidays/<holiday_id>", methods=["DELETE"])
@require_role("admin")
def delete_holiday(holiday_id: str, current_user, current_role):
    """Remove a hospital-wide closure."""
    db = get_admin_supabase()
    db.table("public_holidays").delete().eq("id", holiday_id).execute()
    return jsonify({"message": "Holiday removed."})


# ─────────────────────────────────────────────────────────────────────────────
# DOCTOR INVITATIONS — admin pre-authorises a doctor by email so they can
# sign in with Google / email & get promoted to 'doctor' automatically.
# ─────────────────────────────────────────────────────────────────────────────

@bp.route("/doctor-invites", methods=["GET"])
@require_role("admin")
def list_doctor_invites(current_user, current_role):
    """Return all pending + accepted invitations with the linked doctor info."""
    db = get_admin_supabase()
    result = db.table("doctor_invitations") \
        .select("email, doctor_id, accepted_at, created_at, "
                "doctors(id, full_name, title, specialty_id, "
                "       specialties(name, slug))") \
        .order("created_at", desc=True).execute()
    return jsonify({"invitations": result.data or []})


@bp.route("/doctor-invites", methods=["POST"])
@require_role("admin")
def create_doctor_invite(current_user, current_role):
    """
    Pre-authorise a doctor by email. Creates a placeholder doctor row that
    will be linked to the Firebase UID the first time this email signs in.

    Body: { email, full_name, specialty_id, title?, qualifications?,
            experience_years?, consultation_fee?, bio?, photo_url? }
    """
    import traceback
    data = request.get_json(silent=True) or {}
    email   = (data.get("email") or "").strip().lower()
    name    = (data.get("full_name") or "").strip()
    spec_id = (data.get("specialty_id") or "").strip()
    if not email or not name or not spec_id:
        return jsonify({"error": "email, full_name, and specialty_id are required."}), 400

    db = get_admin_supabase()

    try:
        # If invitation already exists, reject (admin can DELETE first)
        existing = db.table("doctor_invitations").select("email, accepted_at") \
            .eq("email", email).execute()
        if existing.data:
            row = existing.data[0]
            if row.get("accepted_at"):
                return jsonify({"error": "This email has already been onboarded as a doctor."}), 409
            return jsonify({"error": "An invitation for this email is already pending."}), 409

        # Also reject if the email already belongs to an active doctor or admin
        existing_profile = db.table("profiles").select("id, email, role") \
            .eq("email", email).execute()
        if existing_profile.data and existing_profile.data[0].get("role") in ("doctor", "admin"):
            return jsonify({"error": f"This email already has '{existing_profile.data[0]['role']}' role."}), 409

        # Create placeholder doctor row (user_id will be filled on first login).
        # Some columns have NOT NULL constraints in the older schema — never
        # pass actual None for them; use empty string as a safe default.
        doctor_row = {
            "user_id":          None,
            "specialty_id":     spec_id,
            "full_name":        name,
            "title":            data.get("title", "").strip() or "—",
            "qualifications":   data.get("qualifications", "").strip() or "—",
            "experience_years": int(data.get("experience_years", 0) or 0),
            "consultation_fee": float(data.get("consultation_fee", 0) or 0),
            "bio":              data.get("bio", "").strip(),
            "is_active":        True,
            "is_available":     True,
        }
        photo = (data.get("photo_url") or "").strip()
        if photo:
            doctor_row["photo_url"] = photo

        try:
            result = db.table("doctors").insert(doctor_row).execute()
        except Exception as e:
            # Most likely cause: doctors.user_id is still NOT NULL because the
            # migration in doctor_invitations_schema.sql wasn't run yet.
            print(f"[error] doctor insert failed: {e}")
            msg = str(e)
            if "user_id" in msg and "not-null" in msg:
                return jsonify({
                    "error": "Schema not migrated. Run backend/doctor_invitations_schema.sql in Supabase SQL Editor first.",
                }), 400
            return jsonify({"error": f"Could not create doctor record: {e}"}), 400
        if not result.data:
            return jsonify({"error": "Failed to create doctor record."}), 500

        new_doctor_id = result.data[0]["id"]

        # Auto-seed 7-day availability (admin can disable per weekday later)
        avail_rows = [{
            "doctor_id":             new_doctor_id,
            "day_of_week":           day,
            "start_time":            "09:00",
            "end_time":              "17:00",
            "slot_duration_minutes": 30,
            "is_active":             True,
        } for day in range(7)]
        try:
            db.table("doctor_availability").insert(avail_rows).execute()
        except Exception as e:
            print(f"[warn] availability seed failed: {e}")

        # Insert invitation
        try:
            db.table("doctor_invitations").insert({
                "email":      email,
                "doctor_id":  new_doctor_id,
                "invited_by": None,  # Firebase UIDs aren't UUIDs — see ALTER in invitations_fix.sql to enable audit
            }).execute()
        except Exception as e:
            # Rollback the doctor row we just created so admin can retry cleanly
            db.table("doctors").delete().eq("id", new_doctor_id).execute()
            print(f"[error] invitation insert failed: {e}")
            if "doctor_invitations" in str(e):
                return jsonify({
                    "error": "doctor_invitations table missing. Run backend/doctor_invitations_schema.sql in Supabase SQL Editor.",
                }), 400
            return jsonify({"error": f"Could not save invitation: {e}"}), 400

        # If the email already has a profile (e.g. patient account), promote them now
        if existing_profile.data:
            existing_uid = existing_profile.data[0]["id"]
            try:
                _accept_invitation(db, email, existing_uid, name)
            except Exception as e:
                print(f"[warn] auto-promote failed: {e}")
            return jsonify({
                "message": "Doctor invited and promoted (account already existed).",
                "doctor":  result.data[0],
            }), 201

        return jsonify({
            "message": "Doctor invited. They can sign in with Google or email to activate.",
            "doctor":  result.data[0],
        }), 201

    except Exception as e:
        print(f"[error] create_doctor_invite crashed: {e}\n{traceback.format_exc()}")
        return jsonify({"error": f"Server error: {e}"}), 500


@bp.route("/doctor-invites/<email>", methods=["DELETE"])
@require_role("admin")
def cancel_doctor_invite(email: str, current_user, current_role):
    """Cancel a pending invitation. Also deletes the placeholder doctor row."""
    email = email.strip().lower()
    db    = get_admin_supabase()

    invite = db.table("doctor_invitations").select("email, doctor_id, accepted_at") \
        .eq("email", email).execute()
    if not invite.data:
        return jsonify({"error": "Invitation not found."}), 404
    if invite.data[0].get("accepted_at"):
        return jsonify({"error": "Cannot cancel — invitation has already been accepted."}), 409

    doc_id = invite.data[0].get("doctor_id")
    db.table("doctor_invitations").delete().eq("email", email).execute()
    if doc_id:
        # Only delete the placeholder row if it was never linked to a user
        db.table("doctors").delete().eq("id", doc_id).is_("user_id", "null").execute()
    return jsonify({"message": "Invitation cancelled."})


def _accept_invitation(db, email: str, uid: str, display_name: str = ""):
    """
    Promote a user to 'doctor': link the placeholder doctor row to their UID,
    set their profile role to 'doctor', set the Firebase custom claim,
    and mark the invitation as accepted.

    Returns the doctor row, or None if no invitation existed.
    """
    invite = db.table("doctor_invitations").select("email, doctor_id, accepted_at") \
        .eq("email", email).execute()
    if not invite.data:
        return None
    if invite.data[0].get("accepted_at"):
        return None  # already used

    doctor_id = invite.data[0]["doctor_id"]
    # Link the doctor row to this Firebase UID
    db.table("doctors").update({"user_id": uid}).eq("id", doctor_id).execute()
    # Promote profile role
    db.table("profiles").update({"role": "doctor", "full_name": display_name or email}) \
        .eq("id", uid).execute()
    # Set Firebase custom claim so the JWT carries the role
    try:
        from services.firebase_service import set_user_role
        set_user_role(uid, "doctor")
    except Exception as e:
        print(f"[warn] Could not set doctor claim for {uid}: {e}")
    # Mark invitation accepted
    db.table("doctor_invitations").update({"accepted_at": "now()"}).eq("email", email).execute()

    doc = db.table("doctors").select("*").eq("id", doctor_id).single().execute()
    return doc.data


# ─────────────────────────────────────────────────────────────────────────────
# ADMIN MANAGEMENT — create/change admins, list current admins, invite by email
# ─────────────────────────────────────────────────────────────────────────────

@bp.route("/users/lookup", methods=["GET"])
@require_role("admin")
def lookup_user_by_email(current_user, current_role):
    """
    Find a user by email. Returns the profile + (if applicable) doctor row.
    Used by the admin "Manage Access" UI to show what role someone has before
    promoting / demoting them.
    """
    email = (request.args.get("email") or "").strip().lower()
    if not email:
        return jsonify({"error": "email query param is required."}), 400
    db = get_admin_supabase()
    profile = db.table("profiles") \
        .select("id, email, full_name, role, created_at, phone") \
        .eq("email", email).execute()
    if not profile.data:
        return jsonify({"found": False, "email": email}), 200
    p = profile.data[0]
    extra = {}
    if p["role"] == "doctor":
        doc = db.table("doctors").select("id, full_name, title") \
            .eq("user_id", p["id"]).execute()
        if doc.data:
            extra["doctor"] = doc.data[0]
    return jsonify({"found": True, "user": p, **extra})


@bp.route("/admins", methods=["GET"])
@require_role("admin")
def list_admins(current_user, current_role):
    """List every account currently holding the 'admin' role."""
    db = get_admin_supabase()
    result = db.table("profiles") \
        .select("id, email, full_name, created_at") \
        .eq("role", "admin").order("created_at").execute()
    return jsonify({"admins": result.data or []})


@bp.route("/admin-invites", methods=["GET"])
@require_role("admin")
def list_admin_invites(current_user, current_role):
    """List pending admin invitations."""
    db = get_admin_supabase()
    result = db.table("admin_invitations") \
        .select("email, accepted_at, created_at") \
        .is_("accepted_at", "null") \
        .order("created_at", desc=True).execute()
    return jsonify({"invitations": result.data or []})


@bp.route("/admin-invites", methods=["POST"])
@require_role("admin")
def create_admin_invite(current_user, current_role):
    """
    Invite a new admin by email. If the email already has an account,
    promote them to admin immediately. Otherwise insert a pending invitation
    that auto-activates the next time they sign in.

    Body: { "email": "new@admin.com" }
    """
    data  = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    if not email:
        return jsonify({"error": "email is required."}), 400

    db = get_admin_supabase()

    # If user already exists → promote immediately
    profile = db.table("profiles").select("id, role, full_name") \
        .eq("email", email).execute()
    if profile.data:
        uid       = profile.data[0]["id"]
        full_name = profile.data[0].get("full_name", "")
        cur_role  = profile.data[0].get("role")
        if cur_role == "admin":
            return jsonify({"message": "This user is already an admin."}), 200
        db.table("profiles").update({"role": "admin"}).eq("id", uid).execute()
        try:
            from services.firebase_service import set_user_role
            set_user_role(uid, "admin")
        except Exception as e:
            print(f"[warn] could not set admin claim for {uid}: {e}")
        return jsonify({
            "message": f"{full_name or email} promoted to admin. They must sign out and back in for the change to take effect.",
            "promoted_immediately": True,
        }), 200

    # Otherwise create a pending invitation
    existing = db.table("admin_invitations").select("email, accepted_at") \
        .eq("email", email).execute()
    if existing.data and not existing.data[0].get("accepted_at"):
        return jsonify({"error": "An admin invitation for this email is already pending."}), 409

    db.table("admin_invitations").upsert({
        "email":      email,
        "invited_by": None,  # Firebase UIDs aren't UUIDs — see ALTER in invitations_fix.sql to enable audit
        "accepted_at": None,
    }, on_conflict="email").execute()
    return jsonify({
        "message": "Admin invitation sent. They'll become admin on first sign-in.",
        "promoted_immediately": False,
    }), 201


@bp.route("/admin-invites/<email>", methods=["DELETE"])
@require_role("admin")
def cancel_admin_invite(email: str, current_user, current_role):
    """Cancel a pending admin invitation."""
    email = email.strip().lower()
    db = get_admin_supabase()
    invite = db.table("admin_invitations").select("email, accepted_at") \
        .eq("email", email).execute()
    if not invite.data:
        return jsonify({"error": "Invitation not found."}), 404
    if invite.data[0].get("accepted_at"):
        return jsonify({"error": "Already accepted — demote via 'Change Role' instead."}), 409
    db.table("admin_invitations").delete().eq("email", email).execute()
    return jsonify({"message": "Invitation cancelled."})


@bp.route("/admins/<user_id>", methods=["DELETE"])
@require_role("admin")
def demote_admin(user_id: str, current_user, current_role):
    """
    Revoke admin privileges. The user is demoted to 'patient'.
    Safety: an admin cannot demote themselves.
    """
    if user_id == current_user["id"]:
        return jsonify({"error": "You cannot revoke your own admin access."}), 400

    db = get_admin_supabase()
    profile = db.table("profiles").select("id, role, email, full_name") \
        .eq("id", user_id).execute()
    if not profile.data:
        return jsonify({"error": "User not found."}), 404
    if profile.data[0]["role"] != "admin":
        return jsonify({"error": "This user is not an admin."}), 400

    # Make sure we're never left with zero admins
    count = db.table("profiles").select("id", count="exact").eq("role", "admin").execute()
    if (count.count or 0) <= 1:
        return jsonify({"error": "Cannot demote — at least one admin must remain."}), 400

    db.table("profiles").update({"role": "patient"}).eq("id", user_id).execute()
    try:
        from services.firebase_service import set_user_role
        set_user_role(user_id, "patient")
    except Exception as e:
        print(f"[warn] could not reset claim for {user_id}: {e}")
    return jsonify({"message": f"{profile.data[0].get('email')} is no longer an admin."})
