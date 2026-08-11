from app.ai.gemini_client import GeminiCallError
from app.ai.ledger_predictor import LedgerPredictionItem, LedgerPredictor
from app.models.ledger import Ledger, LedgerCreatedVia
from app.models.ledger_group import LedgerGroup
from app.models.parsed_transaction import ResolutionSource
from app.normalizer.narration_normalizer import TransactionTypeTag
from app.tests.unit.test_rule_engine import _txn


class FakeGeminiClient:
    """Test double for GeminiClient.call - never touches the real API."""

    def __init__(self, items=None, raise_error=False):
        self._items = items or []
        self._raise_error = raise_error
        self.calls = []

    def call(self, prompt_name, context, model, response_model):
        self.calls.append({"prompt_name": prompt_name, "context": context, "model": model})
        if self._raise_error:
            raise GeminiCallError("simulated failure")
        return list(self._items), "raw-response-text", 42


def _seed_group(db, name="Sundry Creditors"):
    group = LedgerGroup(name=name, tally_group_type=name)
    db.add(group)
    db.commit()
    return group


def test_resolves_existing_ledger_from_prediction(db_session):
    group = _seed_group(db_session)
    ledger = Ledger(name="VCT PRODUCTS", group_id=group.id, created_via=LedgerCreatedVia.MANUAL)
    db_session.add(ledger)
    db_session.commit()

    txn = _txn("RTGS_OUT", "1000", "0")
    txn.normalized_narration = "VCT PRODUCTS AHMD"
    db_session.add(txn)
    db_session.commit()

    fake_client = FakeGeminiClient(
        items=[
            LedgerPredictionItem(
                transaction_id=str(txn.id),
                ledger_name="VCT PRODUCTS",
                is_new_ledger=False,
                group="Sundry Creditors",
                confidence=95,
                reasoning="matches existing ledger",
            )
        ]
    )

    resolved_count = LedgerPredictor(db_session, gemini_client=fake_client).predict_and_resolve([txn])

    assert resolved_count == 1
    assert txn.ledger_id == ledger.id
    assert txn.confidence == 95
    assert txn.resolution_source == ResolutionSource.AI_PREDICTION
    assert txn.requires_review is False  # 95 >= default threshold 90
    assert ledger.usage_count == 1


def test_new_ledger_confidence_is_capped_regardless_of_model_claim(db_session):
    _seed_group(db_session)
    txn = _txn("RTGS_OUT", "1000", "0")
    txn.normalized_narration = "BRAND NEW COMPANY LTD"
    db_session.add(txn)
    db_session.commit()

    fake_client = FakeGeminiClient(
        items=[
            LedgerPredictionItem(
                transaction_id=str(txn.id),
                ledger_name="BRAND NEW COMPANY LTD",
                is_new_ledger=True,
                group="Sundry Creditors",
                confidence=99,
                reasoning="looks like a new vendor",
            )
        ]
    )

    LedgerPredictor(db_session, gemini_client=fake_client).predict_and_resolve([txn])

    assert txn.confidence == 85  # capped, not 99
    assert txn.requires_review is True  # 85 < 90 auto-accept threshold
    created_ledger = db_session.query(Ledger).filter_by(name="BRAND NEW COMPANY LTD").first()
    assert created_ledger.created_via == LedgerCreatedVia.AI


def test_upi_qr_settlement_never_calls_gemini(db_session):
    _seed_group(db_session)
    txn = _txn(TransactionTypeTag.UPI_QR_SETTLEMENT, "0", "500")
    db_session.add(txn)
    db_session.commit()

    fake_client = FakeGeminiClient(items=[])

    resolved_count = LedgerPredictor(db_session, gemini_client=fake_client).predict_and_resolve([txn])

    assert resolved_count == 0
    assert txn.requires_review is True
    assert txn.ledger_id is None
    assert fake_client.calls == []


def test_gemini_call_error_marks_batch_as_ai_failed(db_session):
    _seed_group(db_session)
    txn = _txn("RTGS_OUT", "1000", "0")
    txn.normalized_narration = "SOME COMPANY"
    db_session.add(txn)
    db_session.commit()

    fake_client = FakeGeminiClient(raise_error=True)

    resolved_count = LedgerPredictor(db_session, gemini_client=fake_client).predict_and_resolve([txn])

    assert resolved_count == 0
    assert txn.resolution_source == ResolutionSource.AI_FAILED
    assert txn.requires_review is True


def test_fabricated_group_name_is_rejected(db_session):
    _seed_group(db_session)
    txn = _txn("RTGS_OUT", "1000", "0")
    txn.normalized_narration = "SOME COMPANY"
    db_session.add(txn)
    db_session.commit()

    fake_client = FakeGeminiClient(
        items=[
            LedgerPredictionItem(
                transaction_id=str(txn.id),
                ledger_name="SOME COMPANY",
                is_new_ledger=True,
                group="Made Up Group That Does Not Exist",
                confidence=95,
            )
        ]
    )

    resolved_count = LedgerPredictor(db_session, gemini_client=fake_client).predict_and_resolve([txn])

    assert resolved_count == 0
    assert txn.ledger_id is None
    assert txn.resolution_source == ResolutionSource.AI_FAILED
    assert txn.requires_review is True


def test_transaction_missing_from_response_is_marked_failed(db_session):
    _seed_group(db_session)
    txn_a = _txn("RTGS_OUT", "1000", "0")
    txn_a.normalized_narration = "COMPANY A"
    txn_b = _txn("RTGS_OUT", "2000", "0")
    txn_b.normalized_narration = "COMPANY B"
    db_session.add_all([txn_a, txn_b])
    db_session.commit()

    # Gemini only returns a prediction for txn_a, silently dropping txn_b.
    fake_client = FakeGeminiClient(
        items=[
            LedgerPredictionItem(
                transaction_id=str(txn_a.id),
                ledger_name="COMPANY A",
                is_new_ledger=True,
                group="Sundry Creditors",
                confidence=90,
            )
        ]
    )

    resolved_count = LedgerPredictor(db_session, gemini_client=fake_client).predict_and_resolve(
        [txn_a, txn_b]
    )

    assert resolved_count == 1
    assert txn_a.ledger_id is not None
    assert txn_b.ledger_id is None
    assert txn_b.resolution_source == ResolutionSource.AI_FAILED


def test_batches_transactions_according_to_configured_batch_size(db_session, monkeypatch):
    from app.config.settings import get_settings

    monkeypatch.setattr(get_settings(), "ai_batch_size", 2)
    _seed_group(db_session)

    txns = []
    for i in range(5):
        txn = _txn("RTGS_OUT", "1000", "0")
        txn.normalized_narration = f"COMPANY {i}"
        db_session.add(txn)
        txns.append(txn)
    db_session.commit()

    fake_client = FakeGeminiClient(items=[])  # empty response each call -> all marked failed

    LedgerPredictor(db_session, gemini_client=fake_client).predict_and_resolve(txns)

    # 5 transactions at batch size 2 -> 3 calls (2, 2, 1)
    assert len(fake_client.calls) == 3
