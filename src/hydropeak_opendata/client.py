"""Async client for Hydro-Québec's peak events open data."""

from __future__ import annotations

import asyncio
import json
from datetime import date

import aiohttp

from .const import (
    DESCRIPTION_GRACE,
    DESCRIPTIONS_LIMIT,
    OFFER_DESCRIPTIONS_URL,
    PEAK_EVENTS_URL,
)
from .exceptions import (
    OpenDataConnectionError,
    OpenDataError,
    OpenDataParseError,
    OpenDataRateLimitError,
    OpenDataResponseError,
)
from .models import (
    OfferDescription,
    PeakEvent,
    PeakEventsFeed,
    Sector,
    _offer_in,
    _offer_sector,
    parse_feed,
    parse_offer_description,
)


class OpenDataClient:
    """Client for the peak events feed and the offer descriptions dataset.

    The aiohttp session is injected and never closed by the client, so one
    session can be shared across the application. The client sends
    conditional requests (``If-None-Match``) and serves the last parsed feed
    on ``304 Not Modified``; concurrent callers are serialized on a lock so
    a burst of refreshes results in one request followed by cheap 304s.
    """

    def __init__(
        self,
        session: aiohttp.ClientSession,
        *,
        request_timeout: float = 30.0,
        peak_events_url: str = PEAK_EVENTS_URL,
        offer_descriptions_url: str = OFFER_DESCRIPTIONS_URL,
    ) -> None:
        self._session = session
        self._peak_events_url = peak_events_url
        self._offer_descriptions_url = offer_descriptions_url
        self._timeout = aiohttp.ClientTimeout(total=request_timeout)
        self._lock = asyncio.Lock()
        self._etag: str | None = None
        self._feed: PeakEventsFeed | None = None

    async def get_feed(self) -> PeakEventsFeed:
        """Fetch (or revalidate) the peak events feed."""
        async with self._lock:
            headers: dict[str, str] = {}
            if self._etag is not None and self._feed is not None:
                headers["If-None-Match"] = self._etag

            try:
                async with self._session.get(
                    self._peak_events_url, headers=headers, timeout=self._timeout
                ) as response:
                    if response.status == 304 and self._feed is not None:
                        return self._feed
                    _raise_for_status(response)
                    etag = response.headers.get("ETag")
                    # The endpoint mislabels the JSON payload as text/plain,
                    # so parse the body ourselves instead of response.json().
                    text = await response.text()
            except OSError as err:
                raise OpenDataConnectionError(f"Error fetching peak events: {err}") from err
            except aiohttp.ClientError as err:
                raise OpenDataConnectionError(f"Error fetching peak events: {err}") from err
            except TimeoutError as err:
                raise OpenDataConnectionError("Timeout fetching peak events") from err

            try:
                data = json.loads(text)
            except ValueError as err:
                raise OpenDataParseError("Peak events payload is not valid JSON") from err

            feed = parse_feed(data)
            self._etag = etag
            self._feed = feed
            return feed

    async def get_events(self, offer: str | None = None) -> tuple[PeakEvent, ...]:
        """Fetch events, optionally filtered to one offer (code or display name)."""
        feed = await self.get_feed()
        if offer is None:
            return feed.events
        return feed.events_for_offer(offer)

    async def get_available_offers(self) -> tuple[str, ...]:
        """Fetch the canonical offer list, verbatim from ``offresDisponibles``."""
        feed = await self.get_feed()
        return feed.offers

    async def get_offer_labels(self) -> dict[str, str]:
        """Map each canonical offer identifier to a human-readable label.

        Keys are the canonical strings from ``offresDisponibles`` — the
        values to persist and to pass to :meth:`get_events`. Values are
        display labels for UIs such as a selection form.

        Labels are currently the canonical strings themselves, because
        Hydro-Québec does not yet publish display titles in its open data.
        When it does (expected in the offer descriptions dataset), a library
        update will source labels from there — the keys and this method's
        contract will not change, so consumers need no code change.
        """
        feed = await self.get_feed()
        return {offer: offer for offer in feed.offers}

    async def get_offer_descriptions(
        self, active_on: date | None = None
    ) -> tuple[OfferDescription, ...]:
        """Fetch offer descriptions from the Opendatasoft dataset.

        This endpoint is rate limited (429 raises
        :class:`OpenDataRateLimitError`), so it is intended for occasional
        use such as a setup flow, not for polling. One request returns at
        most ``DESCRIPTIONS_LIMIT`` records (the API maximum), newest first
        by end date. ``active_on`` filters to descriptions whose validity
        window covers that date.
        """
        params: dict[str, str | int] = {"limit": DESCRIPTIONS_LIMIT, "order_by": "fin desc"}
        if active_on is not None:
            day = active_on.isoformat()
            params["where"] = f"debut<='{day}' AND fin>='{day}'"

        try:
            async with self._session.get(
                self._offer_descriptions_url, params=params, timeout=self._timeout
            ) as response:
                _raise_for_status(response)
                data = await response.json(content_type=None)
        except OSError as err:
            raise OpenDataConnectionError(f"Error fetching descriptions: {err}") from err
        except aiohttp.ClientError as err:
            raise OpenDataConnectionError(f"Error fetching descriptions: {err}") from err
        except TimeoutError as err:
            raise OpenDataConnectionError("Timeout fetching descriptions") from err

        if not isinstance(data, dict) or not isinstance(data.get("results"), list):
            raise OpenDataParseError("Unexpected offer descriptions payload")
        return tuple(parse_offer_description(item) for item in data["results"])

    async def is_offer_available(self, offer: str, today: date) -> bool:
        """Whether the feed or a current offer description lists ``offer``.

        A description counts until ``DESCRIPTION_GRACE`` after it ends.
        Matching ignores spelling (see
        :func:`normalize_offer_code`). Offer descriptions are only fetched
        when the feed does not list the offer. Errors from either source
        raise, so ``False`` always means the offer is no longer published.
        """
        feed = await self.get_feed()
        if _offer_in(offer, feed.offers):
            return True
        descriptions = await self.get_offer_descriptions()
        cutoff = today - DESCRIPTION_GRACE
        return _offer_in(
            offer, (d.offer for d in descriptions if d.end is not None and d.end >= cutoff)
        )

    async def get_sector_offers(self, sector: Sector, today: date) -> tuple[str, ...]:
        """Offers in ``sector``, from the feed plus descriptions not ended by ``today``.

        ``CPC-D`` and ``TPC-DPC`` are residential. Any other offer is
        residential only if a description says so, and business otherwise,
        including when no description covers it. Spellings are deduplicated
        (see :func:`normalize_offer_code`), the feed's spelling winning. If
        descriptions cannot be fetched, only the feed is used. Feed errors
        raise.
        """
        feed = await self.get_feed()
        try:
            descriptions = tuple(
                d
                for d in await self.get_offer_descriptions()
                if d.end is not None and d.end >= today
            )
        except OpenDataError:
            descriptions = ()

        offers: list[str] = []
        for offer in (*feed.offers, *(d.offer for d in descriptions)):
            if not _offer_in(offer, offers):
                offers.append(offer)
        return tuple(offer for offer in offers if _offer_sector(offer, descriptions) is sector)


def _raise_for_status(response: aiohttp.ClientResponse) -> None:
    if response.status == 429:
        raise OpenDataRateLimitError("Rate limited by the open data endpoint")
    if response.status != 200:
        raise OpenDataResponseError(response.status)
