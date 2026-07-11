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

PICKER_PATTERNS = [
    re.compile(p)
    for p in (
        r"([A-Z][\w.'\-]+(?:\s+[A-Z][\w.'\-]+){1,2})\s+(?:will\s+(?:be|serve|join)|named|announced|revealed|tabbed|set)\s+(?:as\s+)?(?:the\s+)?(?:celebrity\s+)?guest\s+picker",
        r"guest\s+picker\s*(?:is|will\s+be|:)\s*([A-Z][\w.'\-]+(?:\s+[A-Z][\w.'\-]+){1,2})",
        r"([A-Z][\w.'\-]+(?:\s+[A-Z][\w.'\-]+){1,2})\s+(?:to\s+)?(?:serves?|joins?)\s+as\s+(?:the\s+)?guest\s+picker",
    )
]

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


def _article_text(article: dict) -> str:
    return f"{article.get('headline', '')}. {article.get('description', '')}"


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
                name = match.group(1).strip()
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
