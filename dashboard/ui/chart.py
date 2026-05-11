import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from dashboard.indicators.core import ema, macd, bollinger_bands, volume_analysis, rsi


def build_candlestick_chart(
    df: pd.DataFrame,
    timeframe: str = "1h",
    show_ema: bool = True,
    show_bb: bool = True,
) -> go.Figure:
    if df.empty:
        fig = go.Figure()
        fig.add_annotation(text="Geen data beschikbaar", showarrow=False, font=dict(size=20, color="white"))
        fig.update_layout(template="plotly_dark", height=600)
        return fig

    close = df["Close"]

    ema9_s = ema(close, 9)
    ema21_s = ema(close, 21)
    ema50_s = ema(close, 50)
    macd_df = macd(close)
    bb_df = bollinger_bands(close)
    vol_df = volume_analysis(df)
    rsi_s = rsi(close, 14)

    fig = make_subplots(
        rows=4,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.52, 0.18, 0.16, 0.14],
        subplot_titles=("", "MACD", "RSI", "Volume"),
    )

    # --- Candlesticks ---
    fig.add_trace(
        go.Candlestick(
            x=df.index,
            open=df["Open"],
            high=df["High"],
            low=df["Low"],
            close=df["Close"],
            name="DAX",
            increasing_line_color="#26a69a",
            decreasing_line_color="#ef5350",
            increasing_fillcolor="#26a69a",
            decreasing_fillcolor="#ef5350",
        ),
        row=1, col=1,
    )

    if show_ema:
        for s, color, name in [
            (ema9_s, "#f39c12", "EMA 9"),
            (ema21_s, "#3498db", "EMA 21"),
            (ema50_s, "#9b59b6", "EMA 50"),
        ]:
            fig.add_trace(
                go.Scatter(x=df.index, y=s, name=name, line=dict(color=color, width=1.2), opacity=0.85),
                row=1, col=1,
            )

    if show_bb:
        fig.add_trace(
            go.Scatter(
                x=df.index, y=bb_df["upper"],
                name="BB Upper", line=dict(color="#7f8c8d", width=1, dash="dot"),
                opacity=0.6,
            ),
            row=1, col=1,
        )
        fig.add_trace(
            go.Scatter(
                x=df.index, y=bb_df["lower"],
                name="BB Lower", line=dict(color="#7f8c8d", width=1, dash="dot"),
                fill="tonexty", fillcolor="rgba(127,140,141,0.07)",
                opacity=0.6,
            ),
            row=1, col=1,
        )

    # --- MACD ---
    colors = ["#26a69a" if v >= 0 else "#ef5350" for v in macd_df["histogram"]]
    fig.add_trace(
        go.Bar(x=df.index, y=macd_df["histogram"], name="MACD Hist",
               marker_color=colors, opacity=0.8),
        row=2, col=1,
    )
    fig.add_trace(
        go.Scatter(x=df.index, y=macd_df["macd_line"], name="MACD",
                   line=dict(color="#f39c12", width=1.2)),
        row=2, col=1,
    )
    fig.add_trace(
        go.Scatter(x=df.index, y=macd_df["signal_line"], name="Signal",
                   line=dict(color="#e74c3c", width=1.2)),
        row=2, col=1,
    )

    # --- RSI ---
    fig.add_trace(
        go.Scatter(x=df.index, y=rsi_s, name="RSI 14",
                   line=dict(color="#3498db", width=1.5)),
        row=3, col=1,
    )
    for level, color in [(70, "rgba(231,76,60,0.4)"), (30, "rgba(46,204,113,0.4)")]:
        fig.add_hline(y=level, line_dash="dash", line_color=color, row=3, col=1)
    fig.add_hrect(y0=30, y1=70, fillcolor="rgba(255,255,255,0.03)",
                  line_width=0, row=3, col=1)

    # --- Volume ---
    vol_colors = [
        "#26a69a" if df["Close"].iloc[i] >= df["Open"].iloc[i] else "#ef5350"
        for i in range(len(df))
    ]
    fig.add_trace(
        go.Bar(x=df.index, y=df["Volume"], name="Volume",
               marker_color=vol_colors, opacity=0.7),
        row=4, col=1,
    )
    fig.add_trace(
        go.Scatter(x=df.index, y=vol_df["vol_ma"], name="Vol MA",
                   line=dict(color="#f39c12", width=1.2)),
        row=4, col=1,
    )

    fig.update_layout(
        template="plotly_dark",
        height=680,
        margin=dict(l=10, r=10, t=30, b=10),
        xaxis_rangeslider_visible=False,
        legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="left", x=0,
                    font=dict(size=11)),
        paper_bgcolor="#0e1117",
        plot_bgcolor="#0e1117",
        font=dict(color="#fafafa"),
    )

    fig.update_yaxes(gridcolor="rgba(255,255,255,0.07)", showgrid=True)
    fig.update_xaxes(gridcolor="rgba(255,255,255,0.07)", showgrid=True)
    fig.update_yaxes(title_text="RSI", row=3, col=1, range=[0, 100])
    fig.update_xaxes(showticklabels=True, row=4, col=1)

    return fig
