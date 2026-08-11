from datetime import date
from decimal import Decimal

import pytest

from app.parser.base import ParserError
from app.parser.pdf_parser import PDFParser
from app.tests.unit.pdf_fixture import build_simple_pdf, build_table_pdf

_COL_WIDTHS = [70, 180, 70, 70, 70]


def test_parses_bordered_table_with_wrapped_narration_cell():
    # Mirrors real bank statement PDFs: header + rows where a narration cell wraps
    # across multiple physical lines within a single table row.
    rows = [
        ["Trans Date", "Description/Narration", "Chq./Ref.No.", "Debit(Dr.) INR", "Credit(Cr.) INR"],
        ["2024-09-06", "BY CLG ICI 03/09/2024", "000000000554", "-", "500,000.00"],
        ["2024-09-12", "STLMT FOR AU QR 12/09/2024 VPA\n-1558643", "13119", "-", "1.00"],
        ["2024-09-19", "RTGS DR-\nAUBLR2202409190485-VCT\nPRODUCTS-HDFC0001681", "AUBLR22024", "500,000.00", "-"],
    ]
    pdf_bytes = build_table_pdf(rows, _COL_WIDTHS)

    result = PDFParser().parse(pdf_bytes)

    assert len(result) == 3
    assert result[0].txn_date == date(2024, 9, 6)
    assert result[0].credit == Decimal("500000.00")
    assert result[1].description == "STLMT FOR AU QR 12/09/2024 VPA -1558643"
    assert result[1].credit == Decimal("1.00")
    assert result[2].description == "RTGS DR- AUBLR2202409190485-VCT PRODUCTS-HDFC0001681"
    assert result[2].debit == Decimal("500000.00")


def test_skips_repeated_header_across_pages_worth_of_rows():
    rows = [
        ["Date", "Narration", "Debit", "Credit", "Balance"],
        ["01-01-2026", "UPI-SWIGGY", "250.00", "-", "9750.00"],
        ["Date", "Narration", "Debit", "Credit", "Balance"],  # repeated header, e.g. page break
        ["02-01-2026", "SALARY CREDIT", "-", "50000.00", "59750.00"],
    ]
    pdf_bytes = build_table_pdf(rows, _COL_WIDTHS)

    result = PDFParser().parse(pdf_bytes)

    assert len(result) == 2
    assert result[1].description == "SALARY CREDIT"


def test_raises_when_no_recognizable_table_found():
    pdf_bytes = build_simple_pdf(["Just a cover page with no transactions."])

    with pytest.raises(ParserError):
        PDFParser().parse(pdf_bytes)


def test_raises_on_corrupt_pdf():
    with pytest.raises(ParserError):
        PDFParser().parse(b"not a real pdf")


def test_bordered_table_with_combined_debit_credit_column():
    # Some banks (e.g. Kotak) collapse debit/credit into one column and encode
    # direction as a "(Cr)"/"(Dr)" suffix on the value itself.
    rows = [
        ["Date", "Narration", "Chq/Ref No", "Withdrawal(Dr)/ Deposit(Cr)", "Balance"],
        ["03-03-2025", "RTGS AUBLR62025 D M MARKETING", "RTGSINW-008512", "500,000.00(Cr)", "500,000.00(Cr)"],
        ["03-03-2025", "0424_PROCESSING FEE", "953852132", "70,000.00(Dr)", "430,000.00(Cr)"],
    ]
    wide_col_widths = [70, 150, 70, 130, 100]
    pdf_bytes = build_table_pdf(rows, wide_col_widths)

    result = PDFParser().parse(pdf_bytes)

    assert len(result) == 2
    assert result[0].credit == Decimal("500000.00")
    assert result[0].debit == Decimal("0")
    assert result[0].balance == Decimal("500000.00")
    assert result[1].debit == Decimal("70000.00")
    assert result[1].credit == Decimal("0")
    assert result[1].balance == Decimal("430000.00")


def test_text_line_fallback_for_borderless_statement():
    # No ruled table at all (e.g. Kotak) - date-anchored lines with amounts carrying
    # a (Cr)/(Dr) suffix, and a wrapped narration continuation line with no date.
    lines = [
        "Some Bank Letterhead",
        "Date Narration Chq/Ref No Balance",
        "03-03-2025 RTGS AUBLR62025030311850177 D M RTGSINW-0085120301 500,000.00(Cr) 500,000.00(Cr)",
        "MARKETING AUB",
        "04-03-2025 BY CLG INST 1:3653/OPPTY-635503/DM 50,440.00(Cr) 550,440.00(Cr)",
        "MARKETING(Value Date: 03-03-2025)",
        "Page 1 of 1",
    ]
    pdf_bytes = build_simple_pdf(lines)

    result = PDFParser().parse(pdf_bytes)

    assert len(result) == 2
    assert result[0].txn_date == date(2025, 3, 3)
    assert result[0].credit == Decimal("500000.00")
    assert result[0].balance == Decimal("500000.00")
    assert result[0].description == "RTGS AUBLR62025030311850177 D M RTGSINW-0085120301 MARKETING AUB"
    assert result[1].description == (
        "BY CLG INST 1:3653/OPPTY-635503/DM MARKETING(Value Date: 03-03-2025)"
    )


def test_text_line_fallback_handles_negative_running_balance():
    lines = [
        "01-04-2024 BRB:Sent RTGS KKBKR520240 2,500,000.00(Dr) 2,041,033.62(Dr)",
    ]
    pdf_bytes = build_simple_pdf(lines)

    result = PDFParser().parse(pdf_bytes)

    assert result[0].debit == Decimal("2500000.00")
    assert result[0].balance == Decimal("-2041033.62")
