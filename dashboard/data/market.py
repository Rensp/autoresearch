import pandas as pd
import yfinance as yf
from datetime import datetime, time
import pytz

DAX_TICKER = "^GDAXI"
EXCHANGE_TZ = pytz.timezone("Europe/Berlin")
MARKET_OPEN = time(9, 0)
MARKET_CLOSE = time(17, 30)

_INTERVAL_CONFIG = {
    "15m": {"period": "5d",  "interval": "15m"},
    "1h":  {"period": "60d", "interval": "1h"},
    "4h":  {"period": "60d", "interval": "1h"},  # resampled below
    "1d":  {"period": "2y",  "interval": "1d"},
}


def fetch_dax_ohlcv(timeframe: str = "1h") -> pd.DataFrame:
    cfg = _INTERVAL_CONFIG.get(timeframe, _INTERVAL_CONFIG["1h"])
    try:
        df = yf.download(
            DAX_TICKER,
            period=cfg["period"],
            interval=cfg["interval"],
            progress=False,
            auto_adjust=True,
        )
    except Exception:
        return pd.DataFrame()

    if df.empty:
        return df

    # Flatten multi-level columns yfinance sometimes returns
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df = df.dropna(subset=["Close"])

    # Filter to exchange hours for intraday data
    if timeframe in ("15m", "1h", "4h"):
        df.index = pd.DatetimeIndex(df.index).tz_convert(EXCHANGE_TZ)
        df = df[
            (df.index.time >= MARKET_OPEN) & (df.index.time <= MARKET_CLOSE)
        ]

    if timeframe == "4h":
        df = _resample_to_4h(df)

    df = df.sort_index()
    return df


def _resample_to_4h(df: pd.DataFrame) -> pd.DataFrame:
    resampled = df.resample("4h").agg(
        {
            "Open": "first",
            "High": "max",
            "Low": "min",
            "Close": "last",
            "Volume": "sum",
        }
    )
    return resampled.dropna(subset=["Close"])


def get_dax_day_stats() -> dict:
    try:
        ticker = yf.Ticker(DAX_TICKER)
        info = ticker.fast_info
        hist = ticker.history(period="2d", interval="1d", auto_adjust=True)
        if hist.empty:
            return {}

        prev_close = float(hist["Close"].iloc[-2]) if len(hist) >= 2 else None
        last_close = float(hist["Close"].iloc[-1])
        change = last_close - prev_close if prev_close else 0.0
        change_pct = (change / prev_close * 100) if prev_close else 0.0

        return {
            "price": last_close,
            "open": float(hist["Open"].iloc[-1]),
            "high": float(hist["High"].iloc[-1]),
            "low": float(hist["Low"].iloc[-1]),
            "prev_close": prev_close,
            "change": change,
            "change_pct": change_pct,
            "volume": int(hist["Volume"].iloc[-1]) if "Volume" in hist.columns else 0,
        }
    except Exception:
        return {}


def get_current_dax_price() -> tuple[float | None, str]:
    """
    Returns (price, source_label). Tries multiple sources in order of freshness.
    1. yfinance fast_info (often 1-2 min delay for indices)
    2. Stooq.com via pandas_datareader-style URL (often 0-5 min)
    3. yfinance 1-min history fallback
    """
    # Source 1: yfinance fast_info
    try:
        ticker = yf.Ticker(DAX_TICKER)
        price = ticker.fast_info.last_price
        if price and price > 0:
            return float(price), "Yahoo (fast)"
    except Exception:
        pass

    # Source 2: Stooq — free, low delay for ^DAX
    try:
        url = "https://stooq.com/q/d/l/?s=%5Edax&i=d"
        resp = requests.get(url, timeout=5, headers={"User-Agent": "Mozilla/5.0"})
        if resp.status_code == 200:
            lines = resp.text.strip().split("\n")
            if len(lines) >= 2:
                last = lines[-1].split(",")
                if len(last) >= 5:
                    return float(last[4]), "Stooq"
    except Exception:
        pass

    # Source 3: yfinance 1-min history
    try:
        ticker = yf.Ticker(DAX_TICKER)
        hist = ticker.history(period="1d", interval="1m", auto_adjust=True)
        if not hist.empty:
            return float(hist["Close"].iloc[-1]), "Yahoo (1m)"
    except Exception:
        pass

    return None, "onbekend"
