# hydropeak-opendata

Async Python client for Hydro-Québec's public **peak events** (pointes hivernales) open data. No account, no login — just the open data feed.

Extracted from the [HydroPeak](https://github.com/Beat-YT/hydropeak-ha) Home Assistant integration.

## Data sources

Data comes from [Hydro-Québec's open data portal](https://donnees.hydroquebec.com/explore/dataset/evenements-pointe/information/).

During Quebec winters (December 1 to March 31), Hydro-Québec triggers **peak demand events** (_événements de pointe_) when electricity demand is high due to cold weather and operational constraints. Customers enrolled in participating offers (e.g. Winter Credit, Flex, Hilo) are asked to reduce their consumption during these events — typically in the morning (AM) or evening (PM) — and receive bill credits in return. The dataset is updated as events are scheduled, and covers both residential and business customers.

- **[Peak events](https://donnees.hydroquebec.com/explore/dataset/evenements-pointe/information/)** — scheduled peak demand events with start/end times, time period (AM/PM), duration, applicable offer, and customer sector.
- **[Available offers](https://donnees.hydroquebec.com/explore/dataset/evenements-de-pointe-offres-disponibles/information/)** — the list of programs available each season, with descriptions and validity dates (rate limited; intended for occasional use such as setup flows).

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

Example output:

```
2026-01-22 06:00:00-05:00  2026-01-22 09:00:00-05:00  AM  3:00:00
2026-01-22 16:00:00-05:00  2026-01-22 20:00:00-05:00  PM  4:00:00
```

Check if a peak event is happening right now:

```python
from datetime import datetime, timezone

events = await client.get_events()
now = datetime.now(timezone.utc)
active = [e for e in events if e.is_active(now)]
```

Notes:

- Offer identifiers are the strings published in `offresDisponibles`, used verbatim. The library applies no transformation; `get_events(offer)` filters by exact match.
- `get_offer_labels()` maps each canonical offer identifier to a display label for UIs. Labels currently equal the identifiers; once Hydro-Québec publishes display titles in its open data, a library update will source labels from there without any change to the method's contract — persist the keys, show the values.
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
