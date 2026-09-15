"""Tests for GameDay location extraction.

Dependency-free, matching the rest of the suite. Article text is verbatim
from ESPN's content API; team names and venue cities are verbatim from the
FBS scoreboard for the same weeks:
  story https://content.core.api.espn.com/v1/sports/news/49816722  (Week 1)
  story https://content.core.api.espn.com/v1/sports/news/49904999  (Week 2)
  story https://content.core.api.espn.com/v1/sports/news/49783645  (schedule page)

Run:
    python3 test_parser_location.py
"""
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def _load_module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


parser = _load_module("parser")


def _game(game_id, location, display, short, name, city):
    """Minimal scoreboard event: one home team at one venue city."""
    return {
        "id": game_id,
        "competitions": [{
            "competitors": [{
                "homeAway": "home",
                "team": {
                    "location": location,
                    "displayName": display,
                    "shortDisplayName": short,
                    "name": name,
                },
            }],
            "venue": {"address": {"city": city}},
        }],
    }


LSU = ("LSU", "LSU Tigers", "LSU", "Tigers", "Baton Rouge")
LOUISIANA = ("Louisiana", "Louisiana Ragin' Cajuns", "Louisiana", "Ragin' Cajuns", "Lafayette")
TEXAS = ("Texas", "Texas Longhorns", "Texas", "Longhorns", "Austin")
OHIO = ("Ohio", "Ohio Bobcats", "Ohio", "Bobcats", "Athens")
OLE_MISS = ("Ole Miss", "Ole Miss Rebels", "Ole Miss", "Rebels", "Oxford")
MIAMI_OH = ("Miami (OH)", "Miami (OH) RedHawks", "Miami OH", "RedHawks", "Oxford")


def _week(*games):
    """Aliases for a week's games, in the order given.

    Decoys are listed FIRST on purpose: ESPN's event order is arbitrary, so
    a correct pick must not depend on which game happens to come first.
    """
    return parser.build_game_aliases(
        [_game(str(i), *g) for i, g in enumerate(games)]
    )


def _article(headline, description, story=""):
    return {
        "headline": headline,
        "description": description,
        "story": story,
        "links": {"web": {"href": "https://example.test/a"}},
        "published": "2026-09-11T16:46:07Z",
    }


# --- Real fixtures -----------------------------------------------------

WEEK1 = _article(
    "2026 'College GameDay' Week 1: Matchup, guest picker, more",
    '"College GameDay" heads to Baton Rouge, Louisiana for Week 1.',
    '<h2>Week 1 location</h2>\n<p>"<a href="https://promo.espn.com/collegegameday/">'
    'College GameDay Built by The Home Depot</a>" will be in Baton Rouge, Louisiana at '
    'the LSU Quad for <a href="https://www.espn.com/college-football/team/_/id/228/'
    'clemson-tigers">Clemson</a> at <a href="https://www.espn.com/college-football/team'
    '/_/id/99/lsu-tigers">LSU</a>. It will be the program\'s 500th show on the road and '
    'LSU head coach Lane Kiffin will join live on set.</p>\n',
)

WEEK2 = _article(
    "2026 'College GameDay' Week 2: Matchup, guest picker, more",
    '"College GameDay" heads to Austin for Week 2.',
    '<h2>Week 2 location</h2>\n<p>"<a href="https://promo.espn.com/collegegameday/">'
    'College GameDay Built by The Home Depot</a>" will be in Austin at the LBJ Lawn for '
    '<a href="https://www.espn.com/college-football/game/_/gameId/401856682/'
    'ohio-state-texas">Ohio State at Texas</a>.</p>\n<h2>Who is the guest picker for '
    'Week 2?</h2>\n<p>"The Running Man" actor and Austin native, Glen Powell, was '
    'announced as the celebrity guest picker for Week 2.</p>\n',
)

SCHEDULE_PAGE = _article(
    "Where is 'College GameDay'? 2026 schedule, locations, recaps",
    'What is the "College GameDay" schedule? Find out more about where the program '
    "will be each week of the 2026 college football season.",
    '<p>"<a href="https://promo.espn.com/collegegameday/">College GameDay Built by The '
    'Home Depot</a>" is back! The 40th season of "College GameDay" kicks off its 33rd '
    "year of road shows.</p>\n<p>See below for more details on where \"College GameDay\" "
    "will be each week of the 2026 college football season.</p>\n<h2>Where will "
    '"College GameDay" be in Week 3?</h2>\n<p>"College GameDay" visits Oxford, '
    "Mississippi for LSU vs. Ole Miss.</p>\n<h2>\"College GameDay\" locations</h2>\n"
    "<ul>\n<li><em>Week 1</em>: Baton Rouge</li>\n<li><em>Week 2</em>: Austin</li>\n</ul>\n",
)

FAILURES = []


def check(name, fn):
    try:
        fn()
    except (AssertionError, AttributeError, TypeError, KeyError) as err:
        FAILURES.append(f"{name}: {err}")
        print(f"FAIL {name}\n     {err}")
    else:
        print(f"ok   {name}")


