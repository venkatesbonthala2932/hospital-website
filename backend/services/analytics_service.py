"""
services/analytics_service.py — Patient visit analytics

Used by admin + doctor dashboards to show visit volume over different
periods (today, this week, this month, this year) with comparisons to
the previous equivalent period.

A "visit" here = any appointment that hasn't been cancelled or rejected.
Status values counted: pending, confirmed, completed.
"""
from datetime import date, timedelta
from services.supabase_client import get_admin_supabase

VISIT_STATUSES = ["pending", "confirmed", "completed"]


def _count(db, date_from: date, date_to: date, doctor_id: str | None = None) -> int:
    """
    Count visits between date_from and date_to (inclusive).
    Optionally scoped to a single doctor.
    """
    q = db.table("appointments").select("id", count="exact")
    q = q.gte("appointment_date", date_from.isoformat())
    q = q.lte("appointment_date", date_to.isoformat())
    q = q.in_("status", VISIT_STATUSES)
    if doctor_id:
        q = q.eq("doctor_id", doctor_id)
    r = q.execute()
    return r.count or 0


def _trend_14d(db, doctor_id: str | None = None) -> list[dict]:
    """Return one row per day for the last 14 days: { date, count }."""
    today = date.today()
    start = today - timedelta(days=13)
    q = db.table("appointments") \
        .select("appointment_date") \
        .gte("appointment_date", start.isoformat()) \
        .lte("appointment_date", today.isoformat()) \
        .in_("status", VISIT_STATUSES)
    if doctor_id:
        q = q.eq("doctor_id", doctor_id)
    rows = q.execute().data or []

    buckets = {(start + timedelta(days=i)).isoformat(): 0 for i in range(14)}
    for r in rows:
        d = r.get("appointment_date", "")
        if d in buckets:
            buckets[d] += 1
    return [{"date": d, "count": c} for d, c in buckets.items()]


def get_visit_analytics(doctor_id: str | None = None) -> dict:
    """
    Build the full analytics payload.

    Returns visit counts for:
      today, yesterday
      this_week, last_week
      this_month, last_month
      this_year, last_year
      all_time
      trend_14d  — list of {date, count} for a small bar chart

    If doctor_id is supplied, all numbers are scoped to that doctor.
    """
    db = get_admin_supabase()
    today = date.today()

    # ── Day ──────────────────────────────────────────────────────────────────
    yesterday = today - timedelta(days=1)

    # ── Week (Mon-Sun) ───────────────────────────────────────────────────────
    week_start = today - timedelta(days=today.weekday())
    last_week_end   = week_start - timedelta(days=1)
    last_week_start = last_week_end - timedelta(days=6)

    # ── Month ────────────────────────────────────────────────────────────────
    month_start = today.replace(day=1)
    last_month_end = month_start - timedelta(days=1)
    last_month_start = last_month_end.replace(day=1)

    # ── Year ─────────────────────────────────────────────────────────────────
    year_start      = date(today.year, 1, 1)
    last_year_end   = date(today.year - 1, 12, 31)
    last_year_start = date(today.year - 1, 1, 1)

    far_past = date(2000, 1, 1)

    return {
        "today":      _count(db, today, today, doctor_id),
        "yesterday":  _count(db, yesterday, yesterday, doctor_id),
        "this_week":  _count(db, week_start, today, doctor_id),
        "last_week":  _count(db, last_week_start, last_week_end, doctor_id),
        "this_month": _count(db, month_start, today, doctor_id),
        "last_month": _count(db, last_month_start, last_month_end, doctor_id),
        "this_year":  _count(db, year_start, today, doctor_id),
        "last_year":  _count(db, last_year_start, last_year_end, doctor_id),
        "all_time":   _count(db, far_past, today, doctor_id),
        "trend_14d":  _trend_14d(db, doctor_id),
        "as_of":      today.isoformat(),
    }
