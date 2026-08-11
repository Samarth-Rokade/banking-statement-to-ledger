import re
from decimal import Decimal


class TransactionTypeTag:
    """Plain string constants, not a DB enum - new tags should be addable without a
    migration, per the "keep business rules configurable" guideline.
    """

    RTGS_OUT = "RTGS_OUT"
    RTGS_IN = "RTGS_IN"
    NEFT_OUT = "NEFT_OUT"
    NEFT_IN = "NEFT_IN"
    IMPS_OUT = "IMPS_OUT"
    IMPS_IN = "IMPS_IN"
    UPI_OUT = "UPI_OUT"
    UPI_IN = "UPI_IN"
    UPI_QR_SETTLEMENT = "UPI_QR_SETTLEMENT"
    TRANSFER_OUT = "TRANSFER_OUT"
    TRANSFER_IN = "TRANSFER_IN"
    CASH_DEPOSIT = "CASH_DEPOSIT"
    BANK_CHARGES = "BANK_CHARGES"
    CHEQUE_CLEARING = "CHEQUE_CLEARING"
    CHEQUE_PAID = "CHEQUE_PAID"
    ATM = "ATM"
    INTEREST = "INTEREST"
    OTHER = "OTHER"


# IFSC codes are always 4 letters + '0' + 6 alphanumeric (RBI standard) - a reliable
# anchor for splitting "reference - COUNTERPARTY NAME - IFSC" style narrations used by
# RTGS/NEFT/IMPS, regardless of which bank issued the statement. Different banks put
# the counterparty name on either side of the IFSC (AU Bank: name before; ICICI: name
# after), so both sides are extracted and the more name-like one wins.
_IFSC_RE = re.compile(r"[A-Z]{4}0[A-Z0-9]{6}")
_SEGMENT_SPLIT_RE = re.compile(r"[-/]")

# UPI/QR aggregated settlement batches carry a settlement reference only - no payer
# identity is present in the text at all (confirmed against a real statement), so
# these are tagged distinctly and MUST NOT be treated as resolvable by narration alone.
_UPI_QR_RE = re.compile(r"^(STLMT FOR AU QR|QR STLMT\b|AUQR STLMT2?\b)")
_BANK_CHARGES_RE = re.compile(r"^(CASH DEPOSIT CHARGES|LDN DEPOSIT CHARGES|BANK CHARGES\b|REV CD\+TAX)")
# Kotak-style loan/account fee lines: "0424_PROCESSING FEE_953852132_..." or with a
# "GST_" prefix for the associated GST line, or "Chrg: Debit Card Annual Fee ...".
# Anchored on BOTH a recognizable prefix AND an explicit FEE/CHARGES keyword so this
# never fires on an unrelated numeric-prefixed narration.
_NUMERIC_FEE_RE = re.compile(r"^(?:GST_)?\d{3,4}_.*(?:FEE|CHARGES)")
_CHRG_RE = re.compile(r"^CHRG:.*\bFEE\b")
_CASH_DEPOSIT_RE = re.compile(r"^(CASH DEP\b|BY CASH\b|.*DEPOSIT AT BC POINT)")
_CHEQUE_CLEARING_RE = re.compile(r"^BY CLG\s+(\S+)\s+(\d{2}/\d{2}/\d{4})\s*(.*)$")
# ICICI's cheque-clearing narration has no "BY " prefix and uses '/' delimiters:
# "CLG/RAJ TRADER/701056/INB/02.04.2024".
_CLG_SLASH_RE = re.compile(r"^CLG/([^/]+)/")
_CHEQUE_PAID_RE = re.compile(r"^I/W CHEQUE PAID-(.+?)-\d+$")
_RTGS_RE = re.compile(r"^RTGS\s*(?:DR|CR)?-?(.*)$")
# Kotak's outbound-RTGS variant carries no "RTGS" prefix at all, just "BRB:Sent RTGS
# ...", and often no IFSC code either - the counterparty then is whatever trails the
# last '/' (e.g. ".../MEGA PRODUCT").
_BRB_SENT_RTGS_RE = re.compile(r"^BRB:SENT RTGS\s+(.*)$")
_NEFT_RE = re.compile(r"^NEFT\s*(?:DR|CR)?-?(.*)$")
_IMPS_RE = re.compile(r"^IMPS-(.*)$")
# Kotak's inbound-IMPS variant: "Recd:IMPS/507111398673/ULTIMATE C/KKBK ...".
_RECD_IMPS_RE = re.compile(r"^(?:RECD|SENT):IMPS[/-](.*)$")
_ATM_RE = re.compile(r"\bATM\b")
_INTEREST_RE = re.compile(r"\bINTEREST\b")

