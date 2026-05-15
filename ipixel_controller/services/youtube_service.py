"""
YouTube data fetching service.

Provides functionality to fetch YouTube channel statistics using the
YouTube Data API v3.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, Any, Optional

from .api_fetcher import APIFetcher, CachingAPIFetcher

if TYPE_CHECKING:  # pragma: no cover
    import tkinter as tk


class YouTubeService(CachingAPIFetcher):
    """
    Service for fetching YouTube channel statistics.

    Uses YouTube Data API v3. Requires an API key from Google Cloud Console.

    Usage:
        def on_data(data):
            print(f"Subscribers: {data['subscriber_count']}")

        service = YouTubeService(root, on_data, on_error, api_key="YOUR_KEY")
        service.fetch(channel="@MrBeast")
    """

    def __init__(
        self,
        root: tk.Tk,
        on_success,
        on_error,
        on_start=None,
        api_key: str = "",
        cache_ttl_seconds: int = 60
    ):
        super().__init__(root, on_success, on_error, on_start, cache_ttl_seconds)
        self._api_key = api_key

    def set_api_key(self, key: str) -> None:
        """Set the YouTube API key."""
        self._api_key = key
        self.clear_cache()  # Clear cache when key changes

    def _fetch_data_impl(self) -> Dict[str, Any]:
        """Fetch YouTube channel statistics."""
        if not self._api_key:
            raise ValueError("YouTube API key is required. Get one from Google Cloud Console.")

        channel_input = self._params.get('channel', '')
        if not channel_input:
            raise ValueError("Channel ID or handle is required")

        try:
            from googleapiclient.discovery import build
        except ImportError:
            raise ImportError(
                "google-api-python-client not installed. "
                "Run: pip install google-api-python-client"
            )

        youtube = build('youtube', 'v3', developerKey=self._api_key)

        # Determine if input is handle (@username) or channel ID
        channel_id = channel_input
        if channel_input.startswith('@'):
            # Search for channel by handle
            search_response = youtube.search().list(
                part='snippet',
                q=channel_input,
                type='channel',
                maxResults=1
            ).execute()

            if not search_response.get('items'):
                raise ValueError(f"Channel not found: {channel_input}")

            channel_id = search_response['items'][0]['snippet']['channelId']

        # Get channel statistics
        channel_response = youtube.channels().list(
            part='snippet,statistics',
            id=channel_id
        ).execute()

        if not channel_response.get('items'):
            raise ValueError(f"Channel not found: {channel_id}")

        item = channel_response['items'][0]
        snippet = item['snippet']
        stats = item['statistics']

        return {
            'channel_id': channel_id,
            'title': snippet.get('title', 'Unknown'),
            'description': snippet.get('description', ''),
            'subscriber_count': int(stats.get('subscriberCount', 0)),
            'view_count': int(stats.get('viewCount', 0)),
            'video_count': int(stats.get('videoCount', 0)),
            'hidden_subscriber_count': stats.get('hiddenSubscriberCount', False),
            'thumbnail_url': snippet.get('thumbnails', {}).get('default', {}).get('url', ''),
        }


def format_youtube_display(
    data: Dict[str, Any],
    format_type: str = 'subscribers',
    max_chars: int = 16
) -> str:
    """
    Format YouTube data for LED display.

    Args:
        data: YouTube data dictionary from YouTubeService
        format_type: Display format:
            - 'subscribers': Just subscriber count
            - 'subs_views': Subscribers and views
            - 'channel_subs': Channel name and subscribers
        max_chars: Maximum characters for display

    Returns:
        Formatted string for display
    """
    subs = data.get('subscriber_count', 0)
    views = data.get('view_count', 0)
    title = data.get('title', 'Unknown')

    subs_str = _format_large_number(subs)
    views_str = _format_large_number(views)

    if format_type == 'subscribers':
        return subs_str

    elif format_type == 'subs_views':
        result = f"{subs_str} {views_str}V"
        return result[:max_chars]

    elif format_type == 'channel_subs':
        # Truncate title if needed
        max_title = max_chars - len(subs_str) - 1
        if len(title) > max_title:
            title = title[:max_title-2] + ".."
        result = f"{title} {subs_str}"
        return result[:max_chars]

    return subs_str


def _format_large_number(num: int) -> str:
    """
    Format a large number with K/M/B suffix.

    Args:
        num: Number to format

    Returns:
        Formatted string like "1.5M" or "450K"
    """
    if num >= 1_000_000_000:
        return f"{num / 1_000_000_000:.1f}B"
    elif num >= 1_000_000:
        return f"{num / 1_000_000:.1f}M"
    elif num >= 1_000:
        return f"{num / 1_000:.1f}K"
    else:
        return str(num)
