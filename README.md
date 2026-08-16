# hydropeak-opendata

Async Python client for Hydro-Québec's public **peak events** (pointes hivernales) open data. No account, no login — just the open data feed.

Extracted from the [HydroPeak](https://github.com/Beat-YT/hydropeak-ha) Home Assistant integration.

## Data sources

- **Peak events feed** — `pointeshivernales.json`: available offers (canonical, verbatim) and scheduled peak events.
- **Offer descriptions** — the `evenements-de-pointe-offres-disponibles` Opendatasoft dataset (rate limited; intended for occasional use such as setup flows).

## Usage

```python
import aiohttp
from hydropeak_opendata import OpenDataClient

async def main():
    async with aiohttp.ClientSession() as session:
        client = OpenDataClient(session)

        offers = await client.get_available_offers()
        # ('Credit hivernal Residentiel (CPC-D)', 'Flex Residentiel (TPC-DPC)', ...)

        events = await client.get_events(offers[0])
        for event in events:
            print(event.start, event.end, event.period, event.duration)
```

Notes:

- Offer identifiers are the strings published in `offresDisponibles`, used verbatim. The library applies no transformation; `get_events(offer)` filters by exact match.
- The client sends conditional requests (`If-None-Match`) and serves its cached parse on `304 Not Modified`, so frequent polling is cheap for both sides. Concurrent refreshes are serialized on a lock.
- All datetimes from the feed are timezone-aware. `PeakEventsFeed.last_execution` is naive (the feed publishes it without an offset).
- Errors raise typed exceptions: `OpenDataConnectionError`, `OpenDataRateLimitError`, `OpenDataResponseError`, `OpenDataParseError` — all subclasses of `OpenDataError`. Failures never silently return empty data.

## Development

```
pip install -e .[dev]
ruff check .
mypy
pytest
```

## License

MIT
