import io
import re
from datetime import date, datetime
from decimal import Decimal

import pandas as pd
import pdfplumber

from app.parser.amount_parsing import split_amount_and_direction, to_decimal
from app.parser.base import ParserError, TransactionRow
from app.parser.column_mapper import build_column_map
from app.parser.tabular_parser import dataframe_to_transactions


def _clean_cell(value: object) -> str:
    if value is None:
        return ""
    # Cells that wrap across multiple physical lines come back with embedded
    # newlines (e.g. a narration split as "VST\nINDUSTRIES LIMITED"); collapsing
    # to single spaces keeps word boundaries intact instead of gluing words together.
    return " ".join(str(value).split())


def _extract_via_ruled_table(pdf: "pdfplumber.PDF") -> list[TransactionRow] | None:
    """Primary strategy: statements with actual ruled/bordered tables (pdfplumber's
    default line-based detection). Returns None (not an error) if no recognizable
    table is found, so the caller can fall through to the text-line strategy.
    """
    header: list[str] | None = None
    data_rows: list[list[str]] = []
    for page in pdf.pages:
        table = page.extract_table()
        if not table:
            continue
        for raw_row in table:
            row = [_clean_cell(c) for c in raw_row]
            if not any(row):
                continue  # fully blank row (spacer)

            if header is None:
                candidate_map = build_column_map(row)
                if "date" in candidate_map and "description" in candidate_map:
                    header = row
                continue  # first recognized row on any page is a header, not data

            if row == header or len(row) != len(header):
                continue  # repeated header (later pages) or a malformed/footer row

            data_rows.append(row)

    if header is None or not data_rows:
        return None

    df = pd.DataFrame(data_rows, columns=header)
    return dataframe_to_transactions(df)


# --- Text-line fallback: for statements with no detectable table borders at all
# (e.g. Kotak), where pdfplumber's ruled-table strategy finds nothing. Each
# transaction is anchored by a line starting with a date; the amounts appear on
# that same line either as three plain numbers (debit, credit, balance) or as two
# numbers each carrying a "(Cr)"/"(Dr)" direction suffix (amount, balance). Any
# following line that doesn't itself start a new transaction is treated as a
# wrapped continuation of the narration, up to a clear footer/summary boundary.

_DATE_RE = re.compile(
    r"^(\d{1,2}[-/]\d{1,2}[-/]\d{2,4}|\d{4}-\d{1,2}-\d{1,2}|\d{1,2}[-/][A-Za-z]{3}[-/]\d{2,4})"
)
_AMOUNT_TOKEN_RE = re.compile(r"-?\d[\d,]*\.\d{2}\s*(?:\(\s*(?:cr|dr)\s*\))?", re.IGNORECASE)
_FOOTER_RE = re.compile(r"^page\s+\d+\s+of\s+\d+$", re.IGNORECASE)
_SUMMARY_LABEL_RE = re.compile(r"^[A-Za-z][A-Za-z /]{2,40}:")
_DATE_FORMATS = (
    "%d-%m-%Y",
    "%d/%m/%Y",
    "%Y-%m-%d",
    "%d-%m-%y",
    "%d/%m/%y",
    "%d-%b-%Y",
    "%d/%b/%Y",
    "%d-%b-%y",
    "%d/%b/%y",
)


def _parse_date_token(token: str) -> date | None:
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(token, fmt).date()
        except ValueError:
            continue
    return None


def _parse_transaction_line(line: str, row_number: int) -> TransactionRow | None:
    date_match = _DATE_RE.match(line.strip())
    if not date_match:
        return None
    txn_date = _parse_date_token(date_match.group(1))
    if txn_date is None:
        return None

    rest = line[date_match.end():].strip()
    amount_matches = list(_AMOUNT_TOKEN_RE.finditer(rest))
    if len(amount_matches) not in (2, 3):
        return None  # ambiguous line - skip rather than guess

    description = rest[: amount_matches[0].start()].strip(" -|")
    if not description:
        return None

    parsed = [split_amount_and_direction(m.group()) for m in amount_matches]

    if len(parsed) == 3:
        (debit_text, _), (credit_text, _), (balance_text, _) = parsed
        debit, credit = to_decimal(debit_text), to_decimal(credit_text)
        balance = to_decimal(balance_text)
    else:
        (amount_text, amount_dir), (balance_text, balance_dir) = parsed
        amount = to_decimal(amount_text)
        if amount_dir is not None:
            debit = amount if amount_dir == "dr" else Decimal("0")
            credit = amount if amount_dir == "cr" else Decimal("0")
        else:
            debit = -amount if amount < 0 else Decimal("0")
            credit = amount if amount > 0 else Decimal("0")
        balance_magnitude = to_decimal(balance_text)
        balance = -balance_magnitude if balance_dir == "dr" else balance_magnitude

    return TransactionRow(
        row_number=row_number,
        txn_date=txn_date,
        description=description,
        reference=None,
        debit=debit,
        credit=credit,
        balance=balance,
    )


def _extract_via_text_lines(pdf: "pdfplumber.PDF") -> list[TransactionRow]:
    rows: list[TransactionRow] = []
    current: TransactionRow | None = None

    for page in pdf.pages:
        text = page.extract_text() or ""
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line or _FOOTER_RE.match(line):
                current = None
                continue

            row = _parse_transaction_line(line, row_number=len(rows) + 1)
            if row is not None:
                rows.append(row)
                current = row
                continue

            if current is not None and not _SUMMARY_LABEL_RE.match(line):
                current.description = f"{current.description} {line}".strip()
            else:
                current = None

    if not rows:
        raise ParserError(
            "No transactions detected in this PDF. It may be a scanned image; "
            "OCR support is not yet enabled."
        )
    return rows


class PDFParser:
    """Extracts transactions from a statement PDF regardless of layout.

    Tries a ruled/bordered table first (works for statements pdfplumber can detect
    real grid lines in). Falls back to a date-anchored text-line strategy for
    statements with no detectable table borders at all. Only a genuinely
    unreadable/scanned PDF should exhaust both and raise ParserError.
    """

    def parse(self, content: bytes) -> list[TransactionRow]:
        try:
            with pdfplumber.open(io.BytesIO(content)) as pdf:
                table_rows = _extract_via_ruled_table(pdf)
                if table_rows:
                    return table_rows
                return _extract_via_text_lines(pdf)
        except ParserError:
            raise
        except Exception as exc:
            raise ParserError("This PDF file could not be read; it may be corrupted.") from exc
