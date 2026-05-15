"""
Stock data fetching service.

Provides functionality to fetch stock prices and format them for display.
Uses yfinance library for data retrieval.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, Any, Optional

from .api_fetcher import APIFetcher, CachingAPIFetcher

if TYPE_CHECKING:  # pragma: no cover
    import tkinter as tk


class StockService(CachingAPIFetcher):
    """
    Service for fetching stock market data.

    Uses yfinance library to retrieve real-time stock prices.
    No API key required.

    Usage:
        def on_data(data):
            print(f"Price: {data['price']}")

        def on_error(msg):
            print(f"Error: {msg}")

        service = StockService(root, on_data, on_error)
        service.fetch(ticker="AAPL")
    """

    def __init__(
        self,
        root: tk.Tk,
        on_success,
        on_error,
        on_start=None,
        cache_ttl_seconds: int = 30
    ):
        super().__init__(root, on_success, on_error, on_start, cache_ttl_seconds)

    def _fetch_data_impl(self) -> Dict[str, Any]:
        """Fetch stock data from yfinance."""
        try:
            import yfinance as yf
        except ImportError:
            raise ImportError("yfinance library not installed. Run: pip install yfinance")

        ticker = self._params.get('ticker', 'AAPL')
        if not ticker:
            raise ValueError("Ticker symbol is required")

        stock = yf.Ticker(ticker)
        info = stock.info

        if not info:
            raise ValueError(f"No data found for ticker: {ticker}")

        # Get current price (try multiple field names)
        current_price = (
            info.get('currentPrice') or
            info.get('regularMarketPrice') or
            info.get('price')
        )

        if current_price is None:
            raise ValueError(f"Could not get price for {ticker}")

        # Get previous close for change calculation
        previous_close = (
            info.get('previousClose') or
            info.get('regularMarketPreviousClose')
        )

        # Calculate change
        change = 0.0
        change_percent = 0.0
        if previous_close and previous_close > 0:
            change = current_price - previous_close
            change_percent = (change / previous_close) * 100

        return {
            'ticker': ticker.upper(),
            'name': info.get('shortName', ticker),
            'price': float(current_price),
            'change': float(change),
            'change_percent': float(change_percent),
            'previous_close': float(previous_close) if previous_close else None,
            'currency': info.get('currency', 'USD'),
            'market_cap': info.get('marketCap'),
            'volume': info.get('volume'),
            'is_crypto': 'USD' in ticker.upper() or 'BTC' in ticker.upper(),
        }


def format_stock_display(
    data: Dict[str, Any],
    format_type: str = 'price_change',
    max_chars: int = 16
) -> str:
    """
    Format stock data for LED display.

    Args:
        data: Stock data dictionary from StockService
        format_type: Display format:
            - 'price_only': Just the price
            - 'price_change': Price with change indicator
            - 'ticker_price': Ticker symbol and price
            - 'full': Ticker, price, and change percent
        max_chars: Maximum characters for display

    Returns:
        Formatted string for display
    """
    ticker = data.get('ticker', 'N/A')
    price = data.get('price', 0)
    change = data.get('change', 0)
    change_percent = data.get('change_percent', 0)

    # Format price appropriately
    if price >= 10000:
        price_str = f"{price/1000:.1f}K"
    elif price >= 100:
        price_str = f"{price:.0f}"
    elif price >= 1:
        price_str = f"{price:.2f}"
    else:
        price_str = f"{price:.4f}"

    # Add currency symbol
    currency = data.get('currency', 'USD')
    if currency == 'USD':
        price_str = f"${price_str}"
    elif currency == 'EUR':
        price_str = f"€{price_str}"
    elif currency == 'GBP':
        price_str = f"£{price_str}"

    # Format based on type
    if format_type == 'price_only':
        return price_str

    elif format_type == 'ticker_price':
        result = f"{ticker} {price_str}"
        return result[:max_chars]

    elif format_type == 'price_change':
        sign = '+' if change >= 0 else ''
        result = f"{price_str} {sign}{change_percent:.1f}%"
        return result[:max_chars]

    elif format_type == 'full':
        sign = '+' if change >= 0 else ''
        result = f"{ticker} {price_str} {sign}{change_percent:.1f}%"
        return result[:max_chars]

    return price_str


def get_stock_color(data: Dict[str, Any]) -> str:
    """
    Get color based on stock price movement.

    Args:
        data: Stock data dictionary

    Returns:
        Hex color string (green for up, red for down)
    """
    change = data.get('change', 0)
    if change > 0:
        return "#00FF00"  # Green
    elif change < 0:
        return "#FF0000"  # Red
    else:
        return "#FFFFFF"  # White (no change)