# Generic UPI transfer. Different banks lay the same three pieces of information out
# in a different order: Kotak puts the counterparty name right after "UPI/"; ICICI
# puts a reference number there instead and the counterparty's UPI handle
# ("name@bank") later in the string. Both are tried; the VPA handle wins when present
# since it's the more consistently person-specific token across a whole statement.
_UPI_RE = re.compile(r"^UPI[/-]")
_VPA_RE = re.compile(r"([A-Za-z0-9._+-]{3,})@[A-Za-z]{2,}")
_UPI_NOISE_SEGMENT_RE = re.compile(
    r"^(NA|OK|UPI|SENT FROM PAYTM|PAYMENT FROM PH|USING PAYT|SENT USING PAYT)$",
    re.IGNORECASE,
)

# "TRF/KALPANA AGENCIES/000542/ICI/16.05.2024" (ICICI/Kotak inter-account transfer)
# or the shorter "TRFR FROM: KALPANA AGENCIES" variant with no trailing reference.
_TRF_SLASH_RE = re.compile(r"\bTRFR?\s*FROM\s*:?\s*TRF/([^/]+)/|^TRF/([^/]+)/", re.IGNORECASE)
_TRF_FROM_PLAIN_RE = re.compile(r"^TRFR?\s*FROM\s*:?\s*(.+)$", re.IGNORECASE)
_FUND_TRF_FROM_RE = re.compile(r"^FUND TRF FROM\s+(.+)$", re.IGNORECASE)


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().upper()


def _looks_like_name(segment: str) -> bool:
    if len(segment) < 2:
        return False
    letters = sum(1 for c in segment if c.isalpha())
    return letters / len(segment) >= 0.6


def _extract_counterparty_near_ifsc(remainder: str) -> str | None:
    match = _IFSC_RE.search(remainder)
    if not match:
        return None

    before_segments = [s.strip() for s in _SEGMENT_SPLIT_RE.split(remainder[: match.start()]) if s.strip()]
    after_segments = [s.strip() for s in _SEGMENT_SPLIT_RE.split(remainder[match.end():]) if s.strip()]
    candidate_before = before_segments[-1] if before_segments else None
    candidate_after = after_segments[0] if after_segments else None

    candidates = [c for c in (candidate_before, candidate_after) if c and _looks_like_name(c)]
    if not candidates:
        return None
    # Prefer whichever candidate has more letters - real names/company names run
    # longer than the short reference suffixes ("DM", "FAST") that also pass the gate.
    return max(candidates, key=lambda c: sum(ch.isalpha() for ch in c))


def _extract_upi_counterparty(remainder: str) -> str | None:
    vpa_match = _VPA_RE.search(remainder)
    if vpa_match:
        handle = vpa_match.group(1).strip()
        if len(handle) >= 3:
            return handle

    for segment in remainder.split("/"):
        candidate = segment.strip()
        if not candidate or _UPI_NOISE_SEGMENT_RE.match(candidate) or candidate.isdigit():
            continue
        if _looks_like_name(candidate):
            return candidate
    return None


