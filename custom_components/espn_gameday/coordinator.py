"""DataUpdateCoordinator for ESPN College GameDay."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import EspnApiError, EspnClient
from .const import (
    CONF_FLAIR_TEAMS,
    DEFAULT_FLAIR_TEAMS,
    DOMAIN,
    EVENT_LOCATION,
    EVENT_PICKER,
    EVENT_PICKS,
    FRESH_WINDOW,
    INTERVAL_HOT,
    INTERVAL_IN_SEASON,
    INTERVAL_OFFSEASON,
    LOCAL_TZ,
    PHASE_IN_SEASON,
    PHASE_OFFSEASON,
    SHOW_END_HOUR_ET,
    SHOW_START_HOUR_ET,
    SHOW_TZ,
    STORAGE_KEY,
    STORAGE_VERSION,
)
from . import parser

_LOGGER = logging.getLogger(__name__)

ET = ZoneInfo(SHOW_TZ)
CT = ZoneInfo(LOCAL_TZ)


class GameDayCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Fetches ESPN data, runs parsers, manages phase + persistence."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=INTERVAL_IN_SEASON,
        )
        self.entry = entry
        self.client = EspnClient(async_get_clientsession(hass))
        self._store: Store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        # Persisted state: detected announcements + manual overrides.
        self.state: dict[str, Any] = {
            "location": None,
            "picker": None,
            "picks": None,
            "overrides": {},
        }
        raw = entry.data.get(CONF_FLAIR_TEAMS, DEFAULT_FLAIR_TEAMS)
        self.flair_teams = [t.strip().lower() for t in raw.split(",") if t.strip()]

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    async def async_load_store(self) -> None:
        stored = await self._store.async_load()
        if stored:
            self.state.update(stored)

    async def _async_save(self) -> None:
        await self._store.async_save(self.state)

    # ------------------------------------------------------------------
    # Override services
    # ------------------------------------------------------------------
    async def async_set_override(self, key: str, value: Any) -> None:
        self.state["overrides"][key] = {
            "value": value,
            "set_at": dt_util.utcnow().isoformat(),
        }
        await self._async_save()
        await self.async_request_refresh()

    async def async_clear_overrides(self) -> None:
        self.state["overrides"] = {}
        await self._async_save()
        await self.async_request_refresh()

    # ------------------------------------------------------------------
    # Update cycle
    # ------------------------------------------------------------------
    async def _async_update_data(self) -> dict[str, Any]:
        try:
            scoreboard = await self.client.get_scoreboard()
        except EspnApiError as err:
            raise UpdateFailed(str(err)) from err

        league = (scoreboard.get("leagues") or [{}])[0]
        season = league.get("season", {}) or {}
        season_start = _parse_iso(season.get("startDate"))
        season_end = _parse_iso(season.get("endDate"))
        season_year = season.get("year")
        week_number = (scoreboard.get("week") or {}).get("number")
        events = scoreboard.get("events") or []

        now = dt_util.utcnow()
        phase = (
            PHASE_IN_SEASON
            if season_start and season_end and season_start <= now <= season_end
            else PHASE_OFFSEASON
        )

        next_show, show_end = _next_show_window(now, season_start, season_end)

        # --- News parsing (skip network call deep offseason to be polite) ---
        articles: list[dict] = []
        if phase == PHASE_IN_SEASON or (
            season_start and now >= season_start - timedelta(days=21)
        ):
            try:
                articles = await self.client.get_news()
            except EspnApiError as err:
                _LOGGER.warning("News fetch failed (non-fatal): %s", err)

        games = parser.build_game_aliases(events)
        self._reconcile("location", parser.find_location(articles, games), EVENT_LOCATION)
        self._reconcile("picker", parser.find_picker(articles), EVENT_PICKER)

        # Picks: only look after the show window has closed, until end of Sunday.
        if show_end is None or now >= show_end or _is_sunday_ct(now):
            self._reconcile("picks", parser.find_picks(articles), EVENT_PICKS)

        location = self._effective("location")
        picker = self._effective("picker")
        picks = self._effective("picks")

        featured_game = _enrich_featured_game(location, events) if location else None
        flair_team = _match_flair(location, featured_game, self.flair_teams)

        # If the week rolled over and the stored location no longer maps to a
        # scheduled game, expire it (prevents last week's site lingering).
        if location and featured_game is None and not self._is_override("location"):
            _LOGGER.debug("Stored location no longer maps to a game; expiring.")
            self.state["location"] = None
            location = None
            flair_team = None

        await self._async_save()
        self.update_interval = self._compute_interval(now, phase, next_show)

        return {
            "phase": phase,
            "season_year": season_year,
            "week_number": week_number,
            "next_show": next_show,
            "show_end": show_end,
            "location": location,
            "picker": picker,
            "picks": picks,
            "featured_game": featured_game,
            "flair_team": flair_team,
            "fresh_until": self._fresh_until(),
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _is_override(self, key: str) -> bool:
        return key in self.state["overrides"]

    def _effective(self, key: str) -> dict | None:
        """Override wins over parsed state."""
        override = self.state["overrides"].get(key)
        if override:
            value = override["value"]
            base = dict(value) if isinstance(value, dict) else {"value": value}
            base["method"] = "manual"
            base["announced_at"] = override["set_at"]
            return base
        return self.state.get(key)

    def _reconcile(self, key: str, parsed: dict | None, event: str) -> None:
        """Store newly parsed data and fire the announcement event on change."""
        if parsed is None:
            return
        current = self.state.get(key)
        marker = parsed.get("school") or parsed.get("name") or str(parsed.get("picks"))
        current_marker = None
        if current:
            current_marker = (
                current.get("school") or current.get("name") or str(current.get("picks"))
            )
        if marker and marker != current_marker:
            parsed["announced_at"] = dt_util.utcnow().isoformat()
            parsed["method"] = "parsed"
            self.state[key] = parsed
            self.hass.bus.async_fire(event, parsed)
            _LOGGER.info("GameDay %s update: %s", key, marker)

    def _fresh_until(self) -> str | None:
        """Latest announced_at + FRESH_WINDOW across location/picker."""
        stamps = []
        for key in ("location", "picker"):
            data = self._effective(key)
            if data and data.get("announced_at"):
                parsed = _parse_iso(data["announced_at"])
                if parsed:
                    stamps.append(parsed)
        if not stamps:
            return None
        return (max(stamps) + FRESH_WINDOW).isoformat()

    @staticmethod
    def _compute_interval(
        now: datetime, phase: str, next_show: datetime | None
    ) -> timedelta:
        if phase == PHASE_OFFSEASON:
            # Tighten up in the 3 weeks before premiere so the first
            # announcement isn't missed.
            if next_show and (next_show - now) <= timedelta(days=21):
                return INTERVAL_IN_SEASON
            return INTERVAL_OFFSEASON
        local = now.astimezone(CT)
        weekday, hour = local.weekday(), local.hour
        if weekday == 5 and 5 <= hour < 12:  # Saturday show morning
            return INTERVAL_HOT
        if (weekday == 5 and hour >= 18) or weekday == 6:  # announcement window
            return INTERVAL_HOT
        return INTERVAL_IN_SEASON


# ----------------------------------------------------------------------
# Module-level pure helpers
# ----------------------------------------------------------------------
def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = dt_util.parse_datetime(value)
    except (ValueError, TypeError):
        return None
    if parsed and parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt_util.UTC)
    return parsed


def _next_show_window(
    now: datetime, season_start: datetime | None, season_end: datetime | None
) -> tuple[datetime | None, datetime | None]:
    """Next Saturday 9:00-12:00 ET that falls inside the season."""
    if not season_start or not season_end:
        return None, None
    cursor = max(now, season_start).astimezone(ET)
    for _ in range(0, 8):
        days_ahead = (5 - cursor.weekday()) % 7
        candidate = (cursor + timedelta(days=days_ahead)).replace(
            hour=SHOW_START_HOUR_ET, minute=0, second=0, microsecond=0
        )
        end = candidate.replace(hour=SHOW_END_HOUR_ET)
        if end <= now.astimezone(ET):
            cursor = candidate + timedelta(days=1)
            continue
        if candidate.astimezone(dt_util.UTC) > season_end:
            return None, None
        return candidate.astimezone(dt_util.UTC), end.astimezone(dt_util.UTC)
    return None, None


def _is_sunday_ct(now: datetime) -> bool:
    return now.astimezone(CT).weekday() == 6


def _enrich_featured_game(location: dict, events: list[dict]) -> dict | None:
    """Pull matchup/kickoff/TV/odds for the game GameDay is at."""
    target = None
    game_id = location.get("game_id")
    school = (location.get("school") or "").lower()
    for ev in events:
        if game_id and str(ev.get("id")) == str(game_id):
            target = ev
            break
        comps = (ev.get("competitions") or [{}])[0]
        for comp in comps.get("competitors") or []:
            team = comp.get("team", {})
            names = {
                (team.get("location") or "").lower(),
                (team.get("displayName") or "").lower(),
            }
            if school and school in names and comp.get("homeAway") == "home":
                target = ev
                break
        if target:
            break
    if not target:
        return None

    comps = (target.get("competitions") or [{}])[0]
    competitors = comps.get("competitors") or []

    def _side(side: str) -> dict:
        comp = next((c for c in competitors if c.get("homeAway") == side), {})
        team = comp.get("team", {})
        rank = (comp.get("curatedRank") or {}).get("current")
        return {
            "name": team.get("displayName"),
            "abbr": team.get("abbreviation"),
            "rank": rank if rank and rank != 99 else None,
        }

    home, away = _side("home"), _side("away")
    broadcast = ""
    broadcasts = comps.get("broadcasts") or []
    if broadcasts:
        names = broadcasts[0].get("names") or []
        broadcast = names[0] if names else ""
    odds = (comps.get("odds") or [{}])[0]
    venue = comps.get("venue", {}) or {}

    def _fmt(team: dict) -> str:
        prefix = f"#{team['rank']} " if team.get("rank") else ""
        return f"{prefix}{team.get('name') or '?'}"

    return {
        "matchup": f"{_fmt(away)} at {_fmt(home)}",
        "home": home,
        "away": away,
        "kickoff": target.get("date"),
        "tv": broadcast,
        "spread": odds.get("details"),
        "over_under": odds.get("overUnder"),
        "venue": venue.get("fullName"),
        "city": (venue.get("address", {}) or {}).get("city"),
        "state": (venue.get("address", {}) or {}).get("state"),
    }


def _match_flair(
    location: dict | None, featured_game: dict | None, flair_teams: list[str]
) -> str | None:
    """Return the matched flair team name (lowercase) if host site matches."""
    candidates: set[str] = set()
    if location and location.get("school"):
        candidates.add(location["school"].lower())
    if featured_game:
        home = featured_game.get("home", {})
        for value in (home.get("name"), home.get("abbr")):
            if value:
                candidates.add(value.lower())
    for flair in flair_teams:
        for cand in candidates:
            if flair in cand or cand in flair:
                return flair
    return None
