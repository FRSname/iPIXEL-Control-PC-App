"""Business logic services (no UI dependencies)."""

from .api_fetcher import APIFetcher, CachingAPIFetcher
from .sprite_font import SpriteFontService, SpriteFont, speed_to_interval_ms
from .stock_service import StockService, format_stock_display, get_stock_color
from .youtube_service import YouTubeService, format_youtube_display
from .weather_service import WeatherService, format_weather_display, get_weather_icon_name
from .animation_generator import (
    AnimationGenerator,
    AnimationState,
    AnimationType,
    ColorScheme,
)

__all__ = [
    # Base classes
    'APIFetcher',
    'CachingAPIFetcher',

    # Sprite fonts
    'SpriteFontService',
    'SpriteFont',
    'speed_to_interval_ms',

    # Stock
    'StockService',
    'format_stock_display',
    'get_stock_color',

    # YouTube
    'YouTubeService',
    'format_youtube_display',

    # Weather
    'WeatherService',
    'format_weather_display',
    'get_weather_icon_name',

    # Animations
    'AnimationGenerator',
    'AnimationState',
    'AnimationType',
    'ColorScheme',
]
