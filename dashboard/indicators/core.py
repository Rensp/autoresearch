import pandas as pd
import numpy as np


def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def macd(
    series: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> pd.DataFrame:
    fast_ema = ema(series, fast)
    slow_ema = ema(series, slow)
    macd_line = fast_ema - slow_ema
    signal_line = ema(macd_line, signal)
    histogram = macd_line - signal_line
    return pd.DataFrame(
        {"macd_line": macd_line, "signal_line": signal_line, "histogram": histogram}
    )


def bollinger_bands(
    series: pd.Series, period: int = 20, std_dev: float = 2.0
) -> pd.DataFrame:
    middle = series.rolling(period).mean()
    std = series.rolling(period).std()
    upper = middle + std_dev * std
    lower = middle - std_dev * std
    bandwidth = (upper - lower) / middle.replace(0, np.nan)
    pct_b = (series - lower) / (upper - lower).replace(0, np.nan)
    return pd.DataFrame(
        {
            "upper": upper,
            "middle": middle,
            "lower": lower,
            "bandwidth": bandwidth,
            "pct_b": pct_b,
        }
    )


def volume_analysis(df: pd.DataFrame, period: int = 20) -> pd.DataFrame:
    vol = df["Volume"].astype(float)
    vol_ma = vol.rolling(period).mean()
    vol_ratio = vol / vol_ma.replace(0, np.nan)

    # On-Balance Volume
    direction = np.sign(df["Close"].diff()).fillna(0)
    obv = (vol * direction).cumsum()

    vol_signal = vol_ratio.apply(
        lambda r: "HIGH" if r > 1.5 else ("LOW" if r < 0.8 else "NORMAL")
        if pd.notna(r)
        else "NORMAL"
    )

    return pd.DataFrame(
        {"vol_ma": vol_ma, "vol_ratio": vol_ratio, "obv": obv, "vol_signal": vol_signal}
    )


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high = df["High"]
    low = df["Low"]
    prev_close = df["Close"].shift(1)
    tr = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1
    ).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False).mean()
