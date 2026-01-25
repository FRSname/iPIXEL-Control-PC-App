"""
Weather data fetching service.

Provides functionality to fetch weather data using the OpenWeatherMap API.
"""

from typing import Dict, Any, Optional
import tkinter as tk

from .api_fetcher import APIFetcher, CachingAPIFetcher


class WeatherService(CachingAPIFetcher):
    """
    Service for fetching weather data.

    Uses OpenWeatherMap API. Requires a free API key.

    Usage:
        def on_data(data):
            print(f"Temperature: {data['temperature']}°C")

        service = WeatherService(root, on_data, on_error, api_key="YOUR_KEY")
        service.fetch(location="London", units="metric")
    """

    API_BASE_URL = "https://api.openweathermap.org/data/2.5/weather"

    def __init__(
        self,
        root: tk.Tk,
        on_success,
        on_error,
        on_start=None,
        api_key: str = "",
        cache_ttl_seconds: int = 600  # 10 minutes default
    ):
        super().__init__(root, on_success, on_error, on_start, cache_ttl_seconds)
        self._api_key = api_key

    def set_api_key(self, key: str) -> None:
        """Set the OpenWeatherMap API key."""
        self._api_key = key
        self.clear_cache()

    def _fetch_data_impl(self) -> Dict[str, Any]:
        """Fetch weather data from OpenWeatherMap."""
        if not self._api_key:
            raise ValueError(
                "OpenWeatherMap API key is required. "
                "Get a free key from openweathermap.org"
            )

        location = self._params.get('location', '')
        if not location:
            raise ValueError("Location is required")

        units = self._params.get('units', 'metric')  # metric or imperial

        try:
            import requests
        except ImportError:
            raise ImportError("requests library not installed. Run: pip install requests")

        params = {
            'q': location,
            'appid': self._api_key,
            'units': units
        }

        response = requests.get(self.API_BASE_URL, params=params, timeout=10)

        if response.status_code == 401:
            raise ValueError("Invalid API key")
        elif response.status_code == 404:
            raise ValueError(f"Location not found: {location}")
        elif response.status_code != 200:
            raise ValueError(f"API error: {response.status_code}")

        data = response.json()

        # Extract weather data
        main = data.get('main', {})
        weather = data.get('weather', [{}])[0]
        wind = data.get('wind', {})

        temp_unit = "°C" if units == "metric" else "°F"

        return {
            'location': data.get('name', location),
            'country': data.get('sys', {}).get('country', ''),
            'temperature': round(main.get('temp', 0)),
            'feels_like': round(main.get('feels_like', 0)),
            'temp_min': round(main.get('temp_min', 0)),
            'temp_max': round(main.get('temp_max', 0)),
            'humidity': main.get('humidity', 0),
            'pressure': main.get('pressure', 0),
            'condition': weather.get('main', 'Unknown'),
            'description': weather.get('description', ''),
            'icon': weather.get('icon', ''),
            'wind_speed': wind.get('speed', 0),
            'wind_direction': wind.get('deg', 0),
            'visibility': data.get('visibility', 0),
            'units': units,
            'temp_unit': temp_unit,
        }


def format_weather_display(
    data: Dict[str, Any],
    format_type: str = 'temp_condition',
    max_chars: int = 16
) -> str:
    """
    Format weather data for LED display.

    Args:
        data: Weather data dictionary from WeatherService
        format_type: Display format:
            - 'temp_only': Just temperature
            - 'temp_condition': Temperature and condition
            - 'city_temp': City name and temperature
            - 'full': City, temp, and condition
        max_chars: Maximum characters for display

    Returns:
        Formatted string for display
    """
    temp = data.get('temperature', 0)
    temp_unit = data.get('temp_unit', '°C')
    condition = data.get('condition', '')
    city = data.get('location', '')

    temp_str = f"{temp}{temp_unit}"

    if format_type == 'temp_only':
        return temp_str

    elif format_type == 'temp_condition':
        result = f"{temp_str} {condition}"
        return result[:max_chars]

    elif format_type == 'city_temp':
        # Truncate city if needed
        max_city = max_chars - len(temp_str) - 1
        if len(city) > max_city:
            city = city[:max_city-2] + ".."
        result = f"{city} {temp_str}"
        return result[:max_chars]

    elif format_type == 'full':
        result = f"{city} {temp_str} {condition}"
        return result[:max_chars]

    return temp_str


def get_weather_icon_name(icon_code: str) -> str:
    """
    Map OpenWeatherMap icon code to a descriptive name.

    Args:
        icon_code: Icon code from API (e.g., "01d", "10n")

    Returns:
        Descriptive name like "clear_day" or "rain_night"
    """
    icon_map = {
        '01d': 'clear_day',
        '01n': 'clear_night',
        '02d': 'few_clouds_day',
        '02n': 'few_clouds_night',
        '03d': 'scattered_clouds',
        '03n': 'scattered_clouds',
        '04d': 'broken_clouds',
        '04n': 'broken_clouds',
        '09d': 'shower_rain',
        '09n': 'shower_rain',
        '10d': 'rain_day',
        '10n': 'rain_night',
        '11d': 'thunderstorm',
        '11n': 'thunderstorm',
        '13d': 'snow',
        '13n': 'snow',
        '50d': 'mist',
        '50n': 'mist',
    }
    return icon_map.get(icon_code, 'unknown')
