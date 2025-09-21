from __future__ import annotations

from datetime import datetime, timedelta

from sqlmodel import Session

from app import reminders
from app.models import Company, Invoice


def test_next_allowed_datetime_respects_business_hours(now: datetime) -> None:
    candidate = reminders.next_allowed_datetime(now, "Asia/Kolkata")
    assert candidate.hour == 9
    assert candidate.tzinfo is not None


def test_next_allowed_datetime_skips_festival() -> None:
    start = datetime(2024, 8, 15, 10, 0)  # Independence Day
    candidate = reminders.next_allowed_datetime(start, "Asia/Kolkata")
    assert candidate.date() == datetime(2024, 8, 16, 9, 0).date()


def test_schedule_initial_reminders_creates_followups(session: Session, company: Company, now: datetime) -> None:
    invoice = Invoice(
        company_id=company.id,
        invoice_number="INV-1",
        customer_name="Acme",
        customer_phone="9999999999",
        amount=1000.0,
        due_date=now.date() + timedelta(days=5),
    )
    session.add(invoice)
    session.commit()
    session.refresh(invoice)
    invoice.company = company

    reminders_created = reminders.schedule_initial_reminders(invoice, session, now)
    session.commit()

    assert len(reminders_created) == 4
    kinds = {rem.kind for rem in reminders_created}
    assert kinds == {"initial", "follow_up"}
