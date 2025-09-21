from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date
from io import StringIO


@dataclass
class ParsedPayment:
    payment_date: date
    amount: float
    reference: str | None
    description: str | None


REQUIRED_COLUMNS = {
    "date",
    "amount",
}


class BankCSVParserError(ValueError):
    """Raised when bank statement CSV parsing fails."""


def parse_bank_csv(raw_csv: str) -> list[ParsedPayment]:
    reader = csv.DictReader(StringIO(raw_csv))
    if reader.fieldnames is None:
        raise BankCSVParserError("Missing CSV header row")

    lower = [col.strip().lower() for col in reader.fieldnames]
    missing = REQUIRED_COLUMNS - set(lower)
    if missing:
        raise BankCSVParserError(f"CSV missing required columns: {', '.join(sorted(missing))}")

    payments: list[ParsedPayment] = []
    for idx, row in enumerate(reader, start=2):
        try:
            payment_date = date.fromisoformat(row.get("date", "").strip())
            amount = float(row.get("amount", "0").strip())
            reference = row.get("reference")
            description = row.get("description")
        except Exception as exc:  # noqa: BLE001
            raise BankCSVParserError(f"Row {idx} is invalid: {exc}") from exc

        payments.append(
            ParsedPayment(
                payment_date=payment_date,
                amount=amount,
                reference=reference.strip() if isinstance(reference, str) else None,
                description=description.strip() if isinstance(description, str) else None,
            )
        )

    return payments
