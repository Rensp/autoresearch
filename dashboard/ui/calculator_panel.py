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

    dax_default = float(current_dax) if current_dax else 18000.0

    with st.form("turbo_form"):
        turbo_type = st.radio(
            "Turbo type", ["LONG", "SHORT"], horizontal=True,
            help="LONG = profiteer van stijgende DAX. SHORT = profiteer van dalende DAX."
        )

        col1, col2 = st.columns(2)
        with col1:
            financing = st.number_input(
                "Financieringsniveau (€)",
                min_value=1000.0,
                max_value=float(dax_default * 1.5),
                value=round(dax_default * 0.90, 0) if turbo_type == "LONG" else round(dax_default * 1.10, 0),
                step=50.0,
                help="Strike/financieringsniveau van de turbo (opgegeven door uitgever).",
            )
        with col2:
            knockout = st.number_input(
                "Knock-out niveau (€)",
                min_value=1000.0,
                max_value=float(dax_default * 1.5),
                value=round(dax_default * 0.92, 0) if turbo_type == "LONG" else round(dax_default * 1.08, 0),
                step=50.0,
                help="Als de DAX dit niveau raakt, vervalt de turbo waardeloos.",
            )

        col3, col4 = st.columns(2)
        with col3:
            investment = st.number_input(
                "Inleg (€)", min_value=10.0, max_value=100_000.0,
                value=1000.0, step=100.0
            )
        with col4:
            ratio = st.selectbox(
                "Ratio (turbo per DAX punt)",
                options=[0.01, 0.001, 0.1],
                index=0,
                help="0.01 = meest gangbaar (bijv. BNP Paribas, SocGen). 0.001 = mini turbos.",
                format_func=lambda x: f"{x} ({1/x:.0f}:1)",
            )

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

        submitted = st.form_submit_button("Berekenen", type="primary", use_container_width=True)

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
    st.dataframe(df, use_container_width=True, hide_index=True)
