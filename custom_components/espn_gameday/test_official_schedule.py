"""Tests for the official-schedule seed, its helpers, and the seed's guard rails.

Dependency-free by design. coordinator.py imports Home Assistant at module
scope, so instead of importing it these tests extract the pure functions and
the seed method from source and run them against a stub coordinator. That
keeps every assertion live — an earlier version of this file silently skipped
when the import failed, which is worse than having no test at all.

Run from the repo root:
    python3 tests/test_official_schedule.py
"""
import importlib.util
import re
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "custom_components" / "espn_gameday"
COORDINATOR_SRC = (ROOT / "coordinator.py").read_text()


def _load_module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


official_schedule = _load_module("official_schedule")
get_official_schedule = official_schedule.get_official_schedule


def _extract_function(pattern, namespace=None):
    match = re.search(pattern, COORDINATOR_SRC, re.S | re.M)
    assert match, f"could not locate {pattern!r} in coordinator.py"
    ns = dict(namespace or {})
    exec(textwrap.dedent(match.group(0)), ns)
    return ns


_find_home_game_id = _extract_function(
    r"^def _find_home_game_id\(.*?(?=^def )"
)["_find_home_game_id"]


def _event(game_id, home_location, away="Visitor"):
    return {
        "id": game_id,
        "competitions": [
            {
                "competitors": [
                    {
                        "homeAway": "home",
                        "team": {
                            "location": home_location,
                            "displayName": f"{home_location} Team",
                            "shortDisplayName": home_location,
                            "abbreviation": home_location[:3].upper(),
                        },
                    },
                    {"homeAway": "away", "team": {"location": away}},
                ]
            }
        ],
    }


# --- official_schedule data ------------------------------------------


def test_2026_schedule_has_both_announced_weeks():
    schedule = get_official_schedule(2026)
    assert schedule[1]["school"] == "LSU"
    assert schedule[2]["school"] == "Texas"


def test_seeds_carry_publication_date_not_install_time():
    for entry in get_official_schedule(2026).values():
        assert entry["published"].startswith("2026-05-12")
        assert entry["source_url"].startswith("https://")


def test_unknown_season_is_empty():
    assert get_official_schedule(2027) == {}
    assert get_official_schedule(None) == {}
    assert get_official_schedule("not-a-year") == {}


def test_season_year_accepts_string_from_espn():
    assert get_official_schedule("2026")[1]["school"] == "LSU"


# --- _find_home_game_id ----------------------------------------------


def test_home_game_id_matches_host_school():
    events = [_event("401", "Clemson"), _event("402", "LSU")]
    assert _find_home_game_id("LSU", events) == "402"


def test_home_game_id_ignores_away_appearances():
    """Texas playing AT Ohio State must not satisfy a Texas-hosted seed."""
    assert _find_home_game_id("Texas", [_event("500", "Ohio State", away="Texas")]) is None


def test_home_game_id_returns_none_when_absent():
    assert _find_home_game_id("Washington", [_event("401", "LSU")]) is None


# --- _seed_official_schedule behavior --------------------------------


class _Bus:
    def __init__(self, sink):
        self.sink = sink

    def async_fire(self, event, data):
        self.sink.append((event, data))


class _Hass:
    def __init__(self, sink):
        self.bus = _Bus(sink)


class _StubCoordinator:
    """Minimal stand-in exposing only what the seed method touches."""

    def __init__(self, primary_week=1, schedule=None, overrides=None):
        self.primary_week = primary_week
        self.state = {"schedule": schedule or {}, "overrides": overrides or {}}
        self.fired = []
        self.hass = _Hass(self.fired)


_SEED = _extract_function(
    r"^ {4}def _seed_official_schedule\(.*?(?=\n {4}def )",
    {
        "get_official_schedule": get_official_schedule,
        "_find_home_game_id": _find_home_game_id,
        "_LOGGER": type("L", (), {"info": staticmethod(lambda *a, **k: None)})(),
        "Any": object,
    },
)["_seed_official_schedule"]

EVENTS = {1: [_event("402", "LSU")], 2: [_event("610", "Texas")]}


def test_seed_populates_empty_schedule():
    c = _StubCoordinator(primary_week=1)
    _SEED(c, 2026, EVENTS)
    assert c.state["schedule"]["1"]["school"] == "LSU"
    assert c.state["schedule"]["1"]["game_id"] == "402"
    assert c.state["schedule"]["1"]["method"] == "official"
    assert c.state["schedule"]["2"]["school"] == "Texas"
    assert c.state["schedule"]["2"]["game_id"] == "610"


def test_seed_never_fires_an_announcement_event():
    """A months-old seed is not news; firing would notify on every install."""
    c = _StubCoordinator(primary_week=1)
    _SEED(c, 2026, EVENTS)
    assert c.fired == []


def test_seed_uses_publication_date_as_announced_at():
    c = _StubCoordinator(primary_week=1)
    _SEED(c, 2026, EVENTS)
    assert c.state["schedule"]["1"]["announced_at"].startswith("2026-05-12")


def test_seed_does_not_resurrect_past_weeks():
    """Guards the seed/rollover fight that would re-add week 1 on every poll."""
    c = _StubCoordinator(primary_week=3)
    _SEED(c, 2026, EVENTS)
    assert c.state["schedule"] == {}


def test_manual_override_beats_seed():
    c = _StubCoordinator(primary_week=1, overrides={"location:1": {"value": {}}})
    _SEED(c, 2026, EVENTS)
    assert "1" not in c.state["schedule"]


def test_seed_does_not_overwrite_existing_location():
    c = _StubCoordinator(
        primary_week=1, schedule={"1": {"school": "Relocated", "method": "parsed"}}
    )
    _SEED(c, 2026, EVENTS)
    assert c.state["schedule"]["1"]["school"] == "Relocated"


def test_seed_tolerates_missing_scoreboard_data():
    """No games fetched yet -> still record the school, game_id None."""
    c = _StubCoordinator(primary_week=1)
    _SEED(c, 2026, {})
    assert c.state["schedule"]["1"]["school"] == "LSU"
    assert c.state["schedule"]["1"]["game_id"] is None


def test_unknown_season_seeds_nothing():
    c = _StubCoordinator(primary_week=1)
    _SEED(c, 2030, EVENTS)
    assert c.state["schedule"] == {}


if __name__ == "__main__":
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS {name}")
            except AssertionError as err:
                failures += 1
                print(f"FAIL {name}: {err}")
    print("\nOK — all tests executed" if not failures else f"\n{failures} failure(s)")
    sys.exit(1 if failures else 0)
