"""Async client for Hydro-Québec's peak events (pointes hivernales) open data."""

from .client import OpenDataClient
from .const import OFFER_CODE_ALIASES, OFFER_DESCRIPTIONS_URL, PEAK_EVENTS_URL
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
    build_events_table_url,
    normalize_offer_code,
    parse_feed,
)

__all__ = [
    "OFFER_CODE_ALIASES",
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
    "build_events_table_url",
    "normalize_offer_code",
    "parse_feed",
]
