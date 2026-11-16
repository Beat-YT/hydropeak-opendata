"""Data models for the Hydro-Québec peak events open data."""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from functools import lru_cache
from typing import Any
from urllib.parse import quote_plus

from .const import OFFER_CODE_ALIASES, OFFER_CODE_PATTERN, PEAK_EVENTS_TABLE_URL
from .exceptions import OpenDataParseError


def _fold(value: str) -> str:
    """Comparison key: accents stripped, case-folded, whitespace collapsed."""
    decomposed = unicodedata.normalize("NFKD", value)
    stripped = "".join(char for char in decomposed if not unicodedata.combining(char))
    return " ".join(stripped.casefold().split())


@lru_cache(maxsize=256)
def normalize_offer_code(offer: str) -> str:
    """Return the offer code that ``offer`` refers to.

    Accepts either a bare code or any display name for it, ignoring accents,
    letter case and extra whitespace: ``"TPC-DPC"``, ``"tpc-dpc"``,
    ``"Flex Residentiel (TPC-DPC)"`` and ``"FLEX RÉSIDENTIEL (tpc-dpc)"`` all
    normalize to ``"TPC-DPC"``. Known codes are returned in their canonical
    spelling. Offers that carry no code, such as ``"OEA"`` or
    ``"ENG_100H_2F_7J"``, are returned with whitespace collapsed and are
    otherwise unchanged; :meth:`PeakEventsFeed.events_for_offer` still
    compares them without regard to accents or case.
    """
    offer = " ".join(offer.split())
    folded = _fold(offer)
    for name, code in OFFER_CODE_ALIASES.items():
        if folded in (_fold(name), _fold(code)):
            return code
    if (match := OFFER_CODE_PATTERN.search(offer)) is not None:
        # Recurse so a known code in any case/accent maps to its canonical form.
        return normalize_offer_code(match.group(1))
    return offer


def build_events_table_url(offer: str | None = None) -> str:
    """URL of the peak events table on the open data portal, sorted by start date.

    With ``offer``, the table is refined to it. When ``offer`` differs from
    its normalized code (see :func:`normalize_offer_code`), both are refined
    so records published under either spelling are shown; otherwise only the
    code is used.
    """
    params = ["sort=datedebut"]
    if offer is not None:
        code = normalize_offer_code(offer)
        values = [code] if offer == code else [offer, code]
        params += [f"refine.offre={quote_plus(value, safe='()')}" for value in values]
    params += ["disjunctive.offre", "disjunctive.plagehoraire", "disjunctive.secteurclient"]
    return f"{PEAK_EVENTS_TABLE_URL}?{'&'.join(params)}"


@dataclass(frozen=True, slots=True)
class PeakEvent:
    """A single peak event from the ``evenements`` array."""

    offer: str
    start: datetime
    end: datetime
    period: str | None
    sector: str | None

    @property
    def offer_code(self) -> str:
        """The offer code this event belongs to (see :func:`normalize_offer_code`)."""
        return normalize_offer_code(self.offer)

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
        """Events for ``offer``, sorted by start time.

        Matching is done on the normalized offer code and ignores accents
        and letter case, so ``"TPC-DPC"``, ``"tpc-dpc"`` and
        ``"Flex Résidentiel (TPC-DPC)"`` select the same events regardless
        of which spelling the feed used.
        """
        key = _fold(normalize_offer_code(offer))
        return tuple(event for event in self.events if _fold(event.offer_code) == key)


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
