from dataclasses import dataclass, field
from typing import Literal
import pandas as pd

TurboType = Literal["LONG", "SHORT"]

DAX_MOVES = [-0.15, -0.10, -0.05, -0.02, -0.01, 0.0, 0.01, 0.02, 0.05, 0.10, 0.15]


@dataclass
class TurboParams:
    dax_current: float
    financing_level: float
    knockout_level: float
    investment_eur: float
    turbo_type: TurboType
    ratio: float = 0.01


@dataclass
class TurboResult:
    intrinsic_value: float
    leverage: float
    num_certificates: float
    distance_to_knockout_pts: float
    distance_to_knockout_pct: float
    pnl_table: pd.DataFrame
    max_loss: float
    risk_label: str
    position_size: dict = field(default_factory=dict)


def _intrinsic_value(params: TurboParams) -> float:
    if params.turbo_type == "LONG":
        return (params.dax_current - params.financing_level) * params.ratio
    else:
        return (params.financing_level - params.dax_current) * params.ratio


def _leverage(params: TurboParams) -> float:
    diff = abs(params.dax_current - params.financing_level)
    if diff == 0:
        return 0.0
    return params.dax_current / diff


def _distance_to_ko(params: TurboParams) -> tuple[float, float]:
    pts = abs(params.dax_current - params.knockout_level)
    pct = pts / params.dax_current * 100
    return pts, pct


def _risk_label(distance_pct: float) -> str:
    if distance_pct < 2:
        return "EXTREME"
    elif distance_pct < 5:
        return "HIGH"
    elif distance_pct < 10:
        return "MODERATE"
    else:
        return "LOW"


def build_pnl_table(params: TurboParams, entry_value: float) -> pd.DataFrame:
    rows = []
    for move in DAX_MOVES:
        new_dax = params.dax_current * (1 + move)
        if params.turbo_type == "LONG":
            new_value = (new_dax - params.financing_level) * params.ratio
            knocked_out = new_dax <= params.knockout_level
        else:
            new_value = (params.financing_level - new_dax) * params.ratio
            knocked_out = new_dax >= params.knockout_level

        if knocked_out or new_value <= 0:
            new_value = 0.0
            knocked_out = True

        n_certs = params.investment_eur / entry_value if entry_value > 0 else 0
        pnl_eur = (new_value - entry_value) * n_certs
        pnl_pct = (new_value / entry_value - 1) * 100 if entry_value > 0 else 0.0

        rows.append(
            {
                "DAX move": f"{move*100:+.0f}%",
                "DAX price": round(new_dax, 0),
                "Turbo waarde (€)": round(new_value, 4),
                "P&L (€)": round(pnl_eur, 2),
                "P&L (%)": round(pnl_pct, 1),
                "Knock-out": "❌ JA" if knocked_out else "✓",
            }
        )
    return pd.DataFrame(rows)


def suggest_position_size(
    account_size: float, risk_pct: float, params: TurboParams, entry_value: float
) -> dict:
    if entry_value <= 0:
        return {}
    max_risk_eur = account_size * risk_pct
    # Full loss = entry_value per certificate (worst case: knock-out)
    n_certs = max_risk_eur / entry_value
    total_investment = n_certs * entry_value
    pct_of_account = total_investment / account_size * 100
    return {
        "certificates": round(n_certs, 1),
        "total_investment_eur": round(total_investment, 2),
        "pct_of_account": round(pct_of_account, 1),
        "max_loss_eur": round(max_risk_eur, 2),
    }


def calculate_turbo(
    params: TurboParams, account_size: float = 10_000, risk_pct: float = 0.02
) -> TurboResult:
    iv = _intrinsic_value(params)
    lev = _leverage(params)
    ko_pts, ko_pct = _distance_to_ko(params)
    risk = _risk_label(ko_pct)

    n_certs = params.investment_eur / iv if iv > 0 else 0
    pnl_table = build_pnl_table(params, iv)
    pos_size = suggest_position_size(account_size, risk_pct, params, iv)

    return TurboResult(
        intrinsic_value=round(iv, 4),
        leverage=round(lev, 1),
        num_certificates=round(n_certs, 2),
        distance_to_knockout_pts=round(ko_pts, 1),
        distance_to_knockout_pct=round(ko_pct, 2),
        pnl_table=pnl_table,
        max_loss=params.investment_eur,
        risk_label=risk,
        position_size=pos_size,
    )
