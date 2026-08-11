import uuid
from datetime import date
from decimal import Decimal

from app.models.ledger import Ledger, LedgerCreatedVia
from app.models.ledger_group import LedgerGroup
from app.models.parsed_transaction import ParsedTransaction
from app.validator.validation_engine import ValidationEngine


def _txn(row_number, debit="0", credit="0", balance=None, narration="test narration", **kwargs):
    return ParsedTransaction(
        processing_job_id=uuid.uuid4(),  # no FK enforcement on SQLite; only NOT NULL matters here
        row_number=row_number,
        txn_date=date(2026, 1, row_number),
        original_narration=narration,
        debit=Decimal(debit),
        credit=Decimal(credit),
        balance=Decimal(balance) if balance is not None else None,
        **kwargs,
    )


def _seed_group_and_ledger(db, group_name="Sundry Creditors", ledger_name="VCT PRODUCTS"):
    group = LedgerGroup(name=group_name, tally_group_type=group_name)
    db.add(group)
    db.flush()
    ledger = Ledger(name=ledger_name, group_id=group.id, created_via=LedgerCreatedVia.MANUAL)
    db.add(ledger)
    db.commit()
    return group, ledger


def test_no_errors_on_clean_resolved_transactions(db_session):
    _, ledger = _seed_group_and_ledger(db_session)
    txn = _txn(1, debit="1000", balance="9000")
    txn.ledger_id = ledger.id
    txn.group_id = ledger.group_id
    db_session.add(txn)
    db_session.commit()

    ValidationEngine(db_session).validate_job_transactions([txn])

    assert txn.validation_errors is None
    assert txn.requires_review is False
    assert txn.is_duplicate is False


def test_flags_both_debit_and_credit_present(db_session):
    txn = _txn(1, debit="500", credit="500")
    db_session.add(txn)
    db_session.commit()

    ValidationEngine(db_session).validate_job_transactions([txn])

    assert txn.requires_review is True
    assert "both a debit and a credit" in txn.validation_errors[0]


def test_flags_neither_debit_nor_credit_present(db_session):
    txn = _txn(1)
    db_session.add(txn)
    db_session.commit()

    ValidationEngine(db_session).validate_job_transactions([txn])

    assert txn.requires_review is True
    assert "neither a debit nor a credit" in txn.validation_errors[0]


def test_flags_broken_ledger_reference_and_zeroes_confidence(db_session):
    txn = _txn(1, debit="500")
    txn.ledger_id = uuid.uuid4()  # no such ledger
    txn.confidence = 90
    db_session.add(txn)
    db_session.commit()

    ValidationEngine(db_session).validate_job_transactions([txn])

    assert txn.requires_review is True
    assert any("no longer exists" in e for e in txn.validation_errors)
    assert txn.confidence == 0


def test_flags_group_mismatch_between_transaction_and_ledger(db_session):
    _, ledger = _seed_group_and_ledger(db_session)
    other_group = LedgerGroup(name="Indirect Expenses", tally_group_type="Indirect Expenses")
    db_session.add(other_group)
    db_session.commit()

    txn = _txn(1, debit="500")
    txn.ledger_id = ledger.id
    txn.group_id = other_group.id  # mismatched on purpose
    db_session.add(txn)
    db_session.commit()

    ValidationEngine(db_session).validate_job_transactions([txn])

    assert txn.requires_review is True
    assert any("does not match" in e for e in txn.validation_errors)
    assert txn.confidence == 0


def test_detects_running_balance_mismatch(db_session):
    first = _txn(1, credit="1000", balance="1000")
    second = _txn(2, debit="200", balance="750")  # should be 800, not 750
    db_session.add_all([first, second])
    db_session.commit()

    ValidationEngine(db_session).validate_job_transactions([first, second])

    assert first.requires_review is False
    assert second.requires_review is True
    assert any("Balance does not follow" in e for e in second.validation_errors)


def test_running_balance_is_a_noop_when_balances_absent(db_session):
    first = _txn(1, credit="1000")
    second = _txn(2, debit="200")
    db_session.add_all([first, second])
    db_session.commit()

    ValidationEngine(db_session).validate_job_transactions([first, second])

    assert first.validation_errors is None
    assert second.validation_errors is None


def test_detects_duplicate_within_job(db_session):
    narration = "UPI-JOHN DOE-1234"
    first = _txn(1, debit="500", narration=narration)
    duplicate = _txn(2, debit="500", narration=narration)
    duplicate.txn_date = first.txn_date  # same date, amount, narration -> exact duplicate
    db_session.add_all([first, duplicate])
    db_session.commit()

    ValidationEngine(db_session).validate_job_transactions([first, duplicate])

    assert first.is_duplicate is False
    assert duplicate.is_duplicate is True
    assert duplicate.duplicate_of_transaction_id == first.id
    assert duplicate.requires_review is True
    assert any("Possible duplicate" in e for e in duplicate.validation_errors)
