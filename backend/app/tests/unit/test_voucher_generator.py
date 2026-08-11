import uuid
from decimal import Decimal

from app.models.ledger import Ledger, LedgerCreatedVia
from app.models.ledger_group import LedgerGroup
from app.repositories.voucher_type_repository import VoucherTypeRepository
from app.tests.unit.test_rule_engine import _txn
from app.vouchers.voucher_generator import VoucherGenerator, determine_voucher_type_name


def _seed_group_and_ledger(db, group_name, ledger_name):
    group = LedgerGroup(name=group_name, tally_group_type=group_name)
    db.add(group)
    db.flush()
    ledger = Ledger(name=ledger_name, group_id=group.id, created_via=LedgerCreatedVia.MANUAL)
    db.add(ledger)
    db.commit()
    return group, ledger


def test_determine_voucher_type_contra_for_own_bank_or_cash_group():
    assert determine_voucher_type_name("Cash-in-Hand", Decimal("100"), Decimal("0")) == "Contra"
    assert determine_voucher_type_name("Bank Accounts", Decimal("0"), Decimal("100")) == "Contra"


def test_determine_voucher_type_receipt_on_credit():
    assert determine_voucher_type_name("Sundry Debtors", Decimal("0"), Decimal("500")) == "Receipt"


def test_determine_voucher_type_payment_on_debit():
    assert determine_voucher_type_name("Sundry Creditors", Decimal("500"), Decimal("0")) == "Payment"


def test_determine_voucher_type_journal_fallback_when_no_amount():
    assert determine_voucher_type_name("Suspense A/c", Decimal("0"), Decimal("0")) == "Journal"


def test_generate_for_transaction_returns_none_when_unresolved(db_session):
    txn = _txn("RTGS_OUT", "1000", "0")
    db_session.add(txn)
    db_session.commit()

    assert VoucherGenerator(db_session).generate_for_transaction(txn) is None


def test_generate_for_transaction_creates_voucher_with_correct_type(db_session):
    _, ledger = _seed_group_and_ledger(db_session, "Sundry Creditors", "VCT PRODUCTS")
    txn = _txn("RTGS_OUT", "1000", "0")
    txn.normalized_narration = "VCT PRODUCTS"
    txn.ledger_id = ledger.id
    txn.group_id = ledger.group_id
    db_session.add(txn)
    db_session.commit()

    voucher = VoucherGenerator(db_session).generate_for_transaction(txn)

    payment_type = VoucherTypeRepository(db_session).get_by_name("Payment")
    assert voucher is not None
    assert voucher.voucher_type_id == payment_type.id
    assert voucher.voucher_number == "V00001"
    assert voucher.narration == "VCT PRODUCTS"
    assert txn.voucher_type_id == payment_type.id


def test_generate_for_transaction_is_idempotent_and_keeps_voucher_number(db_session):
    _, ledger = _seed_group_and_ledger(db_session, "Sundry Creditors", "VCT PRODUCTS")
    txn = _txn("RTGS_OUT", "1000", "0")
    txn.normalized_narration = "VCT PRODUCTS"
    txn.ledger_id = ledger.id
    txn.group_id = ledger.group_id
    db_session.add(txn)
    db_session.commit()

    generator = VoucherGenerator(db_session)
    first = generator.generate_for_transaction(txn)
    first_number = first.voucher_number

    second = generator.generate_for_transaction(txn)

    assert second.id == first.id
    assert second.voucher_number == first_number


def test_generate_for_transaction_updates_type_if_ledger_reassigned_to_contra_group(db_session):
    _, creditor_ledger = _seed_group_and_ledger(db_session, "Sundry Creditors", "VCT PRODUCTS")
    _, cash_ledger = _seed_group_and_ledger(db_session, "Cash-in-Hand", "Cash")
    txn = _txn("RTGS_OUT", "1000", "0")
    txn.normalized_narration = "VCT PRODUCTS"
    txn.ledger_id = creditor_ledger.id
    txn.group_id = creditor_ledger.group_id
    db_session.add(txn)
    db_session.commit()

    generator = VoucherGenerator(db_session)
    generator.generate_for_transaction(txn)

    txn.ledger_id = cash_ledger.id
    txn.group_id = cash_ledger.group_id
    voucher = generator.generate_for_transaction(txn)

    contra_type = VoucherTypeRepository(db_session).get_by_name("Contra")
    assert voucher.voucher_type_id == contra_type.id


def test_voucher_numbers_are_sequential_per_job(db_session):
    _, ledger = _seed_group_and_ledger(db_session, "Sundry Creditors", "VCT PRODUCTS")
    job_id = uuid.uuid4()
    txns = []
    for i in range(3):
        txn = _txn("RTGS_OUT", "1000", "0")
        txn.processing_job_id = job_id
        txn.row_number = i + 1
        txn.normalized_narration = "VCT PRODUCTS"
        txn.ledger_id = ledger.id
        txn.group_id = ledger.group_id
        db_session.add(txn)
        txns.append(txn)
    db_session.commit()

    generated = VoucherGenerator(db_session).generate_for_job(txns)
    db_session.commit()

    assert generated == 3
    numbers = sorted(
        VoucherGenerator(db_session).voucher_repo.get_by_transaction_id(t.id).voucher_number
        for t in txns
    )
    assert numbers == ["V00001", "V00002", "V00003"]
