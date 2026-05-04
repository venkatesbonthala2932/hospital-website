"""
services/email_service.py — Transactional email notifications

Uses standard SMTP (works with Gmail, Zoho, SendGrid SMTP relay, etc.).
All sending is fire-and-forget in a background thread so the API
response is never delayed by email latency.

Required .env keys (if any are missing, emails are silently skipped):
  SMTP_HOST     = smtp.gmail.com
  SMTP_PORT     = 587
  SMTP_USER     = noreply@yourdomain.com
  SMTP_PASS     = your-app-password
  FROM_EMAIL    = Aadityaa Hospital <noreply@yourdomain.com>

For Gmail: create an App Password at myaccount.google.com/apppasswords
(requires 2-step verification to be enabled on the account).
"""
import smtplib
import threading
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from config import Config

log = logging.getLogger(__name__)


def _send_async(msg: MIMEMultipart) -> None:
    """Send an email in a background thread — never raises."""
    try:
        with smtplib.SMTP(Config.SMTP_HOST, Config.SMTP_PORT, timeout=10) as s:
            s.ehlo()
            s.starttls()
            s.login(Config.SMTP_USER, Config.SMTP_PASS)
            s.sendmail(Config.FROM_EMAIL, msg["To"], msg.as_string())
        log.info("Email sent to %s", msg["To"])
    except Exception as exc:
        log.warning("Email failed (non-fatal): %s", exc)


def send_email(to: str, subject: str, html_body: str, text_body: str = "") -> None:
    """
    Queue an email for async delivery.
    No-op if SMTP is not configured.
    """
    if not Config.email_enabled():
        log.debug("Email skipped (SMTP not configured): %s → %s", to, subject)
        return

    msg             = MIMEMultipart("alternative")
    msg["Subject"]  = subject
    msg["From"]     = Config.FROM_EMAIL
    msg["To"]       = to

    if text_body:
        msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    threading.Thread(target=_send_async, args=(msg,), daemon=True).start()


# ── Template helpers ──────────────────────────────────────────────────────────

def _base_template(content: str) -> str:
    return f"""
    <html><body style="margin:0;padding:0;background:#f5fafa;font-family:Inter,Arial,sans-serif;">
      <table width="100%" cellpadding="0" cellspacing="0">
        <tr><td align="center" style="padding:40px 20px;">
          <table width="560" cellpadding="0" cellspacing="0"
                 style="background:#ffffff;border-radius:16px;overflow:hidden;
                        box-shadow:0 4px 24px rgba(0,0,0,0.07);">
            <!-- Header -->
            <tr><td style="background:#006d77;padding:28px 36px;">
              <span style="color:#ffffff;font-size:22px;font-weight:800;letter-spacing:-0.5px;">
                Aadityaa Hospital
              </span>
            </td></tr>
            <!-- Body -->
            <tr><td style="padding:36px;">
              {content}
            </td></tr>
            <!-- Footer -->
            <tr><td style="padding:20px 36px;border-top:1px solid #e4e9e9;
                           background:#f5fafa;font-size:11px;color:#6f797a;">
              Aadityaa Hospital · PI/466, 8, ZP Rd, Hastinapuram, Hyderabad 500070<br>
              This is an automated message. Please do not reply.
            </td></tr>
          </table>
        </td></tr>
      </table>
    </body></html>"""


def send_appointment_booked(patient_email: str, patient_name: str,
                             doctor_name: str, specialty: str,
                             date: str, time: str) -> None:
    """Sent to patient immediately after booking (status = pending)."""
    content = f"""
      <h2 style="color:#171d1d;font-size:22px;margin:0 0 8px;">
        Appointment Request Received
      </h2>
      <p style="color:#3e494a;margin:0 0 24px;">Hi {patient_name},</p>
      <p style="color:#3e494a;margin:0 0 24px;">
        Your appointment request has been received and is awaiting confirmation
        from our team. You will receive another email once it is confirmed.
      </p>
      <table style="background:#eaefef;border-radius:12px;padding:20px 24px;
                    width:100%;border-collapse:collapse;margin-bottom:24px;">
        <tr>
          <td style="color:#6f797a;font-size:13px;padding:4px 0;">Doctor</td>
          <td style="font-weight:600;color:#171d1d;font-size:13px;padding:4px 0;
                     text-align:right;">{doctor_name}</td>
        </tr>
        <tr>
          <td style="color:#6f797a;font-size:13px;padding:4px 0;">Specialty</td>
          <td style="font-weight:600;color:#171d1d;font-size:13px;padding:4px 0;
                     text-align:right;">{specialty}</td>
        </tr>
        <tr>
          <td style="color:#6f797a;font-size:13px;padding:4px 0;">Date</td>
          <td style="font-weight:600;color:#171d1d;font-size:13px;padding:4px 0;
                     text-align:right;">{date}</td>
        </tr>
        <tr>
          <td style="color:#6f797a;font-size:13px;padding:4px 0;">Time</td>
          <td style="font-weight:600;color:#171d1d;font-size:13px;padding:4px 0;
                     text-align:right;">{time}</td>
        </tr>
      </table>
      <p style="color:#3e494a;font-size:13px;margin:0;">
        If you have questions, call us at
        <a href="tel:+914012345678" style="color:#00535b;">+91 40 1234 5678</a>.
      </p>"""

    send_email(
        to       = patient_email,
        subject  = f"Appointment Request — {doctor_name} on {date}",
        html_body= _base_template(content),
        text_body= (f"Hi {patient_name},\n\nYour appointment request with {doctor_name} "
                    f"({specialty}) on {date} at {time} has been received and is pending confirmation.\n\n"
                    f"Aadityaa Hospital · +91 40 1234 5678"),
    )


