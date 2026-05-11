from dataclasses import dataclass, field
from typing import Literal
import pandas as pd
import numpy as np

from dashboard.indicators.core import ema, rsi, macd, bollinger_bands, volume_analysis

Direction = Literal["LONG", "SHORT"]
SignalLabel = Literal["STRONG BUY", "BUY", "NEUTRAL", "SELL", "STRONG SELL"]

SCORE_THRESHOLDS = {
    "STRONG BUY": 60,
    "BUY": 25,
    "NEUTRAL": -25,
    "SELL": -60,
}


@dataclass
class SignalResult:
    score: float
    label: SignalLabel
    direction: Direction
    components: dict = field(default_factory=dict)
    timestamp: object = None
    confluence: bool = False


def _ema_score(e9: float, e21: float, e50: float, e200: float) -> float:
    """Bull/bear stack scoring based on EMA alignment."""
    score = 0.0
    if e9 > e21:
        score += 0.5
    else:
        score -= 0.5
    if e21 > e50:
        score += 0.35
    else:
        score -= 0.35
    if e50 > e200:
        score += 0.15
    else:
        score -= 0.15
    return max(-1.0, min(1.0, score))


def _rsi_score(rsi_val: float) -> float:
    if rsi_val <= 30:
        return 1.0
    elif rsi_val <= 45:
        return 1.0 - (rsi_val - 30) / 15 * 0.7
    elif rsi_val <= 55:
        return 0.0
    elif rsi_val <= 70:
        return -(rsi_val - 55) / 15 * 0.7
    else:
        return -1.0


def _macd_score(hist: float, prev_hist: float, macd_line: float, signal_line: float) -> float:
    # Zero-line crossover: strongest signal
    if prev_hist < 0 and hist >= 0:
        return 1.0
    if prev_hist > 0 and hist <= 0:
        return -1.0
    # Histogram growing/shrinking
    if hist > 0:
        return 0.5 if hist > prev_hist else -0.3
    else:
        return -0.5 if hist < prev_hist else 0.3


def _bb_score(pct_b: float, bandwidth: float) -> float:
    if pd.isna(pct_b):
        return 0.0
    if pct_b <= 0.05:
        raw = 1.0
    elif pct_b <= 0.2:
        raw = 1.0 - (pct_b - 0.05) / 0.15 * 0.5
    elif pct_b <= 0.8:
        raw = 0.0
    elif pct_b <= 0.95:
        raw = -(pct_b - 0.8) / 0.15 * 0.5
    else:
        raw = -1.0
    # Reduce confidence during squeeze
    if not pd.isna(bandwidth) and bandwidth < 0.02:
        raw *= 0.5
    return raw


def _volume_score(vol_ratio: float, current_close: float, close_5_ago: float) -> float:
    if pd.isna(vol_ratio):
        return 0.0
    price_rising = current_close > close_5_ago
    if vol_ratio > 1.5:
        return 1.0 if price_rising else -1.0
    return 0.0


def compute_signal(df: pd.DataFrame, direction: Direction = "LONG") -> SignalResult:
    if len(df) < 50:
        return SignalResult(score=0.0, label="NEUTRAL", direction=direction)

    close = df["Close"]

    e9 = ema(close, 9)
    e21 = ema(close, 21)
    e50 = ema(close, 50)
    e200 = ema(close, min(200, len(close) - 1))

    rsi14 = rsi(close, 14)
    macd_df = macd(close)
    bb_df = bollinger_bands(close)
    vol_df = volume_analysis(df)

    last_rsi = float(rsi14.iloc[-1]) if not pd.isna(rsi14.iloc[-1]) else 50.0
    last_hist = float(macd_df["histogram"].iloc[-1])
    prev_hist = float(macd_df["histogram"].iloc[-2]) if len(macd_df) >= 2 else 0.0
    last_macd = float(macd_df["macd_line"].iloc[-1])
    last_signal_line = float(macd_df["signal_line"].iloc[-1])
    last_pct_b = float(bb_df["pct_b"].iloc[-1])
    last_bw = float(bb_df["bandwidth"].iloc[-1])
    last_vol_ratio = float(vol_df["vol_ratio"].iloc[-1]) if not pd.isna(vol_df["vol_ratio"].iloc[-1]) else 1.0
    close_5_ago = float(close.iloc[-6]) if len(close) >= 6 else float(close.iloc[0])

    ema_s = _ema_score(
        float(e9.iloc[-1]), float(e21.iloc[-1]),
        float(e50.iloc[-1]), float(e200.iloc[-1])
    )
    rsi_s = _rsi_score(last_rsi)
    macd_s = _macd_score(last_hist, prev_hist, last_macd, last_signal_line)
    bb_s = _bb_score(last_pct_b, last_bw)
    vol_s = _volume_score(last_vol_ratio, float(close.iloc[-1]), close_5_ago)

    # Low volume dampens all signals
    vol_dampener = 0.7 if last_vol_ratio < 0.8 else 1.0

    raw_score = (
        ema_s * 0.25
        + rsi_s * 0.20
        + macd_s * 0.25
        + bb_s * 0.15
        + vol_s * 0.15
    ) * vol_dampener

    final_score = raw_score * 100

    # Invert for SHORT direction: bearish = buy signal
    if direction == "SHORT":
        final_score = -final_score

    label = _score_to_label(final_score)

    components = {
        "EMA Crossover": round(ema_s, 3),
        "RSI": round(rsi_s, 3),
        "MACD": round(macd_s, 3),
        "Bollinger Bands": round(bb_s, 3),
        "Volume": round(vol_s, 3),
    }

    return SignalResult(
        score=round(final_score, 1),
        label=label,
        direction=direction,
        components=components,
        timestamp=df.index[-1],
    )


def _score_to_label(score: float) -> SignalLabel:
    if score >= SCORE_THRESHOLDS["STRONG BUY"]:
        return "STRONG BUY"
    elif score >= SCORE_THRESHOLDS["BUY"]:
        return "BUY"
    elif score >= SCORE_THRESHOLDS["NEUTRAL"]:
        return "NEUTRAL"
    elif score >= SCORE_THRESHOLDS["SELL"]:
        return "SELL"
    else:
        return "STRONG SELL"


def compute_mtf_signals(
    dax_data: dict[str, pd.DataFrame], direction: Direction = "LONG"
) -> dict[str, SignalResult]:
    results = {}
    for tf, df in dax_data.items():
        if df is not None and not df.empty:
            results[tf] = compute_signal(df, direction)
    return results


def check_confluence(mtf_results: dict[str, SignalResult]) -> bool:
    buy_labels = {"STRONG BUY", "BUY"}
    sell_labels = {"STRONG SELL", "SELL"}
    labels = [r.label for r in mtf_results.values()]
    buy_count = sum(1 for l in labels if l in buy_labels)
    sell_count = sum(1 for l in labels if l in sell_labels)
    return buy_count >= 3 or sell_count >= 3
