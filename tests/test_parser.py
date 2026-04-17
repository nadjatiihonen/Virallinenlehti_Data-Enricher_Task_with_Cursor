from src.parser import find_matched_keywords


def test_find_matched_keywords_detects_relevant_terms_case_insensitive() -> None:
    text = (
        "Yrityssaneeraus on alkanut. Konkurssi voi johtaa lakkaamiseen myöhemmin."
    )
    keywords = ("konkurssi", "yrityssaneeraus", "alkaminen", "lakkaaminen")

    matched = find_matched_keywords(text, keywords)

    assert matched == ["konkurssi", "yrityssaneeraus", "lakkaaminen"]


def test_find_matched_keywords_returns_empty_for_irrelevant_text() -> None:
    text = "Tama sivu kasittelee vain yleisia ilmoituksia ilman avainsanoja."
    keywords = ("konkurssi", "yrityssaneeraus", "alkaminen", "lakkaaminen")

    matched = find_matched_keywords(text, keywords)

    assert matched == []
