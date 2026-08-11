from decimal import Decimal

import pytest

from app.parser.base import ParserError
from app.parser.csv_parser import CSVParser


def test_parses_split_debit_credit_columns():
    csv_content = (
        "Date,Narration,Reference,Debit,Credit,Balance\n"
        "01-01-2026,UPI-SWIGGY,UTR123,250.00,0,9750.00\n"
        "02-01-2026,SALARY CREDIT,,0,50000.00,59750.00\n"
    ).encode()

    rows = CSVParser().parse(csv_content)

    assert len(rows) == 2
    assert rows[0].description == "UPI-SWIGGY"
    assert rows[0].debit == Decimal("250.00")
    assert rows[0].credit == Decimal("0")
    assert rows[0].reference == "UTR123"
    assert rows[1].credit == Decimal("50000.00")
    assert rows[1].debit == Decimal("0")


def test_parses_single_signed_amount_column():
    csv_content = (
        "Date,Description,Amount,Balance\n"
        "01-01-2026,ATM WITHDRAWAL,-500.00,9500.00\n"
        "02-01-2026,INTEREST CREDIT,120.50,9620.50\n"
    ).encode()

    rows = CSVParser().parse(csv_content)

    assert rows[0].debit == Decimal("500.00")
    assert rows[0].credit == Decimal("0")
    assert rows[1].credit == Decimal("120.50")
    assert rows[1].debit == Decimal("0")


def test_skips_rows_with_unparsable_date():
    csv_content = (
        "Date,Description,Amount,Balance\n"
        "01-01-2026,VALID ROW,100.00,100.00\n"
        "TOTAL,,100.00,\n"
    ).encode()

    rows = CSVParser().parse(csv_content)

    assert len(rows) == 1
    assert rows[0].description == "VALID ROW"


def test_raises_when_required_columns_missing():
    csv_content = "Foo,Bar\n1,2\n".encode()

    with pytest.raises(ParserError):
        CSVParser().parse(csv_content)


def test_raises_on_empty_file():
    with pytest.raises(ParserError):
        CSVParser().parse(b"")
