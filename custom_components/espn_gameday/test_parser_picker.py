"""Tests for guest-picker extraction.

Dependency-free by design, matching test_official_schedule.py: parser.py is
pure stdlib, so it is loaded directly and exercised with real ESPN payloads
captured from the live endpoints.

Fixtures below are verbatim from the Week 1 2026 announcement:
  feed  https://site.api.espn.com/apis/site/v2/.../news?limit=50
  story https://content.core.api.espn.com/v1/sports/news/49816722

Run:
    python3 test_parser_picker.py
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

# --- Real fixtures -----------------------------------------------------

WEEK1_STORY = (
    '<p><video1></p>\n<h2>Week 1 location</h2>\n<p>"<a href="https://promo.espn.com/'
    'collegegameday/">College GameDay Built by The Home Depot</a>" will be in Baton '
    'Rouge, Louisiana at the LSU Quad for <a href="https://www.espn.com/college-football'
    '/team/_/id/228/clemson-tigers">Clemson</a> at <a href="https://www.espn.com/'
    'college-football/team/_/id/99/lsu-tigers">LSU</a>. It will be the program\'s 500th '
    'show on the road and LSU head coach Lane Kiffin will join live on set.</p>\n'
    '<h2>Who is the celebrity picker for Week 1?</h2>\n<p>Country singer/songwriter '
    'Lainey Wilson, a Louisiana native, was announced as the celebrity guest picker '
    'for Week 1.</p>\n'
)

WEEK1_ARTICLE = {
    "id": "49816722",
    "type": "Story",
    "headline": "2026 'College GameDay' Week 1: Matchup, guest picker, more",
    "description": '"College GameDay" heads to Baton Rouge, Louisiana for Week 1.',
    "published": "2026-09-03T20:12:27Z",
    "links": {
        "api": {"self": {"href": "https://content.core.api.espn.com/v1/sports/news/49816722"}},
        "web": {"href": "https://www.espn.com/college-football/story/_/id/49816722/"
                        "2026-college-gameday-week-1-matchup-guest-picker-more"},
    },
}

UNRELATED_ARTICLE = {
    "headline": "Colorado rallies, blocks Georgia Tech's walk-off field goal try",
    "description": "Freshman quarterback Julian Lewis led a clutch two-minute drill.",
    "links": {"web": {"href": "https://www.espn.com/x"}},
}

FAILURES = []


def check(name, fn):
    try:
        fn()
    except (AssertionError, AttributeError, TypeError) as err:
        FAILURES.append(f"{name}: {err}")
        print(f"FAIL {name}\n     {err}")
    else:
        print(f"ok   {name}")


def _picker_name(text):
    """Run find_picker against a single synthetic article carrying `text`."""
    article = {
        "headline": "College GameDay news",
        "description": text,
        "links": {"web": {"href": "https://example.test/a"}},
    }
    found = parser.find_picker([article])
    return found["name"] if found else None


# --- Tests -------------------------------------------------------------

def test_strip_html_drops_tags_and_keeps_sentence():
    text = parser.strip_html("<p>Lainey Wilson was <a href='#'>announced</a>.</p>")
    assert "<" not in text, f"tags survived: {text!r}"
    assert "Lainey Wilson was announced." in text, f"got {text!r}"


def test_strip_html_inserts_space_between_blocks():
    text = parser.strip_html("<h2>Week 1</h2><p>Lainey Wilson</p>")
    assert "Week 1 Lainey Wilson" in text, f"blocks ran together: {text!r}"


def test_wants_body_true_for_gameday_headline():
    assert parser.wants_body(WEEK1_ARTICLE) is True


def test_wants_body_false_for_unrelated_headline():
    assert parser.wants_body(UNRELATED_ARTICLE) is False


def test_wants_body_false_when_story_already_present():
    already = dict(WEEK1_ARTICLE, story=WEEK1_STORY)
    assert parser.wants_body(already) is False


def test_real_week1_article_yields_picker_from_story():
    article = dict(WEEK1_ARTICLE, story=WEEK1_STORY)
    found = parser.find_picker([article])
    assert found is not None, "no picker found in the real Week 1 story"
    assert found["name"] == "Lainey Wilson", f"got {found['name']!r}"
    assert found["source_url"].endswith("matchup-guest-picker-more"), found["source_url"]


def test_headline_and_description_alone_still_yield_nothing():
    # The name genuinely is not in the feed summary; must not be invented.
    assert parser.find_picker([dict(WEEK1_ARTICLE)]) is None


def test_auxiliary_was_announced_as():
    assert _picker_name("Lainey Wilson was announced as the celebrity guest picker.") == "Lainey Wilson"


def test_auxiliary_was_named():
    assert _picker_name("Lainey Wilson was named the guest picker.") == "Lainey Wilson"


def test_auxiliary_has_been_named():
    assert _picker_name("Lainey Wilson has been named the guest picker.") == "Lainey Wilson"


def test_auxiliary_is_the_guest_picker():
    assert _picker_name("Lainey Wilson is the guest picker this week.") == "Lainey Wilson"


def test_appositive_between_name_and_verb():
    got = _picker_name(
        "Country singer/songwriter Lainey Wilson, a Louisiana native, was "
        "announced as the celebrity guest picker for Week 1."
    )
    assert got == "Lainey Wilson", f"got {got!r}"


def test_name_has_no_trailing_punctuation():
    got = _picker_name("The guest picker is Lainey Wilson.")
    assert got == "Lainey Wilson", f"trailing punctuation leaked: {got!r}"


def test_does_not_bleed_across_a_sentence_boundary():
    # The name group must not glue the previous sentence's last word on.
    got = _picker_name(
        "GameDay heads to Baton Rouge. Lainey Wilson was announced as the guest picker."
    )
    assert got == "Lainey Wilson", f"got {got!r}"


def test_keeps_initials_in_a_name():
    got = _picker_name("A.J. Hawk was announced as the guest picker.")
    assert got == "A.J. Hawk", f"got {got!r}"


def test_existing_phrasings_still_match():
    for text in (
        "Lainey Wilson will be the guest picker.",
        "Lainey Wilson announced as the celebrity guest picker for Week 1.",
        "Lainey Wilson joins as the guest picker.",
        "Guest picker: Lainey Wilson",
    ):
        got = _picker_name(text)
        assert got == "Lainey Wilson", f"{text!r} -> {got!r}"


def test_rejects_show_name_as_picker():
    assert _picker_name("College GameDay is the guest picker.") is None


def test_unrelated_article_yields_nothing():
    assert parser.find_picker([UNRELATED_ARTICLE]) is None


def test_non_gameday_story_is_ignored_even_with_picker_phrase():
    stray = {
        "headline": "NBA notes",
        "description": "Some Guy was named the guest picker.",
        "links": {"web": {"href": "https://example.test/b"}},
    }
    assert parser.find_picker([stray]) is None


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            check(name, fn)
    print()
    if FAILURES:
        print(f"{len(FAILURES)} FAILED")
        sys.exit(1)
    print("all passed")