def classify(original_narration: str, debit: Decimal, credit: Decimal) -> tuple[str, str]:
    """Module 5's entire job: tag the narration's bank-specific pattern into a
    canonical transaction_type_tag, and produce a cleaned normalized_narration
    candidate for later ledger/counterparty matching (Modules 6-9). Purely
    rule/regex-based - no AI, no ledger/DB lookups.
    """
    text = _clean(original_narration)
    is_debit = debit > 0

    if _UPI_QR_RE.match(text):
        return "UPI QR SETTLEMENT", TransactionTypeTag.UPI_QR_SETTLEMENT

    if _BANK_CHARGES_RE.match(text) or _NUMERIC_FEE_RE.match(text) or _CHRG_RE.match(text):
        return "BANK CHARGES", TransactionTypeTag.BANK_CHARGES

    if _CASH_DEPOSIT_RE.match(text):
        return "CASH DEPOSIT", TransactionTypeTag.CASH_DEPOSIT

    match = _CHEQUE_CLEARING_RE.match(text)
    if match:
        name = match.group(3).strip()
        return (name or "CHEQUE CLEARING"), TransactionTypeTag.CHEQUE_CLEARING

    match = _CLG_SLASH_RE.match(text)
    if match:
        return match.group(1).strip(), TransactionTypeTag.CHEQUE_CLEARING

    if text.startswith("BY CLG"):
        # Recognized cheque-clearing prefix, but this bank's layout doesn't carry a
        # cleanly extractable payer name (e.g. Kotak's "BY CLG INST 1:3653/...").
        return "CHEQUE CLEARING", TransactionTypeTag.CHEQUE_CLEARING

    match = _CHEQUE_PAID_RE.match(text)
    if match:
        return match.group(1).strip(), TransactionTypeTag.CHEQUE_PAID

    match = _FUND_TRF_FROM_RE.match(text)
    if match:
        tag = TransactionTypeTag.TRANSFER_OUT if is_debit else TransactionTypeTag.TRANSFER_IN
        return match.group(1).strip(), tag

    if text.startswith("TRF"):
        match = _TRF_SLASH_RE.search(text)
        if match:
            name = match.group(1) or match.group(2)
            tag = TransactionTypeTag.TRANSFER_OUT if is_debit else TransactionTypeTag.TRANSFER_IN
            return name.strip(), tag
        match = _TRF_FROM_PLAIN_RE.match(text)
        if match:
            tag = TransactionTypeTag.TRANSFER_OUT if is_debit else TransactionTypeTag.TRANSFER_IN
            return match.group(1).strip(), tag

    match = _RTGS_RE.match(text)
    if match:
        counterparty = _extract_counterparty_near_ifsc(match.group(1))
        tag = TransactionTypeTag.RTGS_OUT if is_debit else TransactionTypeTag.RTGS_IN
        return (counterparty or "RTGS"), tag

    match = _BRB_SENT_RTGS_RE.match(text)
    if match:
        segments = [s.strip() for s in match.group(1).split("/") if s.strip()]
        counterparty = segments[-1] if segments and _looks_like_name(segments[-1]) else None
        tag = TransactionTypeTag.RTGS_OUT if is_debit else TransactionTypeTag.RTGS_IN
        return (counterparty or "RTGS"), tag

    match = _NEFT_RE.match(text)
    if match:
        counterparty = _extract_counterparty_near_ifsc(match.group(1))
        tag = TransactionTypeTag.NEFT_OUT if is_debit else TransactionTypeTag.NEFT_IN
        return (counterparty or "NEFT"), tag

    match = _IMPS_RE.match(text)
    if match:
        counterparty = _extract_counterparty_near_ifsc(match.group(1))
        tag = TransactionTypeTag.IMPS_OUT if is_debit else TransactionTypeTag.IMPS_IN
        return (counterparty or "IMPS"), tag

    match = _RECD_IMPS_RE.match(text)
    if match:
        segments = [s.strip() for s in match.group(1).split("/") if s.strip()]
        counterparty = next(
            (s for s in segments if not s.isdigit() and _looks_like_name(s)), None
        )
        tag = TransactionTypeTag.IMPS_OUT if is_debit else TransactionTypeTag.IMPS_IN
        return (counterparty or "IMPS"), tag

    if _UPI_RE.match(text):
        remainder = _UPI_RE.sub("", text, count=1)
        counterparty = _extract_upi_counterparty(remainder)
        tag = TransactionTypeTag.UPI_OUT if is_debit else TransactionTypeTag.UPI_IN
        return (counterparty or "UPI"), tag

    if _ATM_RE.search(text):
        return "ATM WITHDRAWAL", TransactionTypeTag.ATM

    if _INTEREST_RE.search(text):
        return "INTEREST", TransactionTypeTag.INTEREST

    return text, TransactionTypeTag.OTHER