def _school(results, week):
    entry = results.get(week)
    return entry["school"] if entry else None


# --- Destination phrasing ----------------------------------------------

def test_quoted_show_name_heads_to():
    low = '"college gameday" heads to austin for week 2.'
    assert parser.has_destination(low), low


def test_sponsor_name_will_be_in():
    low = '"college gameday built by the home depot" will be in austin at the lbj lawn.'
    assert parser.has_destination(low), low


def test_quoted_show_name_visits():
    low = '"college gameday" visits oxford, mississippi for lsu vs. ole miss.'
    assert parser.has_destination(low), low


def test_existing_destination_phrasings_still_match():
    for low in (
        "college gameday is heading to columbus",
        "gameday will be live from ann arbor",
        "michigan hosts espn's college gameday",
        "gameday is set for tuscaloosa",
    ):
        assert parser.has_destination(low), low


def test_no_destination_in_unrelated_gameday_prose():
    for low in (
        "rece davis hosts the three-hour show from 9 a.m. to noon et.",
        "the gameday crew made their picks on saturday.",
    ):
        assert not parser.has_destination(low), low


# --- Real articles against the real schedule ---------------------------

def test_real_week1_article_places_show_at_lsu():
    # "Baton Rouge, Louisiana" must not hand the show to the Ragin' Cajuns.
    weeks = {1: _week(LOUISIANA, LSU)}
    got = parser.find_locations([WEEK1], weeks)
    assert _school(got, 1) == "LSU", f"got {got!r}"


def test_real_week2_article_places_show_at_texas():
    # "Ohio State at Texas" must not hand the show to the Ohio Bobcats.
    weeks = {2: _week(OHIO, TEXAS), 3: _week(TEXAS)}
    got = parser.find_locations([WEEK2], weeks)
    assert _school(got, 2) == "Texas", f"got {got!r}"
    assert 3 not in got, f"leaked into week 3: {got!r}"


def test_real_schedule_page_places_week3_at_ole_miss():
    # The recap list ("Week 2: Austin") must not count for Texas, which also
    # hosts in Austin in Week 3.
    weeks = {3: _week(TEXAS, OLE_MISS), 4: _week(MIAMI_OH, LSU)}
    got = parser.find_locations([SCHEDULE_PAGE], weeks)
    assert _school(got, 3) == "Ole Miss", f"got {got!r}"
    assert set(got) == {3}, f"unexpected weeks: {got!r}"


def test_result_carries_game_id_and_source():
    weeks = {2: _week(OHIO, TEXAS)}
    entry = parser.find_locations([WEEK2], weeks)[2]
    assert entry["game_id"] == "1", entry  # TEXAS is index 1 in _week()
    assert entry["source_url"] == "https://example.test/a", entry


# --- Never guess --------------------------------------------------------

def test_two_equally_strong_schools_yields_nothing():
    article = _article(
        "College GameDay Week 2 update",
        '"College GameDay" heads to Austin or Athens, Texas or Ohio, for Week 2.',
    )
    weeks = {2: _week(OHIO, TEXAS)}
    got = parser.find_locations([article], weeks)
    assert got == {}, f"guessed: {got!r}"


def test_explicit_week_not_on_schedule_yields_nothing():
    weeks = {3: _week(TEXAS)}
    got = parser.find_locations([WEEK2], weeks)  # says Week 2; only week 3 fetched
    assert got == {}, f"guessed: {got!r}"


def test_school_named_only_outside_announcement_yields_nothing():
    article = _article(
        "College GameDay notebook",
        '"College GameDay" heads to a mystery site for Week 2. Texas won big.',
    )
    weeks = {2: _week(TEXAS)}
    got = parser.find_locations([article], weeks)
    assert got == {}, f"guessed: {got!r}"


def test_bare_gameday_in_is_not_an_announcement():
    # Verbatim, 2025 "Lee Corso's impact felt far beyond 'College GameDay'
    # audience". Ohio State hosts in 2026 Week 3, so a loose "gameday in"
    # pattern placed the show in Columbus.
    article = _article(
        "Lee Corso's impact felt far beyond 'College GameDay' audience",
        "",
        "<p>It's hard to remember when we see the current Herbie, the "
        "father-of-four statesman of the sport, but when he first joined "
        '"College GameDay" in 1996, he had just turned 27, less than four '
        "years out of Ohio State.</p>",
    )
    ohio_state = ("Ohio State", "Ohio State Buckeyes", "Ohio State", "Buckeyes", "Columbus")
    weeks = {3: _week(ohio_state)}
    got = parser.find_locations([article], weeks)
    assert got == {}, f"guessed: {got!r}"


def test_non_gameday_article_is_ignored():
    article = _article("Texas notebook", "The Longhorns head to Austin for Week 2.")
    weeks = {2: _week(TEXAS)}
    assert parser.find_locations([article], weeks) == {}


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            check(name, fn)
    print()
    if FAILURES:
        print(f"{len(FAILURES)} FAILED")
        sys.exit(1)
    print("all passed")
