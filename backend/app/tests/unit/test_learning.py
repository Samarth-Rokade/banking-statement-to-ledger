from app.learning.service import record_correction
from app.models.ledger import Ledger, LedgerCreatedVia
from app.models.ledger_alias import LedgerAlias, LedgerAliasSource
from app.models.ledger_group import LedgerGroup
from app.repositories.ledger_alias_repository import LedgerAliasRepository
from app.tests.unit.test_rule_engine import _txn


def _seed_group_and_ledger(db, group_name="Sundry Creditors", ledger_name="VCT PRODUCTS"):
    group = LedgerGroup(name=group_name, tally_group_type=group_name)
    db.add(group)
    db.flush()
    ledger = Ledger(name=ledger_name, group_id=group.id, created_via=LedgerCreatedVia.MANUAL)
    db.add(ledger)
    db.commit()
    return group, ledger


def test_record_correction_creates_learned_alias(db_session):
    _, ledger = _seed_group_and_ledger(db_session)
    txn = _txn("RTGS_OUT", "1000", "0")
    txn.normalized_narration = "VCT PRODUCTS PVT LTD"  # deliberately not an exact ledger-name match
    db_session.add(txn)
    db_session.commit()

    record_correction(db_session, txn, ledger.id)

    alias = LedgerAliasRepository(db_session).get_by_alias("VCT PRODUCTS PVT LTD")
    assert alias is not None
    assert alias.ledger_id == ledger.id
    assert alias.source == LedgerAliasSource.LEARNED


def test_record_correction_skips_when_narration_matches_ledger_name_exactly(db_session):
    _, ledger = _seed_group_and_ledger(db_session)
    txn = _txn("RTGS_OUT", "1000", "0")
    txn.normalized_narration = ledger.name  # Exact Match already covers this case
    db_session.add(txn)
    db_session.commit()

    record_correction(db_session, txn, ledger.id)

    assert LedgerAliasRepository(db_session).get_by_alias(ledger.name) is None


def test_record_correction_skips_when_narration_missing(db_session):
    _, ledger = _seed_group_and_ledger(db_session)
    txn = _txn("RTGS_OUT", "1000", "0")
    txn.normalized_narration = None
    db_session.add(txn)
    db_session.commit()

    record_correction(db_session, txn, ledger.id)  # should not raise

    assert LedgerAliasRepository(db_session).list_all() == []


def test_record_correction_never_overwrites_manual_alias(db_session):
    _, ledger_a = _seed_group_and_ledger(db_session, ledger_name="LEDGER A")
    _, ledger_b = _seed_group_and_ledger(db_session, group_name="Indirect Expenses", ledger_name="LEDGER B")
    db_session.add(
        LedgerAlias(ledger_id=ledger_a.id, alias="AMBIGUOUS NARRATION", source=LedgerAliasSource.MANUAL)
    )
    db_session.commit()

    txn = _txn("RTGS_OUT", "1000", "0")
    txn.normalized_narration = "AMBIGUOUS NARRATION"
    db_session.add(txn)
    db_session.commit()

    record_correction(db_session, txn, ledger_b.id)  # human correction points elsewhere

    alias = LedgerAliasRepository(db_session).get_by_alias("AMBIGUOUS NARRATION")
    assert alias.ledger_id == ledger_a.id  # manual alias wins
    assert alias.source == LedgerAliasSource.MANUAL


def test_record_correction_updates_stale_learned_alias(db_session):
    _, ledger_a = _seed_group_and_ledger(db_session, ledger_name="LEDGER A")
    _, ledger_b = _seed_group_and_ledger(db_session, group_name="Indirect Expenses", ledger_name="LEDGER B")
    db_session.add(
        LedgerAlias(ledger_id=ledger_a.id, alias="DRIFTING NARRATION", source=LedgerAliasSource.LEARNED)
    )
    db_session.commit()

    txn = _txn("RTGS_OUT", "1000", "0")
    txn.normalized_narration = "DRIFTING NARRATION"
    db_session.add(txn)
    db_session.commit()

    record_correction(db_session, txn, ledger_b.id)

    alias = LedgerAliasRepository(db_session).get_by_alias("DRIFTING NARRATION")
    assert alias.ledger_id == ledger_b.id  # a later correction refines a learned alias
