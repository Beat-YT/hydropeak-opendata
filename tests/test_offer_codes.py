"""Tests for offer code normalization."""

from __future__ import annotations

import pytest

from hydropeak_opendata import OFFER_CODE_ALIASES, normalize_offer_code, parse_feed


@pytest.mark.parametrize(
    ("offer", "code"),
    [
        ("Flex Residentiel (TPC-DPC)", "TPC-DPC"),
        ("Flex Affaires (TPC-GPC)", "TPC-GPC"),
        ("Credit hivernal Residentiel (CPC-D)", "CPC-D"),
        ("Credit hivernal Affaires (CPC-G)", "CPC-G"),
        ("TPC-DPC", "TPC-DPC"),
        ("  TPC-DPC ", "TPC-DPC"),
        # Unlisted display name falls back to the trailing code.
        ("Flex D (TPC-DPC)", "TPC-DPC"),
        # Offers without a code are untouched.
        ("OEA", "OEA"),
        ("OEA Serres", "OEA Serres"),
        ("Chaine de bloc", "Chaine de bloc"),
        ("ENG_100H_2F_7J", "ENG_100H_2F_7J"),
        ("Essai_Mardis_Nov", "Essai_Mardis_Nov"),
    ],
)
def test_normalize_offer_code(offer, code):
    assert normalize_offer_code(offer) == code


def test_aliases_are_consistent_with_fallback():
    for name, code in OFFER_CODE_ALIASES.items():
        assert name.endswith(f"({code})")
        assert normalize_offer_code(code) == code


def _event(offer, day):
    return {
        "offre": offer,
        "dateDebut": f"2026-01-{day:02d}T16:00:00-05:00",
        "dateFin": f"2026-01-{day:02d}T20:00:00-05:00",
        "plageHoraire": "PM",
        "secteurClient": "Residentiel",
    }


def test_events_for_offer_matches_across_spellings():
    feed = parse_feed(
        {
            "offresDisponibles": ["Flex Residentiel (TPC-DPC)", "OEA"],
            "evenements": [
                _event("Flex Residentiel (TPC-DPC)", 10),
                _event("TPC-DPC", 11),
                _event("OEA", 12),
            ],
        }
    )

    by_code = feed.events_for_offer("TPC-DPC")
    by_name = feed.events_for_offer("Flex Residentiel (TPC-DPC)")

    assert [e.offer for e in by_code] == ["Flex Residentiel (TPC-DPC)", "TPC-DPC"]
    assert by_name == by_code
    assert all(e.offer_code == "TPC-DPC" for e in by_code)
    # Offers stay verbatim; only matching is normalized.
    assert feed.offers == ("Flex Residentiel (TPC-DPC)", "OEA")
    assert [e.offer for e in feed.events_for_offer("OEA")] == ["OEA"]
