import streamlit as st
import pandas as pd

from dashboard.calculator.turbo import TurboParams, calculate_turbo

_RISK_COLORS = {
    "EXTREME": "🔴",
    "HIGH": "🟠",
    "MODERATE": "🟡",
    "LOW": "🟢",
}


def render_calculator(current_dax: float | None) -> None:
    st.markdown("### 🧮 Turbo Calculator")

    # Sanity check: DAX is always between 5000 and 60000 in any realistic scenario
    _raw = float(current_dax) if current_dax else 0.0
    dax_default = _raw if 5000.0 < _raw < 60000.0 else 18000.0

    # Quick-fill for known turbos
    with st.expander("⚡ Snel invullen — jouw BNP Turbo Short", expanded=True):
        st.markdown(
            "**BNP | DE000BB3S888** — SHORT | STR 25827.2556 | SL 25568.9830 | Ratio 1:500"
        )
        if st.button("Vul mijn turbo in", type="secondary", width="stretch"):
            st.session_state["turbo_prefill"] = {
                "type": "SHORT",
                "financing": 25827.2556,
                "knockout": 25568.9830,
                "ratio_divisor": 500,
            }

    prefill = st.session_state.get("turbo_prefill", {})

    with st.form("turbo_form"):
        turbo_type = st.radio(
            "Turbo type", ["LONG", "SHORT"], horizontal=True,
            index=1 if prefill.get("type") == "SHORT" else 0,
            help="LONG = profiteer van stijgende DAX. SHORT = profiteer van dalende DAX."
        )

        col1, col2 = st.columns(2)
        with col1:
            financing = st.number_input(
                "Strike / Financieringsniveau (STR)",
                min_value=1000.0,
                max_value=float(dax_default * 2.0),
                value=float(prefill.get("financing", round(dax_default * 1.10, 0) if turbo_type == "SHORT" else round(dax_default * 0.90, 0))),
                step=0.0001,
                format="%.4f",
                help="Het 'STR' getal op het productblad van je turbo.",
            )
        with col2:
            knockout = st.number_input(
                "Stop Loss / Knock-out niveau (SL)",
                min_value=1000.0,
                max_value=float(dax_default * 2.0),
                value=float(prefill.get("knockout", round(dax_default * 1.08, 0) if turbo_type == "SHORT" else round(dax_default * 0.92, 0))),
                step=0.0001,
                format="%.4f",
                help="Het 'SL' getal op het productblad. Als DAX dit niveau bereikt vervalt de turbo.",
            )

        col3, col4 = st.columns(2)
        with col3:
            investment = st.number_input(
                "Inleg (€)", min_value=10.0, max_value=100_000.0,
                value=1000.0, step=100.0
            )
        with col4:
            # Ratio displayed as divisor (e.g. 500 means 1:500 = multiplier 0.002)
            _RATIO_OPTIONS = [100, 500, 1000, 10, 200]
            _default_ratio_idx = _RATIO_OPTIONS.index(prefill.get("ratio_divisor", 100)) if prefill.get("ratio_divisor") in _RATIO_OPTIONS else 0
            ratio_divisor = st.selectbox(
                "Ratio (zoals op productblad)",
                options=_RATIO_OPTIONS,
                index=_default_ratio_idx,
                format_func=lambda x: f"1:{x}  (= {1/x:.4f} per cert)",
                help="BNP Turbo Short met 'R 500' = kies 1:500. De meest gangbare voor mini-turbos.",
            )
            ratio = 1.0 / ratio_divisor

        st.markdown("**Positiegrootteberekening**")
        col5, col6 = st.columns(2)
        with col5:
            account_size = st.number_input(
                "Accountgrootte (€)", min_value=100.0, value=10_000.0, step=500.0
            )
        with col6:
            risk_pct = st.slider(
                "Max risico per trade", min_value=0.5, max_value=5.0,
                value=2.0, step=0.5, format="%.1f%%"
            )

        submitted = st.form_submit_button("Berekenen", type="primary", width="stretch")

    if submitted:
        _validate_and_show(
            turbo_type=turbo_type,
            dax_current=dax_default,
            financing_level=financing,
            knockout_level=knockout,
            investment_eur=investment,
            ratio=ratio,
            account_size=account_size,
            risk_pct=risk_pct / 100,
        )


