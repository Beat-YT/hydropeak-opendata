"""Constants for the Hydro-Québec peak events open data."""

from __future__ import annotations

import re
from typing import Final

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

# Fallback for display names not listed above: a trailing parenthesized
# code, e.g. "Flex D (TPC-DPC)" -> "TPC-DPC".
_TRAILING_CODE: Final = re.compile(r"\(\s*([A-Za-z0-9][A-Za-z0-9_-]*)\s*\)\s*$")


def normalize_offer_code(offer: str) -> str:
    """Return the offer code that ``offer`` refers to.

    Accepts either a bare code (returned as-is) or any known display name
    for it, so ``"TPC-DPC"`` and ``"Flex Residentiel (TPC-DPC)"`` both
    normalize to ``"TPC-DPC"``. Offers that carry no code, such as ``"OEA"``
    or ``"ENG_100H_2F_7J"``, are returned unchanged (whitespace-stripped).
    """
    offer = offer.strip()
    if (code := OFFER_CODE_ALIASES.get(offer)) is not None:
        return code
    if (match := _TRAILING_CODE.search(offer)) is not None:
        return match.group(1)
    return offer
