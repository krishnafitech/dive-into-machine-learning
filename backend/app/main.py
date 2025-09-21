from __future__ import annotations

from datetime import date, datetime

from fastapi import Depends, FastAPI, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session, select

from . import reminders
from .bank_parser import BankCSVParserError, parse_bank_csv
from .config import get_settings
from .database import get_session, init_db
from .invoice_parser import InvoiceCSVParserError, parse_invoice_csv
from .models import Company, Invoice, Reminder
from .reconciliation import record_payments, reconcile_payments

app = FastAPI(title="WhatsApp Collections MVP")
settings = get_settings()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.post("/companies", response_model=Company)
def create_company(company: Company, session: Session = Depends(get_session)) -> Company:
    if company.id is not None:
        raise HTTPException(status_code=400, detail="New companies cannot specify an id")
    session.add(company)
    session.commit()
    session.refresh(company)
    return company


@app.get("/companies/{company_id}", response_model=Company)
def get_company(company_id: int, session: Session = Depends(get_session)) -> Company:
    company = session.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    return company


@app.post("/companies/{company_id}/invoices/upload")
def upload_invoices(company_id: int, file: UploadFile, session: Session = Depends(get_session)) -> dict:
    company = session.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    raw_csv = file.file.read().decode("utf-8")
    try:
        parsed_invoices = parse_invoice_csv(raw_csv)
    except InvoiceCSVParserError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    created: list[int] = []
    now = datetime.utcnow()
    for parsed in parsed_invoices:
        invoice = Invoice(
            company_id=company_id,
            invoice_number=parsed.invoice_number,
            customer_name=parsed.customer_name,
            customer_phone=parsed.customer_phone,
            amount=parsed.amount,
            due_date=parsed.due_date,
            status="draft",
        )
        session.add(invoice)
        session.commit()
        session.refresh(invoice)
        invoice.company = company
        reminders.schedule_initial_reminders(invoice, session, now)
        session.commit()
        created.append(invoice.id)
    return {"invoices_created": created}


@app.get("/companies/{company_id}/invoices", response_model=list[Invoice])
def list_invoices(company_id: int, session: Session = Depends(get_session)) -> list[Invoice]:
    invoices = session.exec(select(Invoice).where(Invoice.company_id == company_id)).all()
    return invoices


@app.get("/invoices/{invoice_id}", response_model=Invoice)
def get_invoice(invoice_id: int, session: Session = Depends(get_session)) -> Invoice:
    invoice = session.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return invoice


@app.post("/invoices/{invoice_id}/promise")
def record_promise(invoice_id: int, payload: dict[str, str], session: Session = Depends(get_session)) -> dict:
    invoice = session.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    promise_date_str = payload.get("promise_date")
    note = payload.get("note")
    if not promise_date_str:
        raise HTTPException(status_code=400, detail="promise_date is required")

    try:
        promise_date = date.fromisoformat(promise_date_str)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid promise_date format") from exc

    invoice.promise_to_pay_at = promise_date
    invoice.promise_note = note
    session.add(invoice)
    reminders.reschedule_for_promise(invoice, session)
    session.commit()
    return {"status": "snoozed_until", "promise_date": promise_date.isoformat()}


@app.post("/companies/{company_id}/bank/upload")
def upload_bank_statement(company_id: int, file: UploadFile, session: Session = Depends(get_session)) -> dict:
    company = session.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    raw_csv = file.file.read().decode("utf-8")
    try:
        parsed_payments = parse_bank_csv(raw_csv)
    except BankCSVParserError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    payments = record_payments(
        session,
        company_id,
        (
            (payment.payment_date, payment.amount, payment.reference, payment.description)
            for payment in parsed_payments
        ),
    )
    matches = reconcile_payments(session, company_id)
    return {
        "payments_ingested": [payment.id for payment in payments],
        "matches": [
            {
                "payment_id": payment.id,
                "invoice_id": invoice.id,
                "invoice_number": invoice.invoice_number,
            }
            for payment, invoice in matches
        ],
    }


@app.get("/companies/{company_id}/reminders", response_model=list[Reminder])
def list_reminders(company_id: int, session: Session = Depends(get_session)) -> list[Reminder]:
    reminders_query = session.exec(
        select(Reminder).join(Invoice).where(Invoice.company_id == company_id)
    )
    return reminders_query.all()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "timezone": settings.timezone}
