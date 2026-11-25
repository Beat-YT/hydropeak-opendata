# hydropeak-opendata

Async Python client for Hydro-Québec's public **peak events** (pointes hivernales) open data. No account, no login — just the open data feed.

Powers the [Hydro-Québec Peak Events](https://www.home-assistant.io/integrations/hydroquebec_peak/) integration in Home Assistant.

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

List the offers of one sector, e.g. for a setup form:

```python
from datetime import date
from hydropeak_opendata import Sector

offers = await client.get_sector_offers(Sector.RESIDENTIAL, date.today())
# ('Credit hivernal Residentiel (CPC-D)', 'Flex Residentiel (TPC-DPC)')
```

Check that a configured offer is still published:

```python
if not await client.is_offer_available(saved_offer, date.today()):
    ...  # Hydro-Québec no longer lists this offer
```

Notes:

- Offer identifiers are the strings published in `offresDisponibles`, returned verbatim.
- Hydro-Québec names the same offer differently across sources: the feed uses display names (`Flex Residentiel (TPC-DPC)`) while the offers and historical events datasets use bare codes (`TPC-DPC`). `get_events(offer)` matches on the normalized code, ignoring accents, letter case and extra whitespace, so `TPC-DPC`, `tpc-dpc` and `Flex Résidentiel (TPC-DPC)` all select the same events. `normalize_offer_code()` exposes that mapping (its known aliases live in `OFFER_CODE_ALIASES` in `const.py`), and `PeakEvent.offer_code` gives the code for an event.
- `build_events_table_url(offer)` returns a link to the peak events table on the open data portal, refined to that offer. When the offer differs from its code (`Flex Residentiel (TPC-DPC)`), both spellings are refined; a bare code refines on the code alone.
- `get_offer_labels()` maps each canonical offer identifier to a display label for UIs. Labels currently equal the identifiers; once Hydro-Québec publishes display titles in its open data, a library update will source labels from there without any change to the method's contract — persist the keys, show the values.
- `get_sector_offers(sector, today)` lists the feed's offers plus offers from the offer descriptions dataset that have not ended by `today`, merged across spellings with the feed's spelling kept. `CPC-D` and `TPC-DPC` are residential; any other offer is residential only if its description says so, and business otherwise. If the descriptions endpoint fails, the feed alone is used.
- `is_offer_available(offer, today)` tells whether an offer is still published: listed in the feed in any spelling, or in an offer description that ended at most 60 days before `today`. Descriptions are only fetched when the feed does not list the offer; if that fails, the feed alone decides.
- Both methods take `today` from the caller, so the date follows the caller's timezone and tests can pin it.
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
