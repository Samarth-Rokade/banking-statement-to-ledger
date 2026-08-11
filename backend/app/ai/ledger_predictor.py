import logging

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.ai.gemini_client import GeminiCallError, GeminiClient
from app.config.settings import get_settings
from app.models.ledger import Ledger, LedgerCreatedVia
from app.models.parsed_transaction import ParsedTransaction, ResolutionSource
from app.normalizer.narration_normalizer import TransactionTypeTag
from app.repositories.ai_prediction_repository import AIPredictionRepository
from app.repositories.ledger_group_repository import LedgerGroupRepository
from app.repositories.ledger_repository import LedgerRepository

logger = logging.getLogger(__name__)

PROMPT_NAME = "ledger_prediction"


class LedgerPredictionItem(BaseModel):
    transaction_id: str
    ledger_name: str
    is_new_ledger: bool = False
    group: str
    confidence: int
    reasoning: str = ""


def _chunk(items: list, size: int) -> list[list]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def _format_ledgers(ledgers: list[Ledger], groups_by_id: dict, limit: int) -> str:
    subset = ledgers[:limit]
    if not subset:
        return "(none yet)"
    return "\n".join(f"- {ledger.name} -> {groups_by_id.get(ledger.group_id, '?')}" for ledger in subset)


def _format_groups(group_names: list[str]) -> str:
    return "\n".join(f"- {name}" for name in group_names)


def _format_transactions(transactions: list[ParsedTransaction]) -> str:
    lines = []
    for txn in transactions:
        direction = "DEBIT" if txn.debit > 0 else "CREDIT"
        amount = txn.debit if txn.debit > 0 else txn.credit
        narration = txn.normalized_narration or txn.original_narration
        line = (
            f'- id={txn.id}, date={txn.txn_date}, narration="{narration}", '
            f"type={txn.transaction_type_tag}, direction={direction}, amount={amount}"
        )
        if txn.similar_candidates:
            hints = ", ".join(
                f"{c['ledger_name']} (score={c['score']})" for c in txn.similar_candidates
            )
            line += f", similar_candidates=[{hints}]"
        lines.append(line)
    return "\n".join(lines)


class LedgerPredictor:
    """Module 10: only ever called with what Modules 6-9 left unresolved. Batches
    them into as few Gemini calls as the configured batch size allows, applies
    guardrails to whatever comes back, and resolves each transaction in place.
    Never called for UPI_QR_SETTLEMENT transactions - those have no identifiable
    payer in the narration at all (confirmed against real statements) and always
    go straight to manual review instead of being guessed at.
    """

    def __init__(self, db: Session, gemini_client: GeminiClient | None = None):
        self.db = db
        self.settings = get_settings()
        self.gemini_client = gemini_client or GeminiClient()
        self.ledger_repo = LedgerRepository(db)
        self.group_repo = LedgerGroupRepository(db)
        self.prediction_repo = AIPredictionRepository(db)

    def predict_and_resolve(self, transactions: list[ParsedTransaction]) -> int:
        eligible = [
            t for t in transactions if t.transaction_type_tag != TransactionTypeTag.UPI_QR_SETTLEMENT
        ]
        for txn in transactions:
            if txn.transaction_type_tag == TransactionTypeTag.UPI_QR_SETTLEMENT:
                txn.requires_review = True

        if not eligible:
            return 0

        all_ledgers = self.ledger_repo.list_all()
        all_groups = self.group_repo.list_all()
        groups_by_id = {g.id: g.name for g in all_groups}
        group_names = {g.name for g in all_groups}
        ledger_context = _format_ledgers(all_ledgers, groups_by_id, self.settings.ai_max_ledger_context)
        group_context = _format_groups(sorted(group_names))

        resolved_count = 0
        for batch in _chunk(eligible, self.settings.ai_batch_size):
            resolved_count += self._resolve_batch(batch, ledger_context, group_context, group_names)
        return resolved_count

    def _resolve_batch(
        self,
        batch: list[ParsedTransaction],
        ledger_context: str,
        group_context: str,
        group_names: set[str],
    ) -> int:
        by_id = {str(txn.id): txn for txn in batch}
        transactions_context = _format_transactions(batch)

        try:
            items, raw_response, latency_ms = self.gemini_client.call(
                prompt_name=PROMPT_NAME,
                context={
                    "ledgers": ledger_context,
                    "groups": group_context,
                    "transactions": transactions_context,
                },
                model=self.settings.ai_model_ledger_prediction,
                response_model=LedgerPredictionItem,
            )
        except GeminiCallError as exc:
            logger.warning("Gemini call failed for a batch of %d transactions: %s", len(batch), exc)
            for txn in batch:
                self._mark_failed(txn)
                self.prediction_repo.create(
                    parsed_transaction_id=txn.id,
                    prompt_name=PROMPT_NAME,
                    model_used=self.settings.ai_model_ledger_prediction,
                    raw_request={"transaction_id": str(txn.id)},
                    raw_response=None,
                    predicted_confidence=None,
                    latency_ms=0,
                )
            return 0

        resolved_count = 0
        seen_ids: set[str] = set()
        for item in items:
            txn = by_id.get(item.transaction_id)
            if txn is None:
                continue  # Gemini echoed an id we never sent - ignore defensively
            seen_ids.add(item.transaction_id)

            self.prediction_repo.create(
                parsed_transaction_id=txn.id,
                prompt_name=PROMPT_NAME,
                model_used=self.settings.ai_model_ledger_prediction,
                raw_request={"transaction_id": item.transaction_id},
                raw_response=item.model_dump(),
                predicted_confidence=item.confidence,
                latency_ms=latency_ms,
            )

            if item.group not in group_names:
                # Guardrail: never trust a fabricated group name.
                self._mark_failed(txn)
                continue

            confidence = item.confidence
            if item.is_new_ledger:
                # New-ledger creation always needs a human glance the first time,
                # regardless of how confident the model claims to be.
                confidence = min(confidence, self.settings.ai_new_ledger_confidence_cap)

            ledger = self.ledger_repo.get_or_create(
                item.ledger_name, item.group, created_via=LedgerCreatedVia.AI
            )
            self.ledger_repo.increment_usage(ledger)

            txn.ledger_id = ledger.id
            txn.group_id = ledger.group_id
            txn.confidence = confidence
            txn.resolution_source = ResolutionSource.AI_PREDICTION
            txn.requires_review = confidence < self.settings.ai_auto_accept_threshold
            resolved_count += 1

        for txn_id, txn in by_id.items():
            if txn_id not in seen_ids:
                self._mark_failed(txn)

        return resolved_count

    @staticmethod
    def _mark_failed(txn: ParsedTransaction) -> None:
        txn.resolution_source = ResolutionSource.AI_FAILED
        txn.requires_review = True