def _validate_and_show(
    turbo_type, dax_current, financing_level, knockout_level,
    investment_eur, ratio, account_size, risk_pct
):
    # Validate knock-out vs financing level
    if turbo_type == "LONG":
        if financing_level >= dax_current:
            st.error("LONG turbo: Financieringsniveau moet LAGER zijn dan de huidige DAX koers.")
            return
        if knockout_level <= financing_level or knockout_level >= dax_current:
            st.error("LONG turbo: Knock-out moet TUSSEN het financieringsniveau en de DAX koers liggen.")
            return
    else:
        if financing_level <= dax_current:
            st.error("SHORT turbo: Financieringsniveau moet HOGER zijn dan de huidige DAX koers.")
            return
        if knockout_level >= financing_level or knockout_level <= dax_current:
            st.error("SHORT turbo: Knock-out moet TUSSEN de DAX koers en het financieringsniveau liggen.")
            return

    params = TurboParams(
        dax_current=dax_current,
        financing_level=financing_level,
        knockout_level=knockout_level,
        investment_eur=investment_eur,
        turbo_type=turbo_type,
        ratio=ratio,
    )

    result = calculate_turbo(params, account_size=account_size, risk_pct=risk_pct)

    risk_icon = _RISK_COLORS.get(result.risk_label, "⬜")

    # Key metrics
    c1, c2, c3 = st.columns(3)
    c1.metric("Hefboom", f"{result.leverage:.1f}x")
    c2.metric("Intrinsieke waarde", f"€ {result.intrinsic_value:.4f}")
    c3.metric("Aantal certificaten", f"{result.num_certificates:.1f}")

    c4, c5 = st.columns(2)
    c4.metric("Afstand tot KO", f"{result.distance_to_knockout_pts:.0f} pt ({result.distance_to_knockout_pct:.2f}%)")
    c5.metric("Max verlies", f"€ {result.max_loss:.2f}")

    # Risk warning
    if result.risk_label == "EXTREME":
        st.error(f"{risk_icon} **EXTREEM RISICO** — KO afstand < 2%. Overweeg een minder agressieve turbo!")
    elif result.risk_label == "HIGH":
        st.warning(f"{risk_icon} **HOOG RISICO** — KO afstand < 5%. Wees voorzichtig.")
    else:
        st.success(f"{risk_icon} Risico niveau: **{result.risk_label}**")

    # Position sizing
    if result.position_size:
        ps = result.position_size
        st.info(
            f"💼 **Aanbevolen positiegrootte** ({risk_pct*100:.1f}% risico van €{account_size:,.0f}): "
            f"**{ps['certificates']:.1f} certificaten** "
            f"= €{ps['total_investment_eur']:,.2f} ({ps['pct_of_account']:.1f}% van account) "
            f"| Max verlies: €{ps['max_loss_eur']:,.2f}"
        )

    # P&L table
    st.markdown("**P&L tabel bij DAX koersbewegingen**")
    df = result.pnl_table

    def style_row(row):
        if row["Knock-out"] == "❌ JA":
            return ["background-color: rgba(244,67,54,0.3)"] * len(row)
        elif float(row["P&L (%)"].replace("%", "")) > 0:
            return ["background-color: rgba(38,166,154,0.15)"] * len(row)
        elif float(row["P&L (%)"].replace("%", "")) < 0:
            return ["background-color: rgba(239,83,80,0.15)"] * len(row)
        return [""] * len(row)

    # Highlight the zero-move row
    zero_idx = df[df["DAX move"] == "+0%"].index
    st.dataframe(df, width="stretch", hide_index=True)
