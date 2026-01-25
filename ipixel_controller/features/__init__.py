"""Feature plugin modules."""

from .base import FeatureBase
from .image_feature import ImageFeature
from .text_feature import TextFeature
from .clock_feature import ClockFeature
from .stock_feature import StockFeature
from .youtube_feature import YouTubeFeature
from .weather_feature import WeatherFeature
from .animation_feature import AnimationFeature

# All available features in display order
ALL_FEATURES = [
    TextFeature,
    ImageFeature,
    ClockFeature,
    StockFeature,
    YouTubeFeature,
    WeatherFeature,
    AnimationFeature,
]

__all__ = [
    'FeatureBase',
    'ImageFeature',
    'TextFeature',
    'ClockFeature',
    'StockFeature',
    'YouTubeFeature',
    'WeatherFeature',
    'AnimationFeature',
    'ALL_FEATURES',
]
