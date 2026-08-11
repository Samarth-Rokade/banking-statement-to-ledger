import uuid

from sqlalchemy.orm import Session

from app.matcher.similarity import blended_similarity
from app.models.parsed_transaction import ParsedTransaction, ResolutionSource
from app.repositories.ledger_alias_repository import LedgerAliasRepository
from app.repositories.ledger_repository import LedgerRepository

# A top match at/above this score is trustworthy enough to auto-resolve without a
# human glance. Below it but at/above the floor, the match is surfaced as a
# candidate for the (future) AI stage and manual review, never silently dropped.
AUTO_ACCEPT_THRESHOLD = 0.90
CANDIDATE_FLOOR = 0.60
MAX_CANDIDATES = 3


class SimilarityMatcher:
    """Module 9: fuzzy-matches the normalized narration against every known ledger
    name and alias. Candidate generation is a full scan in pure Python (not a DB
    trigram index) - fine at the ledger-book sizes this stage runs against; revisit
    if that stops being true (see the architecture plan's performance notes).
    """

    def __init__(self, db: Session):
        self.ledger_repo = LedgerRepository(db)
        self.alias_repo = LedgerAliasRepository(db)

    def _candidate_names(self) -> list[tuple[str, uuid.UUID]]:
        pairs = [(ledger.name, ledger.id) for ledger in self.ledger_repo.list_all()]
        pairs.extend((alias.alias, alias.ledger_id) for alias in self.alias_repo.list_all())
        return pairs

    def find_candidates(self, normalized_narration: str) -> list[dict]:
        scored = [
            {"ledger_id": ledger_id, "name": name, "score": blended_similarity(normalized_narration, name)}
            for name, ledger_id in self._candidate_names()
        ]
        scored.sort(key=lambda c: c["score"], reverse=True)

        # Same ledger can appear via its own name and one or more aliases; keep only
        # its best-scoring appearance.
        best_per_ledger: dict = {}
        for candidate in scored:
            existing = best_per_ledger.get(candidate["ledger_id"])
            if existing is None or candidate["score"] > existing["score"]:
                best_per_ledger[candidate["ledger_id"]] = candidate

        ranked = sorted(best_per_ledger.values(), key=lambda c: c["score"], reverse=True)
        return [c for c in ranked if c["score"] >= CANDIDATE_FLOOR][:MAX_CANDIDATES]

    def try_resolve(self, transaction: ParsedTransaction) -> bool:
        if not transaction.normalized_narration:
            return False

        candidates = self.find_candidates(transaction.normalized_narration)
        if not candidates:
            return False

        top = candidates[0]
        if top["score"] < AUTO_ACCEPT_THRESHOLD:
            transaction.similar_candidates = [
                {
                    "ledger_id": str(c["ledger_id"]),
                    "ledger_name": c["name"],
                    "score": round(c["score"], 4),
                }
                for c in candidates
            ]
            return False

        ledger = self.ledger_repo.get_by_id(top["ledger_id"])
        if ledger is None:
            return False

        self.ledger_repo.increment_usage(ledger)
        transaction.ledger_id = ledger.id
        transaction.group_id = ledger.group_id
        transaction.confidence = round(top["score"] * 100)
        transaction.resolution_source = ResolutionSource.SIMILARITY_MATCH
        transaction.requires_review = False
        return True
