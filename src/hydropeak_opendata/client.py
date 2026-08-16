"""Async client for Hydro-Québec's peak events open data."""

from __future__ import annotations

import asyncio
import json
from datetime import date

import aiohttp

from .exceptions import (
    OpenDataConnectionError,
    OpenDataParseError,
    OpenDataRateLimitError,
    OpenDataResponseError,
)
from .models import (
    OfferDescription,
    PeakEvent,
    PeakEventsFeed,
    parse_feed,
    parse_offer_description,
)

PEAK_EVENTS_URL = (
    "https://donnees.solutions.hydroquebec.com/donnees-ouvertes/data/json/pointeshivernales.json"
)
OFFER_DESCRIPTIONS_URL = (
    "https://donnees.hydroquebec.com/api/explore/v2.1/catalog/datasets"
    "/evenements-de-pointe-offres-disponibles/records"
)
_DESCRIPTIONS_PAGE_SIZE = 100


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
        """Fetch events, optionally filtered to one offer (exact match)."""
        feed = await self.get_feed()
        if offer is None:
            return feed.events
        return feed.events_for_offer(offer)

    async def get_available_offers(self) -> tuple[str, ...]:
        """Fetch the canonical offer list, verbatim from ``offresDisponibles``."""
        feed = await self.get_feed()
        return feed.offers

    async def get_offer_descriptions(
        self, active_on: date | None = None
    ) -> tuple[OfferDescription, ...]:
        """Fetch offer descriptions from the Opendatasoft dataset.

        This endpoint is rate limited (429 raises
        :class:`OpenDataRateLimitError`), so it is intended for occasional
        use such as a setup flow, not for polling. Results are paginated
        transparently. ``active_on`` filters to descriptions whose validity
        window covers that date.
        """
        params: dict[str, str | int] = {"limit": _DESCRIPTIONS_PAGE_SIZE}
        if active_on is not None:
            day = active_on.isoformat()
            params["where"] = f"debut<='{day}' AND fin>='{day}'"

        descriptions: list[OfferDescription] = []
        offset = 0
        while True:
            try:
                async with self._session.get(
                    self._offer_descriptions_url,
                    params={**params, "offset": offset},
                    timeout=self._timeout,
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

            results = data["results"]
            descriptions.extend(parse_offer_description(item) for item in results)

            total = data.get("total_count", 0)
            offset += len(results)
            if not results or offset >= total:
                return tuple(descriptions)


def _raise_for_status(response: aiohttp.ClientResponse) -> None:
    if response.status == 429:
        raise OpenDataRateLimitError("Rate limited by the open data endpoint")
    if response.status != 200:
        raise OpenDataResponseError(response.status)
