from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date
from io import StringIO


@dataclass
class ParsedInvoice:
    invoice_number: str
    customer_name: str
    customer_phone: str
    amount: float
    due_date: date


REQUIRED_COLUMNS = {
    "invoice_number",
    "customer_name",
    "customer_phone",
    "amount",
    "due_date",
}


class InvoiceCSVParserError(ValueError):
    """Raised when the incoming CSV payload cannot be parsed."""


def parse_invoice_csv(raw_csv: str) -> list[ParsedInvoice]:
    """Parse a CSV string exported from Zoho/Tally/Vyapar into invoices.

    The MVP expects a header row with at least the required columns. Dates must be
    provided in ISO format (YYYY-MM-DD)."""

    reader = csv.DictReader(StringIO(raw_csv))
    if reader.fieldnames is None:
        raise InvoiceCSVParserError("Missing CSV header row")

    missing = REQUIRED_COLUMNS - set(col.strip().lower() for col in reader.fieldnames)
    if missing:
        raise InvoiceCSVParserError(f"CSV missing required columns: {', '.join(sorted(missing))}")

    invoices: list[ParsedInvoice] = []
    for idx, row in enumerate(reader, start=2):
        try:
            invoice_number = row["invoice_number"].strip()
            customer_name = row["customer_name"].strip()
            customer_phone = row["customer_phone"].strip()
            amount = float(row["amount"].strip())
            due_date = date.fromisoformat(row["due_date"].strip())
        except Exception as exc:  # noqa: BLE001 - convert to parser error
            raise InvoiceCSVParserError(f"Row {idx} is invalid: {exc}") from exc

        invoices.append(
            ParsedInvoice(
                invoice_number=invoice_number,
                customer_name=customer_name,
                customer_phone=customer_phone,
                amount=amount,
                due_date=due_date,
            )
        )

    return invoices
