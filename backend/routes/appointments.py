"""
routes/appointments.py — Appointment booking (patient)

POST /api/appointments       book a new appointment  (login required)
GET  /api/appointments/mine  my appointments          (login required)

WHY login is required only HERE (not on the public browsing routes):
  Browsing doctors and checking slots is public — no login friction.
  Booking creates a record in the database tied to the patient's identity,
  so we need to know who is booking. The frontend should only show the
  login modal when the patient actually clicks "Confirm Booking".
"""
from flask import Blueprint, jsonify, request
from middleware.auth_middleware import require_auth
from services.appointment_service import (
    create_appointment,
    get_patient_appointments,
    update_appointment_status,
)
from services.supabase_client import get_admin_supabase
from services import email_service

bp = Blueprint("appointments", __name__)


# ── POST /api/appointments ────────────────────────────────────────────────────
@bp.route("", methods=["POST"])
@require_auth
def book_appointment(current_user, current_role):
    """
    Book an appointment.

    Body (JSON):
    {
        "doctor_id":         "<uuid>",
        "specialty_id":      "<uuid>",
        "appointment_date":  "YYYY-MM-DD",
        "appointment_time":  "HH:MM",
        "patient_name":      "Rahul Sharma",
        "patient_phone":     "+91 98765 43210",
        "notes":             "optional notes"
    }

    WHY we re-validate the slot server-side even though the frontend showed it:
    Between the patient seeing a slot and submitting the form, someone else
    might book that slot. The service layer re-checks availability before
    inserting, and the DB UNIQUE constraint is the final backstop.
    """
    data = request.get_json(silent=True) or {}

    required = ["doctor_id", "appointment_date", "appointment_time"]
    missing  = [f for f in required if not data.get(f)]
    if missing:
        return jsonify({"error": f"Missing required fields: {', '.join(missing)}"}), 400

    # Resolve specialty_id — use provided, or fall back to doctor's specialty
    specialty_id = data.get("specialty_id")
    if not specialty_id:
        db  = get_admin_supabase()
        doc = db.table("doctors").select("specialty_id") \
            .eq("id", data["doctor_id"]).single().execute()
        if not doc.data:
            return jsonify({"error": "Doctor not found."}), 404
        specialty_id = doc.data["specialty_id"]

    patient_name  = data.get("patient_name", "").strip() or current_user["name"] or current_user["email"]
    patient_email = current_user["email"]
    patient_phone = data.get("patient_phone", "").strip()

    appointment, error = create_appointment(
        patient_id       = current_user["id"],
        patient_name     = patient_name,
        patient_email    = patient_email,
        patient_phone    = patient_phone,
        doctor_id        = data["doctor_id"],
        specialty_id     = specialty_id,
        appointment_date = data["appointment_date"],
        appointment_time = data["appointment_time"],
        notes            = data.get("notes", ""),
    )

    if error:
        return jsonify({"error": error}), 400

    # Fire-and-forget confirmation email (non-blocking)
    db  = get_admin_supabase()
    doc = db.table("doctors") \
        .select("full_name, specialties(name)") \
        .eq("id", data["doctor_id"]).single().execute()
    if doc.data:
        email_service.send_appointment_booked(
            patient_email = patient_email,
            patient_name  = patient_name,
            doctor_name   = doc.data.get("full_name", "our doctor"),
            specialty     = (doc.data.get("specialties") or {}).get("name", ""),
            date          = data["appointment_date"],
            time          = data["appointment_time"],
        )

    return jsonify({"message": "Appointment booked successfully.", "appointment": appointment}), 201


# ── GET /api/appointments/mine ────────────────────────────────────────────────
@bp.route("/mine", methods=["GET"])
@require_auth
def my_appointments(current_user, current_role):
    """
    Return all appointments for the currently logged-in patient.
    Includes doctor name, specialty, and status so the patient
    dashboard can display everything without additional calls.
    """
    appointments = get_patient_appointments(current_user["id"])
    return jsonify({"appointments": appointments, "count": len(appointments)})


# ── PUT /api/appointments/:id/cancel ─────────────────────────────────────────
@bp.route("/<appointment_id>/cancel", methods=["PUT"])
@require_auth
def cancel_appointment(appointment_id: str, current_user, current_role):
    """
    Patient cancels their own appointment.
    Only pending or confirmed appointments can be cancelled.
    """
    db = get_admin_supabase()

    existing = db.table("appointments") \
        .select("id, status, patient_id") \
        .eq("id", appointment_id).single().execute()

    if not existing.data:
        return jsonify({"error": "Appointment not found."}), 404

    # Admins can cancel anything; patients only their own
    if current_role not in ("admin",) and existing.data["patient_id"] != current_user["id"]:
        return jsonify({"error": "You can only cancel your own appointments."}), 403

    if existing.data["status"] not in ("pending", "confirmed"):
        return jsonify({"error": "Only pending or confirmed appointments can be cancelled."}), 400

    appt, err = update_appointment_status(appointment_id, "cancelled")
    if err:
        return jsonify({"error": err}), 400

    return jsonify({"message": "Appointment cancelled.", "appointment": appt})
