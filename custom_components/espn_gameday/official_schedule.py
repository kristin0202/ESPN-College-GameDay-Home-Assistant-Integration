"""Officially announced ESPN College GameDay locations.

These are fallback seeds for announcements that may age out of ESPN's
rolling news endpoint. Game details are still obtained dynamically from
the ESPN scoreboard API.
"""

from __future__ import annotations

from typing import Any


OFFICIAL_SCHEDULES: dict[int, dict[int, dict[str, Any]]] = {
    2026: {
        1: {
            "school": "LSU",
            "source_url": (
                "https://espnpressroom.com/press-release/"
                "espns-college-gameday-built-by-the-home-depot-"
                "kicks-off-40th-season-in-baton-rouge-with-500th-show-on-the-road/"
            ),
        },
        2: {
            "school": "Texas",
            "source_url": (
                "https://espnpressroom.com/press-release/"
                "espns-college-gameday-built-by-the-home-depot-"
                "kicks-off-40th-season-in-baton-rouge-with-500th-show-on-the-road/"
            ),
        },
    },
}


def get_official_schedule(season_year: int | None) -> dict[int, dict[str, Any]]:
    """Return officially announced GameDay locations for a season."""
    if season_year is None:
        return {}

    return OFFICIAL_SCHEDULES.get(int(season_year), {})
