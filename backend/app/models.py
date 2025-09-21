from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlmodel import Field, Relationship, SQLModel


class Company(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    timezone: str = "Asia/Kolkata"

    invoices: list["Invoice"] = Relationship(back_populates="company")
    payments: list["Payment"] = Relationship(back_populates="company")


class Invoice(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    company_id: int = Field(foreign_key="company.id")
    invoice_number: str
    customer_name: str
    customer_phone: str
    amount: float
    due_date: date
    currency: str = "INR"
    status: str = Field(default="draft", index=True)
    promise_to_pay_at: Optional[date] = Field(default=None)
    promise_note: Optional[str] = None
    last_reminder_at: Optional[datetime] = Field(default=None, index=True)

    company: Company = Relationship(back_populates="invoices")
    reminders: list["Reminder"] = Relationship(back_populates="invoice")
    payments: list["Payment"] = Relationship(back_populates="invoice")


class Reminder(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    invoice_id: int = Field(foreign_key="invoice.id")
    scheduled_for: datetime = Field(index=True)
    kind: str = Field(default="initial")
    status: str = Field(default="pending", index=True)

    invoice: Invoice = Relationship(back_populates="reminders")


class Payment(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    company_id: int = Field(foreign_key="company.id")
    invoice_id: Optional[int] = Field(default=None, foreign_key="invoice.id")
    payment_date: date
    amount: float
    reference: Optional[str] = None
    description: Optional[str] = None
    matched: bool = Field(default=False, index=True)

    invoice: Optional[Invoice] = Relationship(back_populates="payments")
    company: Company = Relationship(back_populates="payments")
