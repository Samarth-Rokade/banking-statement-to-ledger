import re
from decimal import Decimal, InvalidOperation

import pandas as pd

# Some banks append the transaction direction to the amount itself instead of using
# separate debit/credit columns, e.g. "500,000.00(Cr)" / "70,000.00(Dr)" (Kotak).
_TRAILING_DIRECTION_RE = re.compile(r"\(?\s*(cr|dr)\s*\)?\s*$", re.IGNORECASE)


def to_decimal(value: object) -> Decimal:
    if pd.isna(value):
        return Decimal("0")
    text = str(value)
    # Strip thousands separators and any whitespace - the latter matters because a
    # number that wraps across a PDF cell's physical lines (e.g. "1,12,982.\n00")
    # comes back from text extraction as "1,12,982. 00" once newlines are collapsed
    # to spaces, which Decimal() would otherwise reject outright.
    text = text.replace(",", "").replace(" ", "").strip()
    if text in ("", "-"):
        return Decimal("0")
    try:
        return Decimal(text)
    except InvalidOperation:
        return Decimal("0")


def split_amount_and_direction(raw: str) -> tuple[str, str | None]:
    """Split "500,000.00(Cr)" -> ("500,000.00", "cr"); no-op if no suffix present."""
    text = raw.strip()
    match = _TRAILING_DIRECTION_RE.search(text)
    if not match:
        return text, None
    return text[: match.start()].strip(), match.group(1).lower()
