from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlmodel import Session, select

from .config import get_settings
from .models import Invoice, Reminder

SETTINGS = get_settings()

# Minimal festival calendar for the MVP. Extendable via database/config later.
FESTIVAL_DATES = {
    (1, 26),   # Republic Day
    (8, 15),   # Independence Day
    (10, 2),   # Gandhi Jayanti
    (11, 1),   # Diwali (approximate, adjust yearly)
}


def _is_festival(candidate: date) -> bool:
    return (candidate.month, candidate.day) in FESTIVAL_DATES


def _is_business_day(candidate: date) -> bool:
    # Treat Sunday as non-working; Saturday optional but included for MVP simplicity.
    return candidate.weekday() < 6 and not _is_festival(candidate)


def _combine(candidate_date: date, hour: int, tz: ZoneInfo) -> datetime:
    base = datetime.combine(candidate_date, time(hour=hour))
    return base.replace(tzinfo=tz)


def next_allowed_datetime(start: datetime, tz_name: str | None = None) -> datetime:
    tz = ZoneInfo(tz_name or SETTINGS.timezone)
    current = start.astimezone(tz)

    # Align to next allowed hour window.
    while True:
        if not _is_business_day(current.date()) or current.hour >= SETTINGS.reminder_end_hour:
            current = _combine(current.date() + timedelta(days=1), SETTINGS.reminder_start_hour, tz)
            continue
        if current.hour < SETTINGS.reminder_start_hour:
            current = current.replace(hour=SETTINGS.reminder_start_hour, minute=0, second=0, microsecond=0)
        break
    return current


def schedule_initial_reminders(invoice: Invoice, session: Session, now: datetime) -> list[Reminder]:
    tz = ZoneInfo(invoice.company.timezone if invoice.company else SETTINGS.timezone)
    planned: list[datetime] = []
    current = next_allowed_datetime(now, tz.key)
    planned.append(current)

    due_minus_one = invoice.due_date - timedelta(days=1)
    if due_minus_one >= now.date():
        planned.append(next_allowed_datetime(_combine(due_minus_one, SETTINGS.reminder_start_hour, tz), tz.key))

    planned.append(next_allowed_datetime(_combine(invoice.due_date + timedelta(days=1), SETTINGS.reminder_start_hour, tz), tz.key))
    planned.append(next_allowed_datetime(_combine(invoice.due_date + timedelta(days=4), SETTINGS.reminder_start_hour, tz), tz.key))

    reminders: list[Reminder] = []
    for idx, scheduled_for in enumerate(planned):
        reminder = Reminder(
            invoice_id=invoice.id,
            scheduled_for=scheduled_for,
            kind="initial" if idx == 0 else "follow_up",
        )
        session.add(reminder)
        reminders.append(reminder)

    invoice.status = "scheduled"
    session.add(invoice)
    return reminders


def reschedule_for_promise(invoice: Invoice, session: Session) -> Reminder:
    # Cancel pending reminders
    pending_reminders = session.exec(
        select(Reminder).where(Reminder.invoice_id == invoice.id, Reminder.status == "pending")
    ).all()
    for reminder in pending_reminders:
        reminder.status = "cancelled"
        session.add(reminder)

    if not invoice.promise_to_pay_at:
        raise ValueError("Invoice must have promise_to_pay_at before rescheduling")

    tz = ZoneInfo(invoice.company.timezone if invoice.company else SETTINGS.timezone)
    follow_up = next_allowed_datetime(_combine(invoice.promise_to_pay_at, SETTINGS.reminder_start_hour, tz), tz.key)

    reminder = Reminder(
        invoice_id=invoice.id,
        scheduled_for=follow_up,
        kind="promise_follow_up",
    )
    session.add(reminder)
    invoice.status = "waiting_for_payment"
    session.add(invoice)
    return reminder
