"""Tests for fetching ESPN story bodies.

api.py is stdlib + aiohttp only, so it loads standalone once a synthetic
parent package exists for its relative `.const` import. The aiohttp session is
stubbed; nothing here touches the network.

Run:
    python3 test_article_bodies.py
"""
import asyncio
import importlib
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parent

_pkg = types.ModuleType("espn_gameday")
_pkg.__path__ = [str(ROOT)]
sys.modules["espn_gameday"] = _pkg

api = importlib.import_module("espn_gameday.api")
parser = importlib.import_module("espn_gameday.parser")

BODY_URL = "https://content.core.api.espn.com/v1/sports/news/49816722"
STORY = "<p>Lainey Wilson was announced as the celebrity guest picker.</p>"

# Verbatim shape of the content-API response.
CONTENT_PAYLOAD = {
    "resultsCount": 1,
    "headlines": [{"id": "49816722", "headline": "2026 'College GameDay' Week 1", "story": STORY}],
}


class FakeResponse:
    def __init__(self, status, payload):
        self.status = status
        self._payload = payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def json(self, content_type=None):
        return self._payload


class FakeSession:
    """Serves canned payloads per URL and records what was requested."""

    def __init__(self, routes):
        self.routes = routes
        self.requested = []

    def get(self, url, params=None, timeout=None):
        self.requested.append(url)
        status, payload = self.routes.get(url, (404, {}))
        return FakeResponse(status, payload)


FAILURES = []


def check(name, fn):
    try:
        asyncio.run(fn()) if asyncio.iscoroutinefunction(fn) else fn()
    except (AssertionError, AttributeError, TypeError) as err:
        FAILURES.append(f"{name}: {err}")
        print(f"FAIL {name}\n     {err!r}")
    else:
        print(f"ok   {name}")


def _article(url=BODY_URL, headline="2026 'College GameDay' Week 1: guest picker"):
    links = {"web": {"href": "https://espn.com/story"}}
    if url:
        links["api"] = {"self": {"href": url}}
    return {"headline": headline, "description": "GameDay heads to Baton Rouge.", "links": links}


# --- Tests -------------------------------------------------------------

async def test_get_article_story_returns_story_html():
    client = api.EspnClient(FakeSession({BODY_URL: (200, CONTENT_PAYLOAD)}))
    assert await client.get_article_story(BODY_URL) == STORY


async def test_get_article_story_empty_when_no_headlines():
    client = api.EspnClient(FakeSession({BODY_URL: (200, {"headlines": []})}))
    assert await client.get_article_story(BODY_URL) == ""


async def test_get_article_story_raises_on_http_error():
    client = api.EspnClient(FakeSession({BODY_URL: (500, {})}))
    try:
        await client.get_article_story(BODY_URL)
    except api.EspnApiError:
        return
    raise AssertionError("expected EspnApiError on HTTP 500")


async def test_attach_stories_sets_story_on_article():
    art = _article()
    client = api.EspnClient(FakeSession({BODY_URL: (200, CONTENT_PAYLOAD)}))
    await client.attach_stories([art])
    assert art.get("story") == STORY, f"got {art.get('story')!r}"


async def test_attach_stories_skips_article_with_no_api_link():
    art = _article(url=None)
    session = FakeSession({})
    await api.EspnClient(session).attach_stories([art])
    assert session.requested == [], f"fetched anyway: {session.requested}"
    assert "story" not in art


async def test_attach_stories_survives_one_failure():
    good_url = "https://content.core.api.espn.com/v1/sports/news/2"
    bad, good = _article(), _article(url=good_url)
    client = api.EspnClient(FakeSession({BODY_URL: (500, {}), good_url: (200, CONTENT_PAYLOAD)}))
    await client.attach_stories([bad, good])
    assert bad.get("story") in (None, ""), f"bad article got {bad.get('story')!r}"
    assert good.get("story") == STORY, "a sibling failure must not block the good fetch"


async def test_attached_story_makes_the_picker_findable():
    """The whole point: feed summary alone yields nothing, body yields the name."""
    art = _article()
    assert parser.find_picker([dict(art)]) is None
    await api.EspnClient(FakeSession({BODY_URL: (200, CONTENT_PAYLOAD)})).attach_stories([art])
    found = parser.find_picker([art])
    assert found and found["name"] == "Lainey Wilson", f"got {found!r}"


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            check(name, fn)
    print()
    if FAILURES:
        print(f"{len(FAILURES)} FAILED")
        sys.exit(1)
    print("all passed")
