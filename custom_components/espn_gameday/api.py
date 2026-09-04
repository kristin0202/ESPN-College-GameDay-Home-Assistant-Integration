"""Thin async client for ESPN's unofficial college football endpoints."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp

from .const import (
    DEEZER_ARTIST_URL,
    ESPN_SEARCH_URL,
    NEWS_LIMIT,
    NEWS_URL,
    RANKINGS_URL,
    SCOREBOARD_URL,
)

_LOGGER = logging.getLogger(__name__)


class EspnApiError(Exception):
    """Raised when ESPN returns an error or unexpected payload."""


class EspnClient:
    """Fetches scoreboard and news JSON from ESPN's site API."""

    def __init__(self, session: aiohttp.ClientSession) -> None:
        self._session = session

    async def _get(self, url: str, params: dict[str, Any] | None = None) -> dict:
        try:
            async with self._session.get(
                url, params=params, timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                if resp.status != 200:
                    raise EspnApiError(f"ESPN returned HTTP {resp.status} for {url}")
                data = await resp.json(content_type=None)
        except aiohttp.ClientError as err:
            raise EspnApiError(f"Network error talking to ESPN: {err}") from err
        if not isinstance(data, dict):
            raise EspnApiError(f"Unexpected payload shape from {url}")
        return data

    async def get_scoreboard(self, week: int | None = None) -> dict:
        """Current (or specified) week scoreboard, incl. season calendar."""
        params: dict[str, Any] = {"groups": "80"}  # FBS
        if week is not None:
            params["week"] = week
        return await self._get(SCOREBOARD_URL, params)

    async def get_rankings(self) -> list[dict]:
        """Current polls (AP / Coaches / CFP), each with its top-25 ranks.

        The scoreboard only carries a usable curatedRank for the week that is
        actually in play — every future week reports 99 — so ranked matchups
        for the lookahead weeks have to come from here.
        """
        data = await self._get(RANKINGS_URL)
        rankings = data.get("rankings", [])
        return rankings if isinstance(rankings, list) else []

    @staticmethod
    def _body_url(article: dict) -> str:
        """ESPN's content-API href for an article's full story, if present."""
        links = article.get("links")
        if not isinstance(links, dict):
            return ""
        api_links = links.get("api")
        if not isinstance(api_links, dict):
            return ""
        return (api_links.get("self") or {}).get("href", "")

    async def get_article_story(self, url: str) -> str:
        """Full story HTML for one article, via ESPN's content API.

        The news feed carries only headline + description; announcements like
        the guest picker live in the body, so it has to be fetched separately.
        """
        data = await self._get(url)
        headlines = data.get("headlines")
        if not isinstance(headlines, list) or not headlines:
            return ""
        first = headlines[0]
        return first.get("story", "") if isinstance(first, dict) else ""

    async def attach_stories(self, articles: list[dict]) -> None:
        """Fetch bodies for `articles` and attach each as ``story``, in place.

        Bodies are best-effort: one article's failure must not take down the
        rest of the poll, so every fetch is isolated.
        """
        targets = [(a, self._body_url(a)) for a in articles]
        targets = [(a, url) for a, url in targets if url]
        if not targets:
            return
        results = await asyncio.gather(
            *(self.get_article_story(url) for _, url in targets),
            return_exceptions=True,
        )
        for (article, url), result in zip(targets, results):
            if isinstance(result, BaseException):
                _LOGGER.debug("Story fetch failed for %s: %s", url, result)
                continue
            if result:
                article["story"] = result

    async def search_person(self, name: str) -> dict:
        """ESPN site search -- carries a real headshot for athletes/coaches."""
        return await self._get(ESPN_SEARCH_URL, {"query": name, "limit": 5})

    async def search_artist(self, name: str) -> dict:
        """Deezer artist search -- square press photos for musicians."""
        return await self._get(DEEZER_ARTIST_URL, {"q": name, "limit": 3})

    async def get_news(self) -> list[dict]:
        """Recent CFB news articles (headline, description, links, published)."""
        data = await self._get(NEWS_URL, {"limit": NEWS_LIMIT})
        articles = data.get("articles", [])
        return articles if isinstance(articles, list) else []
