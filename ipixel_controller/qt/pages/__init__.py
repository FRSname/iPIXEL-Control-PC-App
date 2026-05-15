"""Page widgets for each section of the Qt UI."""

from .base import Page
from .home import HomePage
from .text_page import TextPage
from .image_page import ImagePage
from .clock_page import ClockPage
from .animation_page import AnimationPage
from .stock_page import StockPage
from .weather_page import WeatherPage
from .youtube_page import YoutubePage
from .instagram_page import InstagramPage
from .draw_page import DrawPage
from .settings_page import SettingsPage
from .placeholder import PlaceholderPage

__all__ = [
    "Page",
    "HomePage",
    "TextPage",
    "ImagePage",
    "ClockPage",
    "AnimationPage",
    "StockPage",
    "WeatherPage",
    "YoutubePage",
    "InstagramPage",
    "DrawPage",
    "SettingsPage",
    "PlaceholderPage",
]
