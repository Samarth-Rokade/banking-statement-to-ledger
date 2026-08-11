from decimal import Decimal

from app.normalizer.narration_normalizer import TransactionTypeTag, classify


def test_upi_qr_settlement_variants_all_tag_the_same_and_carry_no_counterparty():
    variants = [
        "STLMT FOR AU QR 12/09/2024 VPA-1558643 13119",
        "QR STLMT 03/01/2025 1558643 CR - 2402201158745230 - SOME BANK LIMITED QR SETTLEM",
        "AUQR STLMT2 100325 1558643 CR - 2402201158745230 - SOME BANK LIMITED QR SETTLEM",
    ]
    for narration in variants:
        normalized, tag = classify(narration, debit=Decimal("0"), credit=Decimal("100"))
        assert tag == TransactionTypeTag.UPI_QR_SETTLEMENT
        assert normalized == "UPI QR SETTLEMENT"


def test_bank_charges_variants():
    for narration in [
        "CASH DEPOSIT CHARGES-FOR-CA-GRP-28102024",
        "LDN DEPOSIT CHARGES_ON_11122024",
        "REV CD+TAX 291024 2402251461862643",
    ]:
        normalized, tag = classify(narration, debit=Decimal("10"), credit=Decimal("0"))
        assert tag == TransactionTypeTag.BANK_CHARGES
        assert normalized == "BANK CHARGES"


def test_cash_deposit_variants():
    for narration in [
        "CASH DEP-SELF- SOME BRANCH",
        "AEONTPD507914527466DEPOSIT AT BC POINT CR -1921223625770107 - SOME AGENT",
    ]:
        normalized, tag = classify(narration, debit=Decimal("0"), credit=Decimal("1000"))
        assert tag == TransactionTypeTag.CASH_DEPOSIT
        assert normalized == "CASH DEPOSIT"


def test_cheque_clearing_extracts_trailing_name():
    normalized, tag = classify(
        "BY CLG ADA 15/03/2025 SUNSHINE AGENCY", debit=Decimal("0"), credit=Decimal("6800")
    )
    assert tag == TransactionTypeTag.CHEQUE_CLEARING
    assert normalized == "SUNSHINE AGENCY"


def test_cheque_clearing_without_trailing_name_falls_back():
    normalized, tag = classify("BY CLG ICI 03/09/2024", debit=Decimal("0"), credit=Decimal("500000"))
    assert tag == TransactionTypeTag.CHEQUE_CLEARING
    assert normalized == "CHEQUE CLEARING"


def test_cheque_paid_extracts_name():
    normalized, tag = classify(
        "I/W CHEQUE PAID-ABC TRADERS-000001", debit=Decimal("50000"), credit=Decimal("0")
    )
    assert tag == TransactionTypeTag.CHEQUE_PAID
    assert normalized == "ABC TRADERS"


def test_rtgs_extracts_counterparty_between_reference_and_ifsc():
    normalized, tag = classify(
        "RTGS DR-AUBLR62025012411252103 -TEST INDUSTRIES LIMITED -HDFC0000021 -DM",
        debit=Decimal("1000000"),
        credit=Decimal("0"),
    )
    assert tag == TransactionTypeTag.RTGS_OUT
    assert normalized == "TEST INDUSTRIES LIMITED"


def test_rtgs_direction_follows_actual_amount_not_dr_cr_text():
    # Real statements sometimes carry "RTGS CR..." for inbound RTGS; direction must be
    # derived from the actual debit/credit amount, not trusted from narration text alone.
    normalized, tag = classify(
        "RTGS CRHDFCR52025032855143742 -SOME PERSON -HDFC0000119 -/FAST/FAST",
        debit=Decimal("0"),
        credit=Decimal("9000000"),
    )
    assert tag == TransactionTypeTag.RTGS_IN
    assert normalized == "SOME PERSON"


def test_neft_extracts_counterparty():
    normalized, tag = classify(
        "NEFT DR-N319242164564000 -SAMPLE VENDOR LIMITED -HDFC0000021 -DM",
        debit=Decimal("11111"),
        credit=Decimal("0"),
    )
    assert tag == TransactionTypeTag.NEFT_OUT
    assert normalized == "SAMPLE VENDOR LIMITED"


def test_imps_extracts_counterparty_and_direction():
    normalized, tag = classify(
        "IMPS-505215869885 -JOHN DOE -ICIC0006935 -********0431 -PIKU",
        debit=Decimal("0"),
        credit=Decimal("1"),
    )
    assert tag == TransactionTypeTag.IMPS_IN
    assert normalized == "JOHN DOE"


def test_atm_and_interest_fallbacks():
    normalized, tag = classify("ATM CASH WITHDRAWAL", debit=Decimal("2000"), credit=Decimal("0"))
    assert tag == TransactionTypeTag.ATM

    normalized, tag = classify("INTEREST CREDIT", debit=Decimal("0"), credit=Decimal("50"))
    assert tag == TransactionTypeTag.INTEREST


def test_unrecognized_narration_falls_back_to_other():
    normalized, tag = classify("SOME UNSEEN BANK FORMAT XYZ", debit=Decimal("0"), credit=Decimal("1"))
    assert tag == TransactionTypeTag.OTHER
    assert normalized == "SOME UNSEEN BANK FORMAT XYZ"


