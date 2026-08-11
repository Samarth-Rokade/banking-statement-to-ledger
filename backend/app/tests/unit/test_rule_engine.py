import uuid
from datetime import date
from decimal import Decimal

from app.models.ledger import Ledger
from app.models.ledger_group import LedgerGroup
from app.models.parsed_transaction import ParsedTransaction, ResolutionSource
from app.models.rule import Rule, RuleDirection, RuleType
from app.rules.rule_engine import RuleEngine


def _seed_groups_and_rules(db):
    for name in ["Cash-in-Hand", "Indirect Expenses", "Indirect Incomes"]:
        db.add(LedgerGroup(name=name, tally_group_type=name))
    db.flush()

    db.add_all(
        [
            Rule(
                rule_type=RuleType.TAG,
                pattern="CASH_DEPOSIT",
                ledger_name="Cash",
                group_name="Cash-in-Hand",
                priority=100,
            ),
            Rule(
                rule_type=RuleType.TAG,
                pattern="BANK_CHARGES",
                ledger_name="Bank Charges",
                group_name="Indirect Expenses",
                priority=100,
            ),
            Rule(
                rule_type=RuleType.TAG,
                pattern="INTEREST",
                direction=RuleDirection.CREDIT,
                ledger_name="Interest Income",
                group_name="Indirect Incomes",
                priority=100,
            ),
            Rule(
                rule_type=RuleType.TAG,
                pattern="INTEREST",
                direction=RuleDirection.DEBIT,
                ledger_name="Interest Expense",
                group_name="Indirect Expenses",
                priority=100,
            ),
        ]
    )
    db.commit()


def _txn(tag: str, debit: str, credit: str) -> ParsedTransaction:
    return ParsedTransaction(
        processing_job_id=uuid.uuid4(),  # no FK enforcement on SQLite; only NOT NULL matters here
        row_number=1,
        txn_date=date(2026, 1, 1),
        original_narration="test narration",
        debit=Decimal(debit),
        credit=Decimal(credit),
        transaction_type_tag=tag,
    )


def test_cash_deposit_resolves_via_rule(db_session):
    _seed_groups_and_rules(db_session)
    txn = _txn("CASH_DEPOSIT", "0", "1000")
    db_session.add(txn)
    db_session.commit()

    resolved = RuleEngine(db_session).try_resolve(txn)

    assert resolved is True
    assert txn.confidence == 100
    assert txn.resolution_source == ResolutionSource.RULE
    assert txn.requires_review is False
    ledger = db_session.get(Ledger, txn.ledger_id)
    assert ledger.name == "Cash"


def test_interest_direction_picks_correct_ledger(db_session):
    _seed_groups_and_rules(db_session)
    credit_txn = _txn("INTEREST", "0", "50")
    debit_txn = _txn("INTEREST", "20", "0")
    db_session.add_all([credit_txn, debit_txn])
    db_session.commit()

    engine = RuleEngine(db_session)
    assert engine.try_resolve(credit_txn) is True
    assert engine.try_resolve(debit_txn) is True

    assert db_session.get(Ledger, credit_txn.ledger_id).name == "Interest Income"
    assert db_session.get(Ledger, debit_txn.ledger_id).name == "Interest Expense"


def test_repeated_rule_hits_reuse_the_same_ledger_and_increment_usage(db_session):
    _seed_groups_and_rules(db_session)
    first = _txn("CASH_DEPOSIT", "0", "500")
    second = _txn("CASH_DEPOSIT", "0", "700")
    db_session.add_all([first, second])
    db_session.commit()

    engine = RuleEngine(db_session)
    engine.try_resolve(first)
    engine.try_resolve(second)

    assert first.ledger_id == second.ledger_id
    ledger = db_session.get(Ledger, first.ledger_id)
    assert ledger.usage_count == 2


def test_unmatched_tag_is_left_unresolved(db_session):
    _seed_groups_and_rules(db_session)
    txn = _txn("RTGS_OUT", "1000", "0")
    db_session.add(txn)
    db_session.commit()

    resolved = RuleEngine(db_session).try_resolve(txn)

    assert resolved is False
    assert txn.ledger_id is None
    assert txn.resolution_source is None
    assert txn.requires_review is False


def test_none_tag_is_left_unresolved(db_session):
    _seed_groups_and_rules(db_session)
    txn = _txn(None, "0", "1")
    db_session.add(txn)
    db_session.commit()

    assert RuleEngine(db_session).try_resolve(txn) is False


def test_resolve_job_transactions_returns_count_of_resolved_only(db_session):
    _seed_groups_and_rules(db_session)
    resolvable = _txn("CASH_DEPOSIT", "0", "500")
    unresolvable = _txn("RTGS_OUT", "1000", "0")
    db_session.add_all([resolvable, unresolvable])
    db_session.commit()

    count = RuleEngine(db_session).resolve_job_transactions([resolvable, unresolvable])

    assert count == 1
