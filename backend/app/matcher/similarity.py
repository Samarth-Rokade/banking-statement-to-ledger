"""Blended string similarity for ledger fuzzy matching.

Implemented in pure Python at the application layer (not via Postgres' pg_trgm
extension) so it behaves identically on SQLite (dev) and Postgres (prod) - the
extension approach documented in the architecture plan doesn't exist on SQLite at
all, and duplicating the algorithm per-dialect isn't worth it at this scale.

The 0.7/0.3 trigram/Levenshtein blend and weights are a v1 starting point (per the
architecture plan's own note), not tuned against labeled data yet.
"""

TRIGRAM_WEIGHT = 0.7
LEVENSHTEIN_WEIGHT = 0.3


def _trigrams(text: str) -> set[str]:
    padded = f"  {text}  "
    if len(padded) < 3:
        return {padded} if padded else set()
    return {padded[i : i + 3] for i in range(len(padded) - 2)}


def trigram_similarity(a: str, b: str) -> float:
    set_a, set_b = _trigrams(a), _trigrams(b)
    if not set_a or not set_b:
        return 0.0
    union = len(set_a | set_b)
    return len(set_a & set_b) / union if union else 0.0


def _levenshtein_distance(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)

    previous_row = list(range(len(b) + 1))
    for i, char_a in enumerate(a, start=1):
        current_row = [i] + [0] * len(b)
        for j, char_b in enumerate(b, start=1):
            cost = 0 if char_a == char_b else 1
            current_row[j] = min(
                previous_row[j] + 1,  # deletion
                current_row[j - 1] + 1,  # insertion
                previous_row[j - 1] + cost,  # substitution
            )
        previous_row = current_row
    return previous_row[-1]


def normalized_levenshtein_similarity(a: str, b: str) -> float:
    if not a and not b:
        return 1.0
    distance = _levenshtein_distance(a, b)
    return 1 - distance / max(len(a), len(b))


def blended_similarity(a: str, b: str) -> float:
    a_norm, b_norm = a.strip().upper(), b.strip().upper()
    if not a_norm or not b_norm:
        return 0.0
    return TRIGRAM_WEIGHT * trigram_similarity(a_norm, b_norm) + LEVENSHTEIN_WEIGHT * (
        normalized_levenshtein_similarity(a_norm, b_norm)
    )
