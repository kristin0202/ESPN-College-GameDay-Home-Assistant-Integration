"""Guest-picker headshot resolution.

Wikipedia's lead image is whatever editors chose -- for a musician that is
usually a full-body stage shot, which crops badly to a small round tile. ESPN
(athletes) and Deezer (musicians) both publish actual headshots and need no API
key, so try those first and let Wikipedia remain the last resort.

This lives in the integration rather than the card because Deezer serves no
access-control-allow-origin header, so a browser cannot call it at all.

Selection is deliberately strict: a wrong face is worse than no face.
"""
from __future__ import annotations

import re
from typing import Any

# Deezer matches loosely and its catalogue is full of tribute and soundalike
# uploads: "Lee Corso" returns an artist called "Leecose" (5 fans), and
# "Peyton Manning" returns a namesake with 0 fans and no photo. Require an
# exact name and a real following.
DEEZER_MIN_FANS = 1000

_PUNCT = re.compile(r"[^a-z0-9]+")


def normalize(name: str | None) -> str:
    """Casefold and strip punctuation/extra spaces for name comparison."""
    return _PUNCT.sub(" ", (name or "").lower()).strip()


def pick_espn(payload: Any, name: str) -> str | None:
    """Headshot for an athlete or coach from ESPN's search results."""
    if not isinstance(payload, dict):
        return None
    want = normalize(name)
    for result in payload.get("results") or []:
        if result.get("type") != "player":
            continue
        for item in result.get("contents") or []:
            if normalize(item.get("displayName")) != want:
                continue
            image = item.get("image")
            url = image.get("default") if isinstance(image, dict) else None
            if url:
                return url
    return None


def pick_deezer(payload: Any, name: str, min_fans: int = DEEZER_MIN_FANS) -> str | None:
    """Artist photo from Deezer, behind an exact-name and following check."""
    if not isinstance(payload, dict):
        return None
    want = normalize(name)
    for artist in payload.get("data") or []:
        if normalize(artist.get("name")) != want:
            continue
        if (artist.get("nb_fan") or 0) < min_fans:
            continue
        url = artist.get("picture_xl") or artist.get("picture_big") or ""
        # Deezer emits an id-less path ("/artist//") when there is no photo.
        if not url or "/artist//" in url:
            continue
        return url
    return None


def choose(name: str, espn: Any = None, deezer: Any = None) -> str | None:
    """Best available headshot, or None to leave the card's fallback in charge.

    ESPN goes first: it is unambiguous for athletes and correctly returns
    nothing for everyone else, so it cannot shadow a musician's photo.
    """
    return pick_espn(espn, name) or pick_deezer(deezer, name)
