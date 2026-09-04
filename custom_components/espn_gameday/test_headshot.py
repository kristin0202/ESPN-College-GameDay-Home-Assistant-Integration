"""Tests for guest-picker headshot resolution.

Wikipedia lead images are frequently full-body stage or sideline shots. ESPN
(athletes) and Deezer (musicians) both serve real headshots and need no API
key, but neither can be called from the browser -- Deezer sends no
access-control-allow-origin -- so selection happens here, server side.

Payloads below are trimmed from live responses captured 2026-09-04.

Run:
    python3 custom_components/espn_gameday/test_headshot.py
"""
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def _load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


headshot = _load("headshot")

ESPN_MANNING = {"results": [
    {"type": "player", "contents": [
        {"displayName": "Peyton Manning",
         "image": {"default": "https://a.espncdn.com/i/headshots/nfl/players/full/1428.png"}}]},
    {"type": "article", "contents": [{"displayName": "Peyton Manning tributes"}]},
]}
ESPN_EMPTY = {"results": [{"type": "article", "contents": [{"displayName": "Lainey Wilson"}]}]}

def dz(name, fans, pic="https://cdn-images.dzcdn.net/images/artist/abc/500x500-000000-80-0-0.jpg"):
    return {"data": [{"name": name, "nb_fan": fans, "picture_xl": pic, "picture_big": pic}]}

DZ_LAINEY = dz("Lainey Wilson", 55491)
DZ_CORSO = dz("Leecose", 5)                       # wrong artist entirely
DZ_MANNING = dz("Peyton Manning", 0)              # novelty upload, no photo
DZ_MCAFEE = dz("Pat McAfee", 4)                   # novelty upload
DZ_NO_PHOTO = dz("Somebody", 90000, "https://cdn-images.dzcdn.net/images/artist//500x500-000000-80-0-0.jpg")

FAILURES = []


def check(name, fn):
    try:
        fn()
    except (AssertionError, AttributeError, TypeError) as err:
        FAILURES.append(f"{name}: {err}")
        print(f"FAIL {name}\n     {err}")
    else:
        print(f"ok   {name}")


# --- ESPN --------------------------------------------------------------
def test_espn_returns_the_player_headshot():
    got = headshot.pick_espn(ESPN_MANNING, "Peyton Manning")
    assert got == "https://a.espncdn.com/i/headshots/nfl/players/full/1428.png", got


def test_espn_ignores_article_hits():
    assert headshot.pick_espn(ESPN_EMPTY, "Lainey Wilson") is None


def test_espn_rejects_a_player_whose_name_does_not_match():
    # A search for a celebrity must not latch onto some unrelated athlete.
    payload = {"results": [{"type": "player", "contents": [
        {"displayName": "Willie Wilson",
         "image": {"default": "https://a.espncdn.com/i/headshots/mlb/players/full/9.png"}}]}]}
    assert headshot.pick_espn(payload, "Lainey Wilson") is None


def test_espn_tolerates_a_player_with_no_image():
    payload = {"results": [{"type": "player", "contents": [{"displayName": "Peyton Manning"}]}]}
    assert headshot.pick_espn(payload, "Peyton Manning") is None


# --- Deezer ------------------------------------------------------------
def test_deezer_returns_a_real_artist_photo():
    assert headshot.pick_deezer(DZ_LAINEY, "Lainey Wilson") is not None


def test_deezer_rejects_a_near_miss_name():
    # "Lee Corso" matched an unrelated artist called "Leecose".
    assert headshot.pick_deezer(DZ_CORSO, "Lee Corso") is None


def test_deezer_rejects_a_novelty_upload_with_no_following():
    # Exact name, but 0 fans -- not the real person.
    assert headshot.pick_deezer(DZ_MANNING, "Peyton Manning") is None
    assert headshot.pick_deezer(DZ_MCAFEE, "Pat McAfee") is None


def test_deezer_rejects_the_placeholder_image():
    # Deezer serves /artist// with no id when the artist has no photo.
    assert headshot.pick_deezer(DZ_NO_PHOTO, "Somebody") is None


def test_deezer_name_match_ignores_case_and_punctuation():
    assert headshot.pick_deezer(dz("LAINEY WILSON", 55491), "Lainey Wilson") is not None
    assert headshot.pick_deezer(dz("Jelly Roll", 900000), "Jelly  Roll") is not None


# --- Ordering ----------------------------------------------------------
def test_athletes_prefer_espn_over_deezer():
    got = headshot.choose("Peyton Manning", espn=ESPN_MANNING, deezer=DZ_LAINEY)
    assert "espncdn" in (got or ""), f"expected the ESPN headshot, got {got!r}"


def test_musicians_fall_through_to_deezer():
    got = headshot.choose("Lainey Wilson", espn=ESPN_EMPTY, deezer=DZ_LAINEY)
    assert "dzcdn" in (got or ""), f"expected the Deezer photo, got {got!r}"


def test_no_source_yields_none_so_the_card_falls_back():
    assert headshot.choose("Lee Corso", espn=ESPN_EMPTY, deezer=DZ_CORSO) is None


def test_choose_tolerates_missing_payloads():
    assert headshot.choose("Anyone", espn=None, deezer=None) is None


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            check(name, fn)
    print()
    if FAILURES:
        print(f"{len(FAILURES)} FAILED")
        sys.exit(1)
    print("all passed")
