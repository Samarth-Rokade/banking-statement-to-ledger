import re

# Each canonical field maps to a list of header aliases (lowercased, punctuation-stripped)
# seen across different bank export formats. Add new aliases here as new banks are onboarded -
# this is the extensibility point the parser is designed around.
#
# Aliases are matched as substrings of the normalized header, so "Debit(Dr.) INR" ->
# "debitdrinr" still matches alias "debit". Short aliases (<=3 chars, e.g. "dr"/"cr") are
# matched as exact equality instead, since as a substring they'd false-positive on
# unrelated headers (e.g. "dr" inside "Address").
_FIELD_ALIASES: dict[str, list[str]] = {
    "date": ["transdate", "txndate", "transactiondate", "valuedate", "postingdate", "date"],
    "description": [
        "description",
        "narration",
        "particulars",
        "transactiondetails",
        "remarks",
        "details",
    ],
    "reference": [
        "chqrefno",
        "reference",
        "refno",
        "chequeno",
        "utrno",
        "referenceno",
        "instrumentno",
    ],
    "debit": ["debit", "withdrawal", "withdrawalamt", "debitamount", "dr"],
    "credit": ["credit", "deposit", "depositamt", "creditamount", "cr"],
    "amount": ["amount", "transactionamount"],
    "balance": ["balance", "closingbalance", "runningbalance", "availablebalance"],
}


# Some banks (e.g. Kotak) collapse debit/credit into a single column and encode
# direction in the value itself, e.g. "Withdrawal(Dr)/ Deposit(Cr)" -> "500.00(Cr)".
# Detected as a combined column whenever a header mentions both sides of one of
# these pairs, so it isn't mistakenly claimed as a plain debit-only column.
_COMBINED_AMOUNT_MARKER_PAIRS = [("withdrawal", "deposit"), ("debit", "credit")]


def _normalize_header(header: str) -> str:
    return re.sub(r"[^a-z0-9]", "", header.strip().lower())


def _is_combined_amount_header(normalized: str) -> bool:
    return any(a in normalized and b in normalized for a, b in _COMBINED_AMOUNT_MARKER_PAIRS)


def build_column_map(headers: list[str]) -> dict[str, str]:
    """Map canonical field name -> original header string, for whichever fields are present.

    Returns only fields that were actually found; callers must check for the
    combination they need (e.g. either debit+credit, a single amount column, or a
    combined amount+direction column).
    """
    normalized_headers = [(_normalize_header(h), h) for h in headers]
    column_map: dict[str, str] = {}
    claimed: set[str] = set()

    for normalized, original in normalized_headers:
        if _is_combined_amount_header(normalized):
            column_map["combined_amount"] = original
            claimed.add(original)
            break  # only one combined column expected per statement

    for canonical_field, aliases in _FIELD_ALIASES.items():
        for alias in aliases:
            match = None
            for normalized, original in normalized_headers:
                if original in claimed:
                    continue
                is_match = normalized == alias if len(alias) <= 3 else alias in normalized
                if is_match:
                    match = original
                    break
            if match:
                column_map[canonical_field] = match
                claimed.add(match)
                break

    return column_map
