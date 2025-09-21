from __future__ import annotations

from datetime import date, timedelta
from typing import Iterable

from sqlmodel import Session, select

from .models import Invoice, Payment


MATCH_WINDOW_DAYS = 2
AMOUNT_TOLERANCE = 1.0


def _is_amount_match(invoice: Invoice, payment: Payment) -> bool:
    return abs(invoice.amount - payment.amount) <= AMOUNT_TOLERANCE


def _is_date_match(invoice: Invoice, payment: Payment) -> bool:
    lower = invoice.due_date - timedelta(days=MATCH_WINDOW_DAYS)
    upper = invoice.due_date + timedelta(days=MATCH_WINDOW_DAYS)
    return lower <= payment.payment_date <= upper


def reconcile_payments(session: Session, company_id: int) -> list[tuple[Payment, Invoice]]:
    invoices = session.exec(
        select(Invoice).where(Invoice.company_id == company_id, Invoice.status != "paid")
    ).all()
    payments = session.exec(
        select(Payment).where(Payment.company_id == company_id, Payment.matched.is_(False)).order_by(Payment.payment_date)
    ).all()

    matches: list[tuple[Payment, Invoice]] = []
    for payment in payments:
        candidate = next(
            (
                invoice
                for invoice in invoices
                if _is_amount_match(invoice, payment) and _is_date_match(invoice, payment)
            ),
            None,
        )
        if candidate:
            payment.invoice_id = candidate.id
            payment.matched = True
            candidate.status = "paid"
            session.add(payment)
            session.add(candidate)
            matches.append((payment, candidate))
    session.commit()
    return matches


def record_payments(
    session: Session,
    company_id: int,
    payments: Iterable[tuple[date, float, str | None, str | None]],
) -> list[Payment]:
    stored: list[Payment] = []
    for payment_date, amount, reference, description in payments:
        payment = Payment(
            company_id=company_id,
            payment_date=payment_date,
            amount=amount,
            reference=reference,
            description=description,
        )
        session.add(payment)
        stored.append(payment)
    session.commit()
    for payment in stored:
        session.refresh(payment)
    return stored
