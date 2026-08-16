"""Exceptions raised by the hydropeak-opendata client."""

from __future__ import annotations


class OpenDataError(Exception):
    """Base exception for all hydropeak-opendata errors."""


class OpenDataConnectionError(OpenDataError):
    """Communicating with the open data endpoint failed (network, timeout)."""


class OpenDataRateLimitError(OpenDataError):
    """The endpoint answered 429 Too Many Requests."""


class OpenDataResponseError(OpenDataError):
    """The endpoint answered with an unexpected HTTP status."""

    def __init__(self, status: int, message: str | None = None) -> None:
        super().__init__(message or f"Unexpected HTTP status {status}")
        self.status = status


class OpenDataParseError(OpenDataError):
    """The endpoint answered 200 but the payload could not be parsed."""
