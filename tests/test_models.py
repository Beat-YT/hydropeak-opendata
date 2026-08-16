"""Tests for feed parsing and models."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from hydropeak_opendata import OpenDataParseError, parse_feed
from hydropeak_opendata.models import parse_offer_description

EST = timezone(timedelta(hours=-5))


def test_parse_summer_feed(summer_feed):
    feed = parse_feed(summer_feed)

    assert "Credit hivernal Residentiel (CPC-D)" in feed.offers
    assert "OEA" in feed.offers
    assert len(feed.offers) == 38

    assert len(feed.events) == 7
    # sorted by start
    starts = [event.start for event in feed.events]
    assert starts == sorted(starts)
    # datetimes are timezone-aware
    assert all(event.start.tzinfo is not None for event in feed.events)

    assert feed.last_execution == datetime(2026, 8, 15, 19, 21, 22)


def test_offers_are_verbatim(winter_feed):
    feed = parse_feed(winter_feed)
    assert feed.offers[0] == "Credit hivernal Residentiel (CPC-D)"


def test_events_for_offer_exact_match(winter_feed):
    feed = parse_feed(winter_feed)

    events = feed.events_for_offer("Credit hivernal Residentiel (CPC-D)")
    assert len(events) == 3
    assert all(event.offer == "Credit hivernal Residentiel (CPC-D)" for event in events)

    assert feed.events_for_offer("Flex Residentiel (TPC-DPC)") != ()
    assert feed.events_for_offer("nonexistent") == ()


def test_event_fields(winter_feed):
    feed = parse_feed(winter_feed)
    event = feed.events[0]

    assert event.start == datetime(2026, 1, 9, 6, 0, tzinfo=EST)
    assert event.end == datetime(2026, 1, 9, 9, 0, tzinfo=EST)
    assert event.period == "AM"
    assert event.sector == "Residentiel"
    assert event.duration == timedelta(hours=3)


def test_event_is_active(winter_feed):
    feed = parse_feed(winter_feed)
    event = feed.events[0]

    assert event.is_active(datetime(2026, 1, 9, 7, 0, tzinfo=EST))
    assert not event.is_active(datetime(2026, 1, 9, 5, 59, tzinfo=EST))
    assert not event.is_active(datetime(2026, 1, 9, 9, 1, tzinfo=EST))


def test_parse_feed_rejects_bad_payloads():
    with pytest.raises(OpenDataParseError):
        parse_feed([])
    with pytest.raises(OpenDataParseError):
        parse_feed({"evenements": []})
    with pytest.raises(OpenDataParseError):
        parse_feed({"offresDisponibles": [], "evenements": "nope"})
    with pytest.raises(OpenDataParseError):
        parse_feed({"offresDisponibles": [], "evenements": [{"offre": "X"}]})


def test_parse_feed_tolerates_missing_last_execution(winter_feed):
    del winter_feed["derniereExecution"]
    assert parse_feed(winter_feed).last_execution is None


def test_parse_offer_description():
    record = {
        "offresdisponibles": "CPC-D",
        "type_clientele": "residentiel",
        "description_fr": "Crédit hivernal",
        "doc_fr": "https://example.test/fr",
        "doc_eng": "https://example.test/en",
        "debut": "2026-12-01",
        "fin": "2027-03-31",
    }
    desc = parse_offer_description(record)
    assert desc.offer == "CPC-D"
    assert desc.client_type == "residentiel"
    assert desc.start.isoformat() == "2026-12-01"
    assert desc.end.isoformat() == "2027-03-31"

    with pytest.raises(OpenDataParseError):
        parse_offer_description({"description_fr": "no offer key"})
