# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```
pip install -e .[dev]
ruff check .
mypy
pytest
pytest tests/test_client.py::test_get_feed_revalidates_with_etag
pytest -k normalize
```

CI runs ruff, mypy (strict) and pytest on Python 3.11 to 3.13. Pushing a `v*` tag builds and publishes to PyPI via trusted publishing; the version lives in `pyproject.toml`.

## Architecture

Async client library for Hydro-Québec's peak events open data, and the library behind Home Assistant's core `hydroquebec_peak` integration (Hydro-Québec Peak Events, added in 2026.11, source under `homeassistant/components/hydroquebec_peak` in `home-assistant/core`). Every release reaches Home Assistant users. The integration polls the feed every 15 minutes and creates one device per configured offer. Code is in `src/hydropeak_opendata/`.

Two upstream endpoints with different roles:

- **Peak events feed** (`pointeshivernales.json`): polled frequently. Served as `text/plain`, so the client parses with `json.loads` instead of `response.json()`. `get_feed()` sends `If-None-Match` and returns the cached `PeakEventsFeed` object on 304; an `asyncio.Lock` serializes concurrent callers. A failed refresh leaves the cache intact.
- **Offer descriptions** (Opendatasoft `evenements-de-pointe-offres-disponibles`): rate limited (429) and sometimes down. Intended for occasional use like setup flows, never polling. Paginated transparently, not cached.

Library contracts consumers rely on:

- The aiohttp session is injected and never closed by the client.
- `offresDisponibles` strings are returned verbatim; the library matches them through normalization (see Offer naming). `get_offer_labels()` values are currently identical to keys.
- Failures raise `OpenDataError` subclasses (connection, rate limit, response status, parse); nothing silently returns empty data.
- Models are frozen dataclasses with tuples, so cached objects are safe to share.

## Offer naming

Hydro-Québec's offer identifiers are not stable. In 2024-25 and 2025-26, events and descriptions used bare codes (`TPC-DPC`); the 2026-27 data uses display names wrapping the code (`Flex Residentiel (TPC-DPC)`). Spelling flips without notice: the feed had display names on 2026-08-15 and bare codes on 2026-08-25 (Wayback Machine), went display name, bare code, display name again in September, and the descriptions dataset flipped too, lagging the feed and only returning to display names in November. The two sources can disagree at the same moment. A single publish is usually internally consistent. Accent/case variants also appear. All matching goes through `normalize_offer_code()` in `models.py`: known aliases from `OFFER_CODE_ALIASES` in `const.py`, then a trailing `(CODE)` regex fallback, with `_fold()` stripping accents, case and extra whitespace. `events_for_offer()` compares folded normalized codes; `build_events_table_url()` refines on both the given spelling and the code. Offers without a code (`OEA`, `ENG_100H_2F_7J`) pass through unchanged.

## Upstream data quirks (observed November 2026)

- The descriptions dataset holds several seasons at once (one record per offer per season), including offers no longer in the feed. Seasons run December 1 to March 31, so `active_on=today` before December returns nothing for the upcoming season.
- Some offers were restructured, not renamed: `GDP-Affaires` and `ENG01`..`ENG20` (2025-26) appear to be replaced by the `ENG_*` / `LAT_*` modalities (descriptions call them GDP Engagement / GDP Latitude). Normalization cannot map these, so an old saved offer can match nothing.
- `type_clientele` is free text, not an enum (`residentielle`, `affaires`, accented variants seen).
- The feed's `secteurClient` only exists on events, so offers with no events this season have no sector from the feed.
- `offresDisponibles` has been populated in every snapshot seen, off-season included (11 offers with zero events on 2024-12-11, 38 in August 2026). The 2024-12-11 feed had no `derniereExecution` key at all.
- The feed sometimes contains test events (e.g. `Essai_Mardis_Nov`).
- `derniereExecution` is a naive timestamp with no published timezone; event datetimes carry offsets.
- In the big 4 offer codes, D means rate D (residential) and G means rate G (business).

## Tests

`tests/test_client.py` runs the client against a local aiohttp server (`FakeOpenData`). `feed_responses` is a queue of response factories and every `get_feed()` call consumes one, including calls made indirectly through `get_events()` and friends, so queue a `status(304)` for each extra call. `feed_summer_2026.json` is the real feed from August 2026; `feed_winter.json` is synthetic.
