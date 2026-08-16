"""Async client for Hydro-Québec's peak events (pointes hivernales) open data."""

from .client import OFFER_DESCRIPTIONS_URL, PEAK_EVENTS_URL, OpenDataClient
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
    parse_feed,
)

__all__ = [
    "OFFER_DESCRIPTIONS_URL",
    "PEAK_EVENTS_URL",
    "OfferDescription",
    "OpenDataClient",
    "OpenDataConnectionError",
    "OpenDataError",
    "OpenDataParseError",
    "OpenDataRateLimitError",
    "OpenDataResponseError",
    "PeakEvent",
    "PeakEventsFeed",
    "parse_feed",
]
