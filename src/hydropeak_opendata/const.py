"""Constants for the Hydro-Québec peak events open data."""

from __future__ import annotations

import re
from datetime import timedelta
from typing import Final

PEAK_EVENTS_URL: Final = (
    "https://donnees.solutions.hydroquebec.com/donnees-ouvertes/data/json/pointeshivernales.json"
)
OFFER_DESCRIPTIONS_URL: Final = (
    "https://donnees.hydroquebec.com/api/explore/v2.1/catalog/datasets"
    "/evenements-de-pointe-offres-disponibles/records"
)
DESCRIPTIONS_PAGE_SIZE: Final = 100
DESCRIPTION_GRACE: Final = timedelta(days=60)
PEAK_EVENTS_TABLE_URL: Final = (
    "https://donnees.hydroquebec.com/explore/dataset/evenements-pointe/table/"
)

# Hydro-Québec publishes the same offer under different names depending on
# the source: the offer descriptions dataset and the historical events
# dataset use bare codes ("TPC-DPC"), while ``offresDisponibles`` and the
# events of ``pointeshivernales.json`` use display names that wrap the code
# ("Flex Residentiel (TPC-DPC)"). Every known spelling maps to its code here.
OFFER_CODE_ALIASES: Final[dict[str, str]] = {
    "Credit hivernal Residentiel (CPC-D)": "CPC-D",
    "Credit hivernal Affaires (CPC-G)": "CPC-G",
    "Flex Residentiel (TPC-DPC)": "TPC-DPC",
    "Flex Affaires (TPC-GPC)": "TPC-GPC",
}

# Fallback for display names not in OFFER_CODE_ALIASES: a trailing
# parenthesized code, e.g. "Flex D (TPC-DPC)" -> "TPC-DPC". ``\w`` is
# Unicode-aware, so accented letters inside the code still match.
OFFER_CODE_PATTERN: Final = re.compile(r"\(\s*(\w[\w-]*)\s*\)\s*$")
