"""Tests for the HTTP client, against a local aiohttp test server."""

from __future__ import annotations

import asyncio
import json

import pytest
from aiohttp import web

from hydropeak_opendata import (
    OpenDataClient,
    OpenDataConnectionError,
    OpenDataParseError,
    OpenDataRateLimitError,
    OpenDataResponseError,
)


class FakeOpenData:
    """Scriptable stand-in for the two Hydro-Québec endpoints."""

    def __init__(self):
        self.feed_responses = []  # queue of callables returning web.Response
        self.feed_requests = []  # recorded feed request headers
        self.desc_pages = []  # payloads keyed by offset // 100
        self.desc_status = 200
        self.server = None

    async def handle_feed(self, request):
        self.feed_requests.append(dict(request.headers))
        return self.feed_responses.pop(0)(request)

    async def handle_descriptions(self, request):
        if self.desc_status != 200:
            return web.Response(status=self.desc_status)
        offset = int(request.query.get("offset", 0))
        return web.json_response(self.desc_pages[offset // 100])


def json_ok(payload, etag='"v1"'):
    """The endpoint mislabels its JSON as text/plain; the fake does too."""
    return lambda request: web.Response(
        text=json.dumps(payload), content_type="text/plain", headers={"ETag": etag}
    )


def status(code):
    return lambda request: web.Response(status=code)


def body(text):
    return lambda request: web.Response(text=text, content_type="text/plain")


@pytest.fixture
async def fake(aiohttp_server):
    fake = FakeOpenData()
    app = web.Application()
    app.router.add_get("/feed", fake.handle_feed)
    app.router.add_get("/descriptions", fake.handle_descriptions)
    fake.server = await aiohttp_server(app)
    return fake


@pytest.fixture
async def client(fake, aiohttp_client):
    session = await aiohttp_client(fake.server)
    return OpenDataClient(
        session.session,
        peak_events_url=str(fake.server.make_url("/feed")),
        offer_descriptions_url=str(fake.server.make_url("/descriptions")),
    )


async def test_get_feed_parses_mislabeled_json(client, fake, winter_feed):
    fake.feed_responses = [json_ok(winter_feed)]
    feed = await client.get_feed()

    assert feed.offers[0] == "Credit hivernal Residentiel (CPC-D)"
    assert len(feed.events) == 4


async def test_get_feed_revalidates_with_etag(client, fake, winter_feed):
    fake.feed_responses = [json_ok(winter_feed, etag='"v1"'), status(304)]

    first = await client.get_feed()
    second = await client.get_feed()

    assert fake.feed_requests[0].get("If-None-Match") is None
    assert fake.feed_requests[1].get("If-None-Match") == '"v1"'
    assert second is first  # cached object served on 304


async def test_get_feed_304_without_cache_is_an_error(client, fake):
    fake.feed_responses = [status(304)]
    with pytest.raises(OpenDataResponseError) as excinfo:
        await client.get_feed()
    assert excinfo.value.status == 304


async def test_get_feed_error_statuses(client, fake):
    fake.feed_responses = [status(429)]
    with pytest.raises(OpenDataRateLimitError):
        await client.get_feed()

    fake.feed_responses = [status(503)]
    with pytest.raises(OpenDataResponseError) as excinfo:
        await client.get_feed()
    assert excinfo.value.status == 503


async def test_get_feed_invalid_json(client, fake):
    fake.feed_responses = [body("<html>maintenance</html>")]
    with pytest.raises(OpenDataParseError):
        await client.get_feed()


async def test_get_feed_network_error(fake, aiohttp_client):
    session = await aiohttp_client(fake.server)
    unreachable = OpenDataClient(
        session.session, peak_events_url="http://127.0.0.1:1/feed", request_timeout=2
    )
    with pytest.raises(OpenDataConnectionError):
        await unreachable.get_feed()


async def test_failed_refresh_does_not_clobber_cache(client, fake, winter_feed):
    fake.feed_responses = [json_ok(winter_feed), status(503), status(304)]

    first = await client.get_feed()
    with pytest.raises(OpenDataResponseError):
        await client.get_feed()
    third = await client.get_feed()

    assert third is first


async def test_concurrent_callers_are_serialized(client, fake, winter_feed):
    fake.feed_responses = [json_ok(winter_feed, etag='"v1"'), status(304)]

    first, second = await asyncio.gather(client.get_feed(), client.get_feed())

    assert first is second
    assert fake.feed_requests[1].get("If-None-Match") == '"v1"'


async def test_get_events_and_offers(client, fake, winter_feed):
    fake.feed_responses = [json_ok(winter_feed), status(304), status(304)]

    offers = await client.get_available_offers()
    all_events = await client.get_events()
    cpc_events = await client.get_events("Credit hivernal Residentiel (CPC-D)")

    assert "Flex Residentiel (TPC-DPC)" in offers
    assert len(all_events) == 4
    assert len(cpc_events) == 3


async def test_get_offer_labels_identity_until_upstream_ships_titles(client, fake, winter_feed):
    fake.feed_responses = [json_ok(winter_feed)]
    labels = await client.get_offer_labels()

    assert set(labels) == set(winter_feed["offresDisponibles"])
    # Until Hydro-Québec publishes display titles, labels equal the
    # canonical identifiers. Sourcing prettier labels later must not
    # change the keys.
    assert all(key == value for key, value in labels.items())


async def test_get_offer_descriptions_paginates(client, fake):
    def make_record(index):
        return {"offresdisponibles": f"OFFER_{index}", "description_fr": f"desc {index}"}

    fake.desc_pages = [
        {"total_count": 150, "results": [make_record(i) for i in range(100)]},
        {"total_count": 150, "results": [make_record(i) for i in range(100, 150)]},
    ]
    descriptions = await client.get_offer_descriptions()

    assert len(descriptions) == 150
    assert descriptions[0].offer == "OFFER_0"
    assert descriptions[-1].offer == "OFFER_149"


async def test_get_offer_descriptions_rate_limited(client, fake):
    fake.desc_status = 429
    with pytest.raises(OpenDataRateLimitError):
        await client.get_offer_descriptions()
