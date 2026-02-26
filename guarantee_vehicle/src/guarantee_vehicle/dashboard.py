from __future__ import annotations

import argparse
import numpy as np
import pandas as pd
import streamlit as st

from guarantee_vehicle.capital.returns import returns_for_leverage
from guarantee_vehicle.config import load_config


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Guarantee Vehicle investor returns dashboard")
    parser.add_argument("--config", default="examples/config_example.yaml", help="Path to YAML config")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    cfg = load_config(args.config)

    st.set_page_config(page_title="Guarantee Vehicle Dashboard", layout="wide")
    st.title("Guarantee Vehicle Investor Returns Dashboard")
    st.caption("Interactive ROE view by investor type with leverage as direct input.")

    with st.sidebar:
        st.header("Inputs")
        leverage = st.slider("Leverage (Notional / Equity)", min_value=2.0, max_value=40.0, value=15.0, step=0.5)
        pd_annual = st.slider("Annual PD", min_value=0.005, max_value=0.15, value=0.04, step=0.005)
        mean_mtm_pos = st.slider("E[MTM+] at default (% of notional)", min_value=0.001, max_value=0.20, value=0.03, step=0.001)

        expected_loss_rate = pd_annual * mean_mtm_pos
        st.metric("Expected loss (bps)", f"{expected_loss_rate * 10000:,.1f}")

    point = returns_for_leverage(cfg, leverage=leverage, expected_loss_rate=expected_loss_rate)

    col1, col2, col3 = st.columns(3)
    col1.metric("Equity ROE", f"{point['equity_roe']:.2%}")
    col2.metric("Mezz Return", f"{point['mezz_return']:.2%}")
    col3.metric("Guarantor ROE", f"{point['guarantor_roe']:.2%}")

    st.subheader("Capital mix at selected leverage")
    mix_df = pd.DataFrame(
        {
            "investor": ["Equity", "Mezz", "Counter-guarantee"],
            "capital_pct_notional": [point["equity_pct"], point["mezz_pct"], point["counter_guarantee_pct"]],
        }
    )
    st.dataframe(mix_df, use_container_width=True)

    st.subheader("ROE / Returns sensitivity vs leverage")
    lev_grid = np.arange(3.0, 35.5, 0.5)
    rows = []
    for lev in lev_grid:
        try:
            out = returns_for_leverage(cfg, leverage=float(lev), expected_loss_rate=expected_loss_rate)
        except ValueError:
            continue
        rows.append(
            {
                "leverage": lev,
                "equity_roe": out["equity_roe"],
                "mezz_return": out["mezz_return"],
                "guarantor_roe": out["guarantor_roe"],
            }
        )

    curve = pd.DataFrame(rows)
    st.line_chart(curve.set_index("leverage"), use_container_width=True)

    st.subheader("Ideas implemented")
    st.markdown(
        "- Direct leverage control.\n"
        "- Per-investor return view (equity/mezz/guarantor).\n"
        "- Sensitivity curve across leverage for instant trade-off analysis."
    )


if __name__ == "__main__":
    main()
