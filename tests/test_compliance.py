# Maintainer: Leandro Michelino | ACE | leandro.michelino@oracle.com
from src.compliance import parse_compliance_entities, term_matches


def test_compliance_catalog_matches_aliases_with_word_boundaries():
    catalog = parse_compliance_entities(
        """entity_name,aliases,country,type,risk_level,source,source_date,notes
Zimbabwe Schools Examination Council,ZIMSEC|Zimbabwe Schools Examination Council,Zimbabwe,education authority,HIGH,curated,2026-05-07,test
""",
        source_name="test.csv",
    )

    matches = catalog.find_public_sector_matches(
        "Lunch with ZIMSEC Zimbabwe Schools Examination Council"
    )

    assert matches[0].entity.entity_name == "Zimbabwe Schools Examination Council"
    assert matches[0].matched_term == "Zimbabwe Schools Examination Council"
    assert "source: curated" in matches[0].evidence


def test_compliance_term_matching_avoids_partial_words():
    assert term_matches("lunch with gov customer", "gov")
    assert not term_matches("governance review", "gov")


def test_default_catalog_has_small_medium_and_high_risk_categories():
    from collections import Counter

    from src.compliance import load_local_compliance_catalog

    catalog = load_local_compliance_catalog()
    counts = Counter(entity.risk_level for entity in catalog.entities)

    assert counts["LOW"] >= 1
    assert counts["MEDIUM"] >= 1
    assert counts["HIGH"] >= 1
