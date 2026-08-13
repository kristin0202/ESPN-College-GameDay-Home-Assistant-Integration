"""Officially announced ESPN College GameDay host sites.

ESPN's news endpoint is a rolling feed of roughly 50 articles. Sites announced
months in advance — the season premiere is typically revealed in May — age out
of it long before the season starts, so the news parser can never rediscover
them. These entries are a durable, authoritative seed for exactly that case.

Only the host school is recorded here. Everything else (matchup, kickoff, TV,
odds, venue, ranks, colors, logos) still comes live from ESPN's scoreboard via
``_enrich_featured_game``, so this file never goes stale on game details and
never needs touching when a line moves or a team is re-ranked.

Precedence, lowest to highest: official seed < parsed announcement < manual
override. A seed never overwrites a week that already has a location, and
``espn_gameday.set_location`` always wins if ESPN relocates a show.

Maintenance: add a new season key each spring. Old seasons can stay; they are
selected by the season year ESPN reports, so they simply stop being consulted.
"""
from __future__ import annotations

from typing import Any

# {season_year: {week_number: entry}}
#
# entry keys:
#   school     - must match the ESPN home-team name for that week's game
#   published  - ISO8601 announcement date; becomes announced_at so a months-old
#                announcement never flashes as "new" after a restart
#   source_url - the announcement itself
OFFICIAL_SCHEDULES: dict[int, dict[int, dict[str, Any]]] = {
    2026: {
        1: {
            "school": "LSU",
            "published": "2026-05-12T00:00:00-04:00",
            "source_url": (
                "https://espnpressroom.com/us/press-releases/2026/05/"
                "espns-college-gameday-built-by-the-home-depot-kicks-off-"
                "40th-season-in-baton-rouge-with-500th-show-on-the-road/"
            ),
        },
        2: {
            "school": "Texas",
            "published": "2026-05-12T00:00:00-04:00",
            "source_url": (
                "https://espnpressroom.com/us/press-releases/2026/05/"
                "espns-college-gameday-built-by-the-home-depot-kicks-off-"
                "40th-season-in-baton-rouge-with-500th-show-on-the-road/"
            ),
        },
    },
}


def get_official_schedule(season_year: int | None) -> dict[int, dict[str, Any]]:
    """Officially announced host sites for a season, or {} if none are known."""
    if season_year is None:
        return {}
    try:
        return OFFICIAL_SCHEDULES.get(int(season_year), {})
    except (TypeError, ValueError):
        return {}