def send_appointment_confirmed(patient_email: str, patient_name: str,
                                doctor_name: str, specialty: str,
                                date: str, time: str) -> None:
    """Sent to patient when admin confirms the appointment."""
    content = f"""
      <h2 style="color:#171d1d;font-size:22px;margin:0 0 8px;">
        ✓ Appointment Confirmed
      </h2>
      <p style="color:#3e494a;margin:0 0 24px;">Hi {patient_name},</p>
      <p style="color:#3e494a;margin:0 0 24px;">
        Great news! Your appointment has been <strong>confirmed</strong>.
        Please arrive 10 minutes early with a valid ID and any prior reports.
      </p>
      <table style="background:#eaefef;border-radius:12px;padding:20px 24px;
                    width:100%;border-collapse:collapse;margin-bottom:24px;">
        <tr>
          <td style="color:#6f797a;font-size:13px;padding:4px 0;">Doctor</td>
          <td style="font-weight:600;color:#171d1d;font-size:13px;padding:4px 0;
                     text-align:right;">{doctor_name}</td>
        </tr>
        <tr>
          <td style="color:#6f797a;font-size:13px;padding:4px 0;">Specialty</td>
          <td style="font-weight:600;color:#171d1d;font-size:13px;padding:4px 0;
                     text-align:right;">{specialty}</td>
        </tr>
        <tr>
          <td style="color:#6f797a;font-size:13px;padding:4px 0;">Date</td>
          <td style="font-weight:600;color:#00535b;font-size:13px;padding:4px 0;
                     text-align:right;font-weight:700;">{date}</td>
        </tr>
        <tr>
          <td style="color:#6f797a;font-size:13px;padding:4px 0;">Time</td>
          <td style="font-weight:700;color:#00535b;font-size:13px;padding:4px 0;
                     text-align:right;">{time}</td>
        </tr>
      </table>
      <a href="http://localhost:8080/patient-dashboard.html"
         style="display:inline-block;background:#006d77;color:#ffffff;
                font-weight:700;font-size:14px;padding:14px 28px;
                border-radius:50px;text-decoration:none;margin-bottom:24px;">
        View My Appointments
      </a>
      <p style="color:#3e494a;font-size:13px;margin:0;">
        To cancel or reschedule, please call
        <a href="tel:+914012345678" style="color:#00535b;">+91 40 1234 5678</a>.
      </p>"""

    send_email(
        to       = patient_email,
        subject  = f"Confirmed: Appointment with {doctor_name} on {date}",
        html_body= _base_template(content),
        text_body= (f"Hi {patient_name},\n\nYour appointment with {doctor_name} "
                    f"({specialty}) on {date} at {time} is CONFIRMED.\n\n"
                    f"Please arrive 10 minutes early with a valid ID.\n\n"
                    f"Aadityaa Hospital · +91 40 1234 5678"),
    )


def send_appointment_rejected(patient_email: str, patient_name: str,
                               doctor_name: str, date: str,
                               reason: str = "") -> None:
    """Sent to patient when admin rejects the appointment."""
    reason_html = f'<p style="color:#3e494a;margin:0 0 16px;">Reason: <em>{reason}</em></p>' if reason else ""
    content = f"""
      <h2 style="color:#171d1d;font-size:22px;margin:0 0 8px;">
        Appointment Update
      </h2>
      <p style="color:#3e494a;margin:0 0 16px;">Hi {patient_name},</p>
      <p style="color:#3e494a;margin:0 0 16px;">
        Unfortunately, your appointment request with <strong>{doctor_name}</strong>
        on <strong>{date}</strong> could not be confirmed at this time.
      </p>
      {reason_html}
      <p style="color:#3e494a;margin:0 0 24px;">
        Please book a new appointment or call us and we'll help you find an
        alternative slot.
      </p>
      <a href="http://localhost:8080/doctors.html"
         style="display:inline-block;background:#006d77;color:#ffffff;
                font-weight:700;font-size:14px;padding:14px 28px;
                border-radius:50px;text-decoration:none;">
        Book Again
      </a>"""

    send_email(
        to       = patient_email,
        subject  = f"Appointment Update — Aadityaa Hospital",
        html_body= _base_template(content),
        text_body= (f"Hi {patient_name},\n\nUnfortunately your appointment with "
                    f"{doctor_name} on {date} could not be confirmed.\n"
                    f"{f'Reason: {reason}' if reason else ''}\n\n"
                    f"Please book again at our website or call +91 40 1234 5678."),
    )
