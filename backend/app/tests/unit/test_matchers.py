from app.matcher.alias_matcher import ALIAS_MATCH_CONFIDENCE, AliasMatcher
from app.matcher.exact_matcher import ExactMatcher
from app.matcher.similarity_matcher import AUTO_ACCEPT_THRESHOLD, SimilarityMatcher
from app.models.ledger import Ledger, LedgerCreatedVia
from app.models.ledger_alias import LedgerAlias, LedgerAliasSource
from app.models.ledger_group import LedgerGroup
from app.models.parsed_transaction import ParsedTransaction, ResolutionSource
from app.tests.unit.test_rule_engine import _txn


def _seed_group_and_ledger(db, group_name="Sundry Creditors", ledger_name="VCT PRODUCTS"):
    group = LedgerGroup(name=group_name, tally_group_type=group_name)
    db.add(group)
    db.flush()
    ledger = Ledger(name=ledger_name, group_id=group.id, created_via=LedgerCreatedVia.MANUAL)
    db.add(ledger)
    db.commit()
    return group, ledger


def test_exact_matcher_resolves_on_identical_ledger_name(db_session):
    _, ledger = _seed_group_and_ledger(db_session)
    txn = _txn("RTGS_OUT", "1000", "0")
    txn.normalized_narration = "VCT PRODUCTS"
    db_session.add(txn)
    db_session.commit()

    resolved = ExactMatcher(db_session).try_resolve(txn)

    assert resolved is True
    assert txn.ledger_id == ledger.id
    assert txn.confidence == 100
    assert txn.resolution_source == ResolutionSource.EXACT_MATCH
    assert ledger.usage_count == 1


def test_exact_matcher_does_not_resolve_when_no_ledger_matches(db_session):
    _seed_group_and_ledger(db_session)
    txn = _txn("RTGS_OUT", "1000", "0")
    txn.normalized_narration = "SOME OTHER COMPANY"
    db_session.add(txn)
    db_session.commit()

    assert ExactMatcher(db_session).try_resolve(txn) is False
    assert txn.ledger_id is None


def test_alias_matcher_resolves_via_alias(db_session):
    _, ledger = _seed_group_and_ledger(db_session, ledger_name="VCT PRODUCTS,AHMD")
    db_session.add(LedgerAlias(ledger_id=ledger.id, alias="VCT PRODUCTS", source=LedgerAliasSource.MANUAL))
    db_session.commit()

    txn = _txn("RTGS_OUT", "1000", "0")
    txn.normalized_narration = "VCT PRODUCTS"
    db_session.add(txn)
    db_session.commit()

    resolved = AliasMatcher(db_session).try_resolve(txn)

    assert resolved is True
    assert txn.ledger_id == ledger.id
    assert txn.confidence == ALIAS_MATCH_CONFIDENCE
    assert txn.resolution_source == ResolutionSource.ALIAS_MATCH


def test_similarity_matcher_auto_resolves_close_match(db_session):
    _, ledger = _seed_group_and_ledger(db_session, ledger_name="MEGA PRODUCT PROCESSORS PRIVATE LIMITED")
    txn = _txn("RTGS_OUT", "1000", "0")
    txn.normalized_narration = "MEGA PRODUCT PROCESSORS PRIVATE LIMTED"  # single-letter typo
    db_session.add(txn)
    db_session.commit()

    resolved = SimilarityMatcher(db_session).try_resolve(txn)

    assert resolved is True
    assert txn.ledger_id == ledger.id
    assert txn.resolution_source == ResolutionSource.SIMILARITY_MATCH
    assert txn.confidence >= round(AUTO_ACCEPT_THRESHOLD * 100)


def test_similarity_matcher_attaches_candidates_without_resolving_below_threshold(db_session):
    _, ledger = _seed_group_and_ledger(db_session, ledger_name="MEGA PRODUCT PROCESSORS PVT LTD")
    txn = _txn("RTGS_OUT", "1000", "0")
    txn.normalized_narration = "MEGA PRODUCT PROCESSORS PRIVATE LIM"  # plausible but not close enough
    db_session.add(txn)
    db_session.commit()

    resolved = SimilarityMatcher(db_session).try_resolve(txn)

    assert resolved is False
    assert txn.ledger_id is None
    assert txn.similar_candidates is not None
    assert txn.similar_candidates[0]["ledger_id"] == str(ledger.id)


def test_similarity_matcher_no_candidates_when_ledger_book_empty(db_session):
    txn = _txn("RTGS_OUT", "1000", "0")
    txn.normalized_narration = "NOBODY IN THE LEDGER BOOK"
    db_session.add(txn)
    db_session.commit()

    assert SimilarityMatcher(db_session).try_resolve(txn) is False
    assert txn.similar_candidates is None
