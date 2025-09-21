from __future__ import annotations

from datetime import date

from sqlmodel import Session

from app.models import Company, Invoice, Payment
from app.reconciliation import reconcile_payments


def test_reconcile_payments_matches_by_amount_and_date(session: Session, company: Company) -> None:
    invoice = Invoice(
        company_id=company.id,
        invoice_number="INV-100",
        customer_name="Acme",
        customer_phone="9999999999",
        amount=5000.0,
        due_date=date(2024, 8, 20),
        status="scheduled",
    )
    payment = Payment(
        company_id=company.id,
        payment_date=date(2024, 8, 21),
        amount=5000.0,
        reference="NEFT999",
        description="Invoice payment",
    )
    session.add(invoice)
    session.add(payment)
    session.commit()
    session.refresh(invoice)
    session.refresh(payment)

    matches = reconcile_payments(session, company.id)
    assert len(matches) == 1
    match_payment, match_invoice = matches[0]
    assert match_payment.invoice_id == invoice.id
    assert match_invoice.status == "paid"
