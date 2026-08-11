from decimal import Decimal

from app.parser.amount_parsing import split_amount_and_direction, to_decimal


def test_to_decimal_strips_commas():
    assert to_decimal("1,12,982.00") == Decimal("112982.00")


def test_to_decimal_strips_whitespace_from_wrapped_cell_numbers():
    # A number that wraps across a PDF table cell's physical lines comes back from
    # text extraction as e.g. "1,12,982. 00" once newlines are collapsed to spaces.
    assert to_decimal("1,12,982. 00") == Decimal("112982.00")


def test_to_decimal_handles_blank_and_dash():
    assert to_decimal("") == Decimal("0")
    assert to_decimal("-") == Decimal("0")
    assert to_decimal(None) == Decimal("0")


def test_split_amount_and_direction_extracts_suffix():
    assert split_amount_and_direction("500,000.00(Cr)") == ("500,000.00", "cr")
    assert split_amount_and_direction("70,000.00(Dr)") == ("70,000.00", "dr")


def test_split_amount_and_direction_no_suffix_is_noop():
    assert split_amount_and_direction("25,220.00") == ("25,220.00", None)
