import re
from decimal import Decimal

import pandas as pd

from app.parser.amount_parsing import split_amount_and_direction, to_decimal
from app.parser.base import ParserError, TransactionRow
from app.parser.column_mapper import build_column_map

_ISO_DATE_RE = re.compile(r"^\d{4}-\d{1,2}-\d{1,2}")


def _parse_txn_date(raw_date) -> pd.Timestamp:
    # pandas' dayfirst=True can still swap day/month on unambiguous ISO (YYYY-MM-DD)
    # strings in some versions, so ISO dates are parsed explicitly without it; only
    # ambiguous D-M-Y / D/M/Y formats (common in Indian bank exports) use dayfirst.
    text = str(raw_date).strip()
    if _ISO_DATE_RE.match(text):
        return pd.to_datetime(text, errors="coerce")
    return pd.to_datetime(text, dayfirst=True, errors="coerce")


def dataframe_to_transactions(df: pd.DataFrame) -> list[TransactionRow]:
    df = df.dropna(how="all")
    if df.empty:
        raise ParserError("The file contains no data rows.")

    column_map = build_column_map([str(c) for c in df.columns])

    if "date" not in column_map or "description" not in column_map:
        raise ParserError(
            "Could not identify date/description columns in this file. "
            "Expected headers such as 'Date' and 'Narration'/'Description'."
        )

    has_split_columns = "debit" in column_map and "credit" in column_map
    has_amount_column = "amount" in column_map
    has_combined_amount = "combined_amount" in column_map
    if not has_split_columns and not has_amount_column and not has_combined_amount:
        raise ParserError(
            "Could not identify debit/credit amount columns in this file."
        )

    rows: list[TransactionRow] = []
    for _, record in df.iterrows():
        raw_date = record.get(column_map["date"])
        txn_date = _parse_txn_date(raw_date)
        if pd.isna(txn_date):
            continue

        description = str(record.get(column_map["description"], "")).strip()
        if not description:
            continue

        reference = None
        if "reference" in column_map:
            raw_reference = record.get(column_map["reference"])
            reference = None if pd.isna(raw_reference) else str(raw_reference).strip() or None

        if has_split_columns:
            debit = to_decimal(record.get(column_map["debit"]))
            credit = to_decimal(record.get(column_map["credit"]))
        elif has_combined_amount:
            raw_combined = record.get(column_map["combined_amount"])
            if pd.isna(raw_combined):
                debit = credit = Decimal("0")
            else:
                numeric_part, direction = split_amount_and_direction(str(raw_combined))
                magnitude = to_decimal(numeric_part)
                if direction == "dr":
                    debit, credit = magnitude, Decimal("0")
                elif direction == "cr":
                    debit, credit = Decimal("0"), magnitude
                else:
                    # No direction marker present; fall back to the sign of the number.
                    debit = -magnitude if magnitude < 0 else Decimal("0")
                    credit = magnitude if magnitude > 0 else Decimal("0")
        else:
            amount = to_decimal(record.get(column_map["amount"]))
            debit = -amount if amount < 0 else Decimal("0")
            credit = amount if amount > 0 else Decimal("0")

        balance = None
        if "balance" in column_map:
            raw_balance = record.get(column_map["balance"])
            if not pd.isna(raw_balance):
                numeric_part, direction = split_amount_and_direction(str(raw_balance))
                magnitude = to_decimal(numeric_part)
                balance = -magnitude if direction == "dr" else magnitude

        rows.append(
            TransactionRow(
                row_number=len(rows) + 1,
                txn_date=txn_date.date(),
                description=description,
                reference=reference,
                debit=debit,
                credit=credit,
                balance=balance,
            )
        )

    if not rows:
        raise ParserError("No valid transaction rows could be extracted from this file.")
    return rows
