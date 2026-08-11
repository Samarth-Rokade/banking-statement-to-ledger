from app.matcher.similarity import blended_similarity


def test_identical_strings_score_one():
    assert blended_similarity("VCT PRODUCTS", "VCT PRODUCTS") == 1.0


def test_case_insensitive():
    assert blended_similarity("vct products", "VCT PRODUCTS") == 1.0


def test_close_spelling_variant_scores_high():
    # Real-world case surfaced by the AU Bank statement: same company, accountant's
    # suffix added on one side.
    score = blended_similarity("VCT PRODUCTS", "VCT PRODUCTS,AHMD")
    assert score >= 0.60


def test_unrelated_strings_score_low():
    score = blended_similarity("VCT PRODUCTS", "SHANKAR LAL PATEL")
    assert score < 0.30


def test_empty_string_scores_zero():
    assert blended_similarity("", "VCT PRODUCTS") == 0.0
    assert blended_similarity("VCT PRODUCTS", "") == 0.0
