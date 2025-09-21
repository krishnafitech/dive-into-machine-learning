from __future__ import annotations

import pytest

from app.invoice_parser import InvoiceCSVParserError, parse_invoice_csv
from app.bank_parser import BankCSVParserError, parse_bank_csv


def test_parse_invoice_csv_success() -> None:
    csv_data = ("invoice_number,customer_name,customer_phone,amount,due_date\n"
                "INV-1,Acme,9999999999,1500.50,2024-08-20\n")
    invoices = parse_invoice_csv(csv_data)
    assert len(invoices) == 1
    assert invoices[0].invoice_number == "INV-1"
    assert invoices[0].amount == 1500.50


@pytest.mark.parametrize("csv_data", ["invoice_number,amount\n1,100\n", "\n"])
def test_parse_invoice_csv_failure(csv_data: str) -> None:
    with pytest.raises(InvoiceCSVParserError):
        parse_invoice_csv(csv_data)


def test_parse_bank_csv_success() -> None:
    csv_data = "date,amount,reference,description\n2024-08-10,1500.50,NEFT123,Payment\n"
    payments = parse_bank_csv(csv_data)
    assert len(payments) == 1
    assert payments[0].amount == 1500.50


@pytest.mark.parametrize("csv_data", ["date,reference\n2024-08-10,NEFT\n", "\n"])
def test_parse_bank_csv_failure(csv_data: str) -> None:
    with pytest.raises(BankCSVParserError):
        parse_bank_csv(csv_data)
