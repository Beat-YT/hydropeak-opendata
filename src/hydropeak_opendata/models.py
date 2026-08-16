"""Data models for the Hydro-Québec peak events open data."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

from .exceptions import OpenDataParseError


@dataclass(frozen=True, slots=True)
class PeakEvent:
    """A single peak event from the ``evenements`` array."""

    offer: str
    start: datetime
    end: datetime
    period: str | None
    sector: str | None

    @property
    def duration(self) -> timedelta:
        """Length of the event."""
        return self.end - self.start

    def is_active(self, now: datetime) -> bool:
        """Whether the event is in progress at ``now``."""
        return self.start <= now <= self.end


@dataclass(frozen=True, slots=True)
class PeakEventsFeed:
    """The parsed ``pointeshivernales.json`` document.

    ``offers`` is the canonical list of offer identifiers exactly as
    published in ``offresDisponibles``; no transformation is applied.
    """

    offers: tuple[str, ...]
    events: tuple[PeakEvent, ...]
    last_execution: datetime | None

    def events_for_offer(self, offer: str) -> tuple[PeakEvent, ...]:
        """Events whose ``offre`` value equals ``offer``, sorted by start time."""
        return tuple(event for event in self.events if event.offer == offer)


@dataclass(frozen=True, slots=True)
class OfferDescription:
    """A record from the ``evenements-de-pointe-offres-disponibles`` dataset."""

    offer: str
    client_type: str | None
    description_fr: str | None
    doc_url_fr: str | None
    doc_url_en: str | None
    start: date | None
    end: date | None


def _parse_event(item: dict[str, Any]) -> PeakEvent:
    try:
        return PeakEvent(
            offer=item["offre"],
            start=datetime.fromisoformat(item["dateDebut"]),
            end=datetime.fromisoformat(item["dateFin"]),
            period=item.get("plageHoraire"),
            sector=item.get("secteurClient"),
        )
    except (KeyError, TypeError, ValueError) as err:
        raise OpenDataParseError(f"Malformed event entry: {item!r}") from err


def parse_feed(data: Any) -> PeakEventsFeed:
    """Parse the raw JSON document into a :class:`PeakEventsFeed`.

    Raises :class:`OpenDataParseError` if required structure is missing.
    """
    if not isinstance(data, dict):
        raise OpenDataParseError(f"Expected a JSON object, got {type(data).__name__}")

    try:
        raw_offers = data["offresDisponibles"]
        raw_events = data["evenements"]
    except KeyError as err:
        raise OpenDataParseError(f"Missing key in feed: {err}") from err

    if not isinstance(raw_offers, list) or not isinstance(raw_events, list):
        raise OpenDataParseError("offresDisponibles and evenements must be arrays")

    # "derniereExecution" is a single-element array of a naive local
    # timestamp ("2026-08-15 19:21:22"); its timezone is unspecified upstream.
    last_execution: datetime | None = None
    raw_last = data.get("derniereExecution")
    if isinstance(raw_last, list) and raw_last:
        try:
            last_execution = datetime.fromisoformat(raw_last[0])
        except (TypeError, ValueError):
            last_execution = None

    events = sorted((_parse_event(item) for item in raw_events), key=lambda e: e.start)
    return PeakEventsFeed(
        offers=tuple(str(raw) for raw in raw_offers),
        events=tuple(events),
        last_execution=last_execution,
    )


def _parse_date(value: Any) -> date | None:
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def parse_offer_description(item: dict[str, Any]) -> OfferDescription:
    """Parse one record from the offer descriptions dataset."""
    try:
        offer = item["offresdisponibles"]
    except KeyError as err:
        raise OpenDataParseError(f"Malformed offer description: {item!r}") from err

    return OfferDescription(
        offer=offer,
        client_type=item.get("type_clientele"),
        description_fr=item.get("description_fr"),
        doc_url_fr=item.get("doc_fr"),
        doc_url_en=item.get("doc_eng"),
        start=_parse_date(item.get("debut")),
        end=_parse_date(item.get("fin")),
    )
