"""
Formatting utilities for numbers, prices, and text.

Provides consistent formatting across the application for displaying
stock prices, subscriber counts, and other numerical data.
"""

from typing import Union


def format_number(num: Union[int, float]) -> str:
    """
    Format a large number with K/M/B suffix.

    Used for YouTube subscriber counts and similar large numbers.

    Examples:
        format_number(1234) -> "1.2K"
        format_number(1500000) -> "1.5M"
        format_number(2000000000) -> "2.0B"
        format_number(999) -> "999"

    Args:
        num: Number to format

    Returns:
        Formatted string with appropriate suffix
    """
    num = float(num)

    if num >= 1_000_000_000:
        return f"{num / 1_000_000_000:.1f}B"
    elif num >= 1_000_000:
        return f"{num / 1_000_000:.1f}M"
    elif num >= 1_000:
        return f"{num / 1_000:.1f}K"
    else:
        return str(int(num))


def format_stock_price(
    price: float,
    currency: str = "$",
    max_chars: int = 8
) -> str:
    """
    Format a stock price for display on LED panel.

    Handles different price ranges appropriately:
    - Large prices (>= 10000): Use K notation
    - Normal prices: 2 decimal places
    - Small prices (< 1): Up to 4 decimal places

    Args:
        price: The price to format
        currency: Currency symbol (default: "$")
        max_chars: Maximum characters for the output (default: 8)

    Returns:
        Formatted price string
    """
    if price >= 10000:
        # Use K notation for large numbers
        formatted = f"{price / 1000:.1f}K"
    elif price >= 1000:
        # No decimals for large numbers
        formatted = f"{price:.0f}"
    elif price >= 100:
        # One decimal for mid-range
        formatted = f"{price:.1f}"
    elif price >= 1:
        # Two decimals for normal prices
        formatted = f"{price:.2f}"
    else:
        # More decimals for penny stocks / crypto
        formatted = f"{price:.4f}"

    result = f"{currency}{formatted}"

    # Truncate if too long
    if len(result) > max_chars:
        result = result[:max_chars]

    return result


def format_change(change: float, change_percent: float) -> str:
    """
    Format a stock price change with percentage.

    Examples:
        format_change(2.50, 1.5) -> "+$2.50 (+1.50%)"
        format_change(-1.25, -0.8) -> "-$1.25 (-0.80%)"

    Args:
        change: Absolute price change
        change_percent: Percentage change

    Returns:
        Formatted change string with sign and percentage
    """
    sign = "+" if change >= 0 else ""
    return f"{sign}${abs(change):.2f} ({sign}{change_percent:.2f}%)"


def format_temperature(
    temp: float,
    unit: str = "C",
    include_symbol: bool = True
) -> str:
    """
    Format a temperature value.

    Args:
        temp: Temperature value
        unit: "C" for Celsius, "F" for Fahrenheit
        include_symbol: Whether to include the degree symbol

    Returns:
        Formatted temperature string
    """
    temp_int = round(temp)
    if include_symbol:
        return f"{temp_int}°{unit}"
    else:
        return f"{temp_int}{unit}"


def format_time_remaining(seconds: int) -> str:
    """
    Format seconds as a countdown string.

    Args:
        seconds: Number of seconds remaining

    Returns:
        Formatted string like "2d 5h 30m" or "5:30" for under an hour
    """
    if seconds < 0:
        return "0:00"

    days = seconds // 86400
    hours = (seconds % 86400) // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60

    if days > 0:
        return f"{days}d {hours}h {minutes}m"
    elif hours > 0:
        return f"{hours}h {minutes}m {secs}s"
    else:
        return f"{minutes}:{secs:02d}"


def truncate_text(text: str, max_length: int, suffix: str = "...") -> str:
    """
    Truncate text to a maximum length with suffix.

    Args:
        text: Text to truncate
        max_length: Maximum length including suffix
        suffix: Suffix to add when truncating (default: "...")

    Returns:
        Truncated text or original if short enough
    """
    if len(text) <= max_length:
        return text

    truncate_at = max_length - len(suffix)
    if truncate_at <= 0:
        return suffix[:max_length]

    return text[:truncate_at] + suffix


def hex_to_rgb(hex_color: str) -> tuple:
    """
    Convert a hex color string to RGB tuple.

    Args:
        hex_color: Color string like "#FFFFFF" or "FFFFFF"

    Returns:
        Tuple of (red, green, blue) values 0-255
    """
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def rgb_to_hex(r: int, g: int, b: int) -> str:
    """
    Convert RGB values to hex color string.

    Args:
        r: Red value (0-255)
        g: Green value (0-255)
        b: Blue value (0-255)

    Returns:
        Hex color string like "#FFFFFF"
    """
    return f"#{r:02x}{g:02x}{b:02x}"
