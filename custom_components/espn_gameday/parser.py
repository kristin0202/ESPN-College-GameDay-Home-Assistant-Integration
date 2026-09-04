"""News-article parsing for GameDay announcements.

Design principle: NEVER GUESS. Every extraction must clear a confidence
threshold, and a location candidate is only accepted if it maps to a real
home team (or venue city) on the current week's schedule. Anything below
threshold degrades to TBA and can be filled with the override services.

This module is deliberately isolated: when ESPN changes phrasing, patch here.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from html import unescape
from typing import Any

# Phrases that indicate a destination announcement. Score +2.
DESTINATION_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"gameday\s+(?:is\s+)?(?:head(?:ed|ing)|going|comes?|coming|travel(?:s|ing)?|returns?)\s+(?:back\s+)?to\b",
        r"gameday\s+(?:will\s+be\s+)?(?:live\s+)?(?:at|in|from)\b",
        r"(?:hosts?|hosting|welcomes?)\s+(?:espn'?s\s+)?college\s+gameday",
        r"gameday\s+(?:is\s+)?(?:set|slated|scheduled|bound)\s+for\b",
        r"college\s+gameday\s+(?:location|site|destination)",
    )
]

# --- Guest-picker phrasing ---------------------------------------------
#
# The name capture stays case-SENSITIVE (it anchors on capitalised words), so
# the literal phrases carry scoped (?i:...) flags instead of a global
# re.IGNORECASE, which would let the name group swallow lowercase prose.
# A name token is either initials ("A.J.") or a plain capitalised word. Words
# deliberately exclude "." so the group cannot bleed across a sentence
# boundary ("...Baton Rouge. Lainey Wilson" must not capture "Rouge. Lainey").
_INITIALS = r"(?:[A-Z]\.){1,3}"
_WORD = r"[A-Z][\w'\-]+"
_TOKEN = rf"(?:{_INITIALS}|{_WORD})"
_NAME = rf"{_TOKEN}(?:\s+{_TOKEN}){{1,2}}"
# Optional appositive between the name and its verb: ", a Louisiana native,".
_APPOS = r"(?:,\s[^,]{1,60},)?"
# Optional auxiliary: ESPN writes "was announced", not "announced".
_AUX = r"(?:\s+(?:was|is|are|were|has\s+been|have\s+been|had\s+been|will\s+be|would\s+be|to\s+be))?"
_ACT = (
    r"(?:named|announced|revealed|tabbed|set|selected|tapped|picked"
    r"|serves?|serving|joins?|joining|will\s+serve|will\s+join)"
)
_PICKER = r"(?i:(?:celebrity\s+|special\s+|honorary\s+)?guest\s+picker)"

PICKER_PATTERNS = [
    re.compile(p)
    for p in (
        # "Lainey Wilson, a Louisiana native, was announced as the celebrity guest picker"
        rf"({_NAME}){_APPOS}{_AUX}\s+{_ACT}\s+(?:as\s+)?(?:the\s+)?{_PICKER}",
        # "Lainey Wilson is the guest picker" (auxiliary alone, no action verb)
        rf"({_NAME}){_APPOS}\s+(?:is|was|will\s+be)\s+(?:the\s+)?{_PICKER}",
        # "Guest picker: Lainey Wilson" / "the guest picker is Lainey Wilson"
        rf"{_PICKER}\s*(?:is|will\s+be|:)\s*({_NAME})",
    )
]

# Trailing sentence punctuation swept up by the name group.
_NAME_TRAILING = re.compile(r"[\s.,;:!?]+$")

PICKS_HEADLINE = re.compile(r"gameday.*\bpicks\b|\bpicks\b.*gameday", re.IGNORECASE)
# "Name: Team" or "Name picks Team" pairs inside recap text.
PICK_PAIR = re.compile(
    r"(?m)^\s*([A-Z][\w.'\- ]{2,30}?)\s*[:\u2014-]\s*([A-Z][\w.'&\- ]{2,40})\s*$"
)
PICK_VERB = re.compile(
    r"([A-Z][\w.'\-]+(?:\s+[A-Z][\w.'\-]+){0,2}?)\s+(?:picks?|takes?|went\s+with|goes?\s+with|chose)\s+(?:the\s+)?([A-Z][\w'&\-]+(?:\s+[A-Z][\w'&\-]+){0,3})"
)


@dataclass
class GameAliases:
    """Searchable name aliases for one scheduled game."""

    game_id: str
    home_name: str = ""
    home_aliases: set[str] = field(default_factory=set)
    venue_city: str = ""
    summary: dict[str, Any] = field(default_factory=dict)


def _mentions(needle: str, haystack_low: str) -> bool:
    """Word-boundary containment check (prevents 'lsu' inside other words)."""
    return bool(re.search(rf"\b{re.escape(needle)}\b", haystack_low))


_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")
# A tag boundary before punctuation ("announced</a>.") leaves a floating space.
_SPACE_BEFORE_PUNCT = re.compile(r"\s+([.,;:!?])")


def strip_html(html: str) -> str:
    """Flatten an ESPN story body to plain text.

    Tags collapse to a single space so adjacent blocks (``</h2><p>``) do not
    weld their words together, which would break the phrase patterns.
    """
    if not html:
        return ""
    flat = _WS.sub(" ", unescape(_TAG.sub(" ", html)))
    return _SPACE_BEFORE_PUNCT.sub(r"\1", flat).strip()


def wants_body(article: dict) -> bool:
    """True when this article is worth spending a body fetch on.

    The feed summary carries only headline + description; ESPN buries the
    picker's name in the story. Fetching every article each poll would be
    ~50 extra requests an hour, so only GameDay/picker headlines qualify,
    and only while the body has not already been attached.
    """
    if article.get("story"):
        return False
    headline = (article.get("headline") or "").lower()
    return "gameday" in headline or "picker" in headline


def _article_text(article: dict) -> str:
    """Headline + description + (when attached) the full story body."""
    base = f"{article.get('headline', '')}. {article.get('description', '')}"
    story = strip_html(article.get("story") or "")
    return f"{base} {story}".strip() if story else base


def _article_link(article: dict) -> str:
    links = article.get("links", {})
    return links.get("web", {}).get("href", "") if isinstance(links, dict) else ""


def build_game_aliases(events: list[dict]) -> list[GameAliases]:
    """Extract home-team + venue aliases from a scoreboard events list."""
    out: list[GameAliases] = []
    for ev in events:
        comps = (ev.get("competitions") or [{}])[0]
        competitors = comps.get("competitors") or []
        home = next(
            (c for c in competitors if c.get("homeAway") == "home"), None
        )
        if not home:
            continue
        team = home.get("team", {})
        aliases = {
            v.lower()
            for v in (
                team.get("location"),
                team.get("displayName"),
                team.get("shortDisplayName"),
                team.get("name"),
            )
            if v and len(v) >= 3
        }
        venue = comps.get("venue", {}) or {}
        city = (venue.get("address", {}) or {}).get("city", "") or ""
        out.append(
            GameAliases(
                game_id=str(ev.get("id", "")),
                home_name=team.get("location") or team.get("displayName") or "",
                home_aliases=aliases,
                venue_city=city,
                summary=ev,
            )
        )
    return out


EXPLICIT_WEEK = re.compile(r"\bweek\s+(\d{1,2})\b", re.IGNORECASE)


def find_locations(
    articles: list[dict], games_by_week: dict[int, list[GameAliases]]
) -> dict[int, dict]:
    """Return {week: candidate} for every announcement found.

    Week attribution:
    1. Explicit "Week N" in the article -> that week (confidence +1).
    2. Otherwise -> earliest week in the fetch window where the announced
       school hosts a home game; if it hosts in multiple fetched weeks
       (rare), confidence -1.
    """
    results: dict[int, dict] = {}
    for article in articles:
        text = _article_text(article)
        low = text.lower()
        if "gameday" not in low:
            continue
        score = 0
        if any(p.search(low) for p in DESTINATION_PATTERNS):
            score += 2
        if "gameday" in (article.get("headline") or "").lower():
            score += 1
        if score < 2:
            continue

        explicit = EXPLICIT_WEEK.search(text)
        explicit_week = int(explicit.group(1)) if explicit else None

        # Which weeks does this article's school map to?
        hits: list[tuple[int, str, str, bool]] = []  # (week, school, game_id, both)
        for week in sorted(games_by_week):
            for game in games_by_week[week]:
                alias_hit = any(_mentions(a, low) for a in game.home_aliases)
                city_hit = bool(game.venue_city) and _mentions(
                    game.venue_city.lower(), low
                )
                if alias_hit or city_hit:
                    hits.append(
                        (week, game.home_name or game.venue_city, game.game_id,
                         alias_hit and city_hit)
                    )
        if not hits:
            continue

        if explicit_week is not None:
            week_hits = [h for h in hits if h[0] == explicit_week]
            if not week_hits:
                continue  # explicit week doesn't match schedule: never guess
            week, school, game_id, both = week_hits[0]
            confidence = score + 1 + (1 if both else 0)
        else:
            week, school, game_id, both = hits[0]  # earliest week
            confidence = score + (1 if both else 0)
            if len({h[0] for h in hits if h[1] == school}) > 1:
                confidence -= 1  # same school hosts in multiple fetched weeks

        candidate = {
            "school": school,
            "game_id": game_id,
            "source_url": _article_link(article),
            "confidence": confidence,
            "published": article.get("published", ""),
        }
        if week not in results or candidate["confidence"] > results[week]["confidence"]:
            results[week] = candidate
    return results


def find_location(articles: list[dict], games: list[GameAliases]) -> dict | None:
    """Return {game_id, school, source_url, confidence} or None.

    Scoring: +2 destination phrase, +1 'gameday' in headline.
    A schedule match is REQUIRED. Accept at score >= 2.
    """
    best: dict | None = None
    for article in articles:
        text = _article_text(article)
        low = text.lower()
        if "gameday" not in low:
            continue
        score = 0
        if any(p.search(low) for p in DESTINATION_PATTERNS):
            score += 2
        if "gameday" in (article.get("headline") or "").lower():
            score += 1
        if score < 2:
            continue
        for game in games:
            hit = next((a for a in game.home_aliases if a in low), None)
            city_hit = game.venue_city and game.venue_city.lower() in low
            if not hit and not city_hit:
                continue
            candidate = {
                "game_id": game.game_id,
                "school": (hit or game.venue_city).title(),
                "source_url": _article_link(article),
                "confidence": score + (1 if hit and city_hit else 0),
                "published": article.get("published", ""),
            }
            if best is None or candidate["confidence"] > best["confidence"]:
                best = candidate
    return best


def find_picker(articles: list[dict]) -> dict | None:
    """Return {name, source_url} or None."""
    for article in articles:
        text = _article_text(article)
        if "gameday" not in text.lower():
            continue
        for pattern in PICKER_PATTERNS:
            match = pattern.search(text)
            if match:
                name = _NAME_TRAILING.sub("", match.group(1).strip())
                # Reject obvious false captures.
                if name.lower() in {"college gameday", "espn", "the show"}:
                    continue
                return {
                    "name": name,
                    "source_url": _article_link(article),
                    "published": article.get("published", ""),
                }
    return None


def find_picks(articles: list[dict]) -> dict | None:
    """Best-effort post-show picks: {picks: {name: team}, source_url}.

    Accepted limitation per PRD: ~50% weekly hit rate, 1-3h delay.
    """
    for article in articles:
        headline = article.get("headline", "")
        if not PICKS_HEADLINE.search(headline):
            continue
        text = _article_text(article)
        pairs: dict[str, str] = {}
        for match in PICK_PAIR.finditer(text):
            pairs[match.group(1).strip()] = match.group(2).strip()
        for match in PICK_VERB.finditer(text):
            pairs.setdefault(match.group(1).strip(), match.group(2).strip())
        if len(pairs) >= 3:  # require a real slate, not a stray sentence
            return {
                "picks": pairs,
                "source_url": _article_link(article),
                "published": article.get("published", ""),
            }
    return None