def test_upi_with_name_directly_after_prefix():
    # Kotak-style: UPI/{NAME}/{REF}/{SUFFIX}
    normalized, tag = classify(
        "UPI/SHANKAR LAL PAT/101161731489/UPI", debit=Decimal("0"), credit=Decimal("6330")
    )
    assert tag == TransactionTypeTag.UPI_IN
    assert normalized == "SHANKAR LAL PAT"


def test_upi_with_vpa_handle_prefers_handle_over_bank_name():
    # ICICI-style: UPI/{REF}/{FILLER}/{HANDLE}@{PSP}/{BANK NAME}/{TXN ID} - the VPA
    # handle is a much more stable per-counterparty key than the generic bank name.
    normalized, tag = classify(
        "UPI/445914375503/Sent from Paytm/7727096912@payt/Rajasthan Marud/PTM649e40ea",
        debit=Decimal("0"),
        credit=Decimal("25220"),
    )
    assert tag == TransactionTypeTag.UPI_IN
    assert normalized == "7727096912"


def test_upi_direction_follows_amount():
    normalized, tag = classify(
        "UPI/PhonePe/147314931091/Payment from Ph", debit=Decimal("500"), credit=Decimal("0")
    )
    assert tag == TransactionTypeTag.UPI_OUT
    assert normalized == "PHONEPE"


def test_icici_style_cheque_clearing_extracts_name():
    normalized, tag = classify(
        "CLG/RAJ TRADER/701056/INB/02.04.2024", debit=Decimal("0"), credit=Decimal("74400")
    )
    assert tag == TransactionTypeTag.CHEQUE_CLEARING
    assert normalized == "RAJ TRADER"


def test_kotak_style_cheque_clearing_without_name_falls_back():
    normalized, tag = classify(
        "BY CLG INST 1:3653/OPPTY-635503/DM MARKETING(Value Date: 03-03-2025)",
        debit=Decimal("0"),
        credit=Decimal("500000"),
    )
    assert tag == TransactionTypeTag.CHEQUE_CLEARING
    assert normalized == "CHEQUE CLEARING"


def test_by_cash_variant_tags_as_cash_deposit():
    normalized, tag = classify("BY CASH -UDAIPUR GNPS DM", debit=Decimal("0"), credit=Decimal("1670380"))
    assert tag == TransactionTypeTag.CASH_DEPOSIT
    assert normalized == "CASH DEPOSIT"


def test_fund_transfer_from_extracts_name():
    normalized, tag = classify(
        "FUND TRF FROM MUKESH TRADERS", debit=Decimal("0"), credit=Decimal("124250")
    )
    assert tag == TransactionTypeTag.TRANSFER_IN
    assert normalized == "MUKESH TRADERS"


def test_trf_slash_extracts_name():
    normalized, tag = classify(
        "TRF/KALPANA AGENCIES/000460/ICI/03.04.2024", debit=Decimal("0"), credit=Decimal("24800")
    )
    assert tag == TransactionTypeTag.TRANSFER_IN
    assert normalized == "KALPANA AGENCIES"


def test_trf_from_plain_extracts_name():
    normalized, tag = classify("TRFR FROM: KALPANA AGENCIES", debit=Decimal("0"), credit=Decimal("24800"))
    assert tag == TransactionTypeTag.TRANSFER_IN
    assert normalized == "KALPANA AGENCIES"


def test_numeric_prefixed_fee_line_tags_as_bank_charges():
    normalized, tag = classify(
        "0424_PROCESSING FEE_953852132_D.M. MARKETING", debit=Decimal("70000"), credit=Decimal("0")
    )
    assert tag == TransactionTypeTag.BANK_CHARGES
    assert normalized == "BANK CHARGES"


def test_gst_prefixed_fee_line_tags_as_bank_charges():
    normalized, tag = classify(
        "GST_0424_CERSAI CHARGES_953852132_D.M. MARKETING", debit=Decimal("90"), credit=Decimal("0")
    )
    assert tag == TransactionTypeTag.BANK_CHARGES


def test_chrg_prefixed_fee_line_tags_as_bank_charges():
    normalized, tag = classify(
        "Chrg: Debit Card Annual Fee 5818 for 2025", debit=Decimal("305.62"), credit=Decimal("0")
    )
    assert tag == TransactionTypeTag.BANK_CHARGES


def test_brb_sent_rtgs_extracts_trailing_name():
    normalized, tag = classify(
        "BRB:Sent RTGS KKBKR52025032900710885 000454361832 5 /MEGA PRODUCT",
        debit=Decimal("2500000"),
        credit=Decimal("0"),
    )
    assert tag == TransactionTypeTag.RTGS_OUT
    assert normalized == "MEGA PRODUCT"


def test_recd_imps_extracts_counterparty():
    normalized, tag = classify(
        "Recd:IMPS/507111398673/ULTIMATE C/KKBK/X3466/D", debit=Decimal("0"), credit=Decimal("50000")
    )
    assert tag == TransactionTypeTag.IMPS_IN
    assert normalized == "ULTIMATE C"


def test_rtgs_extracts_counterparty_after_ifsc_when_that_side_is_more_name_like():
    # ICICI's format puts the reference before the IFSC and the real name after it,
    # the reverse of AU Bank's layout - both must resolve to the human-readable name.
    normalized, tag = classify(
        "RTGS/ICICR4202404040400553944/UTIB0004778/SanjayKumarWalwani/UN71452404042",
        debit=Decimal("2500000"),
        credit=Decimal("0"),
    )
    assert tag == TransactionTypeTag.RTGS_OUT
    assert normalized == "SANJAYKUMARWALWANI"
