import io
from decimal import Decimal

import pandas as pd

from app.parser.excel_parser import ExcelParser


def _build_xlsx(rows: list[dict]) -> bytes:
    buffer = io.BytesIO()
    pd.DataFrame(rows).to_excel(buffer, index=False, engine="openpyxl")
    return buffer.getvalue()


def test_parses_xlsx_with_split_columns():
    content = _build_xlsx(
        [
            {
                "Date": "01-01-2026",
                "Narration": "UPI-SWIGGY",
                "Debit": 250.00,
                "Credit": 0,
                "Balance": 9750.00,
            },
            {
                "Date": "02-01-2026",
                "Narration": "SALARY CREDIT",
                "Debit": 0,
                "Credit": 50000.00,
                "Balance": 59750.00,
            },
        ]
    )

    rows = ExcelParser().parse(content)

    assert len(rows) == 2
    assert rows[0].debit == Decimal("250.0")
    assert rows[1].credit == Decimal("50000.0")
