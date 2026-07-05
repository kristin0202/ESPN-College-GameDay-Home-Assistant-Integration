"""Thin async client for ESPN's unofficial college football endpoints."""
from __future__ import annotations

import logging
from typing import Any

import aiohttp

from .const import NEWS_LIMIT, NEWS_URL, SCOREBOARD_URL

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

    async def get_news(self) -> list[dict]:
        """Recent CFB news articles (headline, description, links, published)."""
        data = await self._get(NEWS_URL, {"limit": NEWS_LIMIT})
        articles = data.get("articles", [])
        return articles if isinstance(articles, list) else []
