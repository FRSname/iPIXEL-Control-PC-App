"""Instagram follower-count fetching service.

Talks to the Instagram Graph API (graph.facebook.com) for IG Business or
Creator accounts. Requires:

- ``ig_user_id`` — the IG Business Account ID (17-digit number, looks like
  ``17841...``). Obtained once via Graph API Explorer.
- ``access_token`` — a User Access Token with ``instagram_basic`` scope,
  or a non-expiring System User token.

Long-lived user tokens last 60 days; ``refresh_long_lived_token`` extends
them another 60 days if the caller supplies ``app_id`` + ``app_secret``.
System User tokens don't expire and never need refresh.
"""

from __future__ import annotations

import json
from typing import Any, Dict
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen


GRAPH_API_VERSION = "v21.0"
GRAPH_BASE = f"https://graph.facebook.com/{GRAPH_API_VERSION}"


def _http_get_json(url: str, timeout: float = 10.0) -> Dict[str, Any]:
    try:
        with urlopen(url, timeout=timeout) as resp:
            payload = resp.read().decode("utf-8", errors="replace")
    except HTTPError as e:
        body = e.read().decode("utf-8", errors="replace") if e.fp else ""
        try:
            data = json.loads(body)
            msg = data.get("error", {}).get("message") or body or str(e)
        except Exception:
            msg = body or str(e)
        raise RuntimeError(f"Instagram API error: {msg}") from None
    except URLError as e:
        raise RuntimeError(f"Network error: {e.reason}") from None

    try:
        return json.loads(payload)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Bad JSON from Instagram API: {e}") from None


def fetch_follower_count(ig_user_id: str, access_token: str) -> Dict[str, Any]:
    """Fetch followers_count + username for one IG Business account.

    Returns a dict shaped like::

        {"username": "metro_tesin", "follower_count": 1433,
         "media_count": 87, "ig_user_id": "17841..."}
    """
    if not ig_user_id:
        raise ValueError("Instagram user ID required. Save it under Settings.")
    if not access_token:
        raise ValueError("Instagram access token required. Save it under Settings.")

    qs = urlencode(
        {
            "fields": "followers_count,follows_count,media_count,username,name",
            "access_token": access_token,
        }
    )
    data = _http_get_json(f"{GRAPH_BASE}/{ig_user_id}?{qs}")
    return {
        "ig_user_id": str(data.get("id", ig_user_id)),
        "username": data.get("username", ""),
        "name": data.get("name", ""),
        "follower_count": int(data.get("followers_count", 0)),
        "follows_count": int(data.get("follows_count", 0)),
        "media_count": int(data.get("media_count", 0)),
    }


def refresh_long_lived_token(
    short_or_long_token: str, app_id: str, app_secret: str
) -> Dict[str, Any]:
    """Exchange (or refresh) a token for a fresh 60-day long-lived token.

    Returns ``{"access_token": "...", "expires_in": 5183999}`` on success.
    Works for both:

    - Short-lived User Access Token → first-time exchange.
    - Existing long-lived token within its 60-day window → another 60 days.

    Not needed for non-expiring System User tokens.
    """
    if not (short_or_long_token and app_id and app_secret):
        raise ValueError(
            "Refresh needs token, App ID and App Secret. "
            "System User tokens don't require refresh."
        )
    qs = urlencode(
        {
            "grant_type": "fb_exchange_token",
            "client_id": app_id,
            "client_secret": app_secret,
            "fb_exchange_token": short_or_long_token,
        }
    )
    data = _http_get_json(f"{GRAPH_BASE}/oauth/access_token?{qs}")
    if "access_token" not in data:
        raise RuntimeError(f"No access_token in response: {data}")
    return {
        "access_token": data["access_token"],
        "expires_in": int(data.get("expires_in", 0)),
    }


def _format_large_number(num: int) -> str:
    """Format a large number with K/M/B suffix (1.5M, 450K, ...)."""
    if num >= 1_000_000_000:
        return f"{num / 1_000_000_000:.1f}B"
    if num >= 1_000_000:
        return f"{num / 1_000_000:.1f}M"
    if num >= 10_000:
        return f"{num // 1_000}K"
    if num >= 1_000:
        return f"{num / 1_000:.1f}K"
    return str(num)


def format_instagram_display(
    data: Dict[str, Any],
    format_type: str = "count_short",
    max_chars: int = 16,
) -> str:
    """Format follower data for the LED panel."""
    count = data.get("follower_count", 0)
    username = data.get("username", "")
    name = data.get("name", "") or username

    count_short = _format_large_number(count)
    count_full = str(count)

    if format_type == "count_short":
        return count_short
    if format_type == "count_full":
        return count_full[:max_chars]
    if format_type == "username_count":
        room = max_chars - len(count_short) - 1
        handle = f"@{username}" if username else "IG"
        if len(handle) > room:
            handle = handle[: max(1, room - 1)] + "."
        return f"{handle} {count_short}"[:max_chars]
    if format_type == "followers_label":
        return f"FOLLOWERS {count_short}"[:max_chars]
    if format_type == "name_count":
        room = max_chars - len(count_short) - 1
        if len(name) > room:
            name = name[: max(1, room - 2)] + ".."
        return f"{name} {count_short}"[:max_chars]
    return count_short
