from __future__ import annotations

from io import BytesIO
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

from guarantee_vehicle.capital.aggregation import weighted_portfolio_samples
from guarantee_vehicle.capital.returns import returns_for_leverage
from guarantee_vehicle.config import AppConfig, load_config
from guarantee_vehicle.io import load_data, validate_loaded_data
from guarantee_vehicle.market.fx import phase0_mtm_positive, summarize_mtm_distribution


DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[2] / "examples" / "config_example.yaml"


def _load_default_config() -> AppConfig:
    return load_config(DEFAULT_CONFIG_PATH)


def _to_upload_template(cfg: AppConfig, fx: pd.DataFrame, rates: dict[str, pd.Series]) -> bytes:
    date_row = cfg.data.excel.dates_row_index
    code_col = cfg.data.excel.fx_row_key_column
    start_row = cfg.data.excel.values_start_row_index
    start_col = cfg.data.excel.values_start_col_index

    n_rows = max(start_row + len(cfg.universe.currencies) + 3, date_row + 2)
    n_cols = max(start_col + max(len(fx.index), 12), code_col + 1)
    fx_sheet = pd.DataFrame("", index=range(n_rows), columns=range(n_cols))

    if not fx.empty:
        fx_sheet.iloc[date_row, start_col : start_col + len(fx.index)] = [d.date().isoformat() for d in fx.index]

    for i, ccy in enumerate(cfg.universe.currencies):
        row = start_row + i
        fx_sheet.iloc[row, code_col] = ccy
        if ccy in fx.columns:
            vals = fx[ccy].reindex(fx.index).tolist()
            fx_sheet.iloc[row, start_col : start_col + len(vals)] = vals

    rates_rows = []
    for ccy, key in cfg.data.rates.mapping.items():
        series = rates.get(ccy, pd.Series(dtype=float))
        row = [key] + series.tolist()
        rates_rows.append(row)

    rates_sheet = pd.DataFrame(rates_rows)

    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        fx_sheet.to_excel(writer, index=False, header=False, sheet_name=cfg.data.excel.fx_sheet)
        rates_sheet.to_excel(writer, index=False, header=False, sheet_name=cfg.data.rates.sheet)
    return buf.getvalue()


def _phase0_stats(cfg: AppConfig, fx_df: pd.DataFrame) -> tuple[pd.DataFrame, np.ndarray]:
    samples_by_ccy: dict[str, np.ndarray] = {}
    rows: list[dict[str, float | str]] = []

    for ccy in cfg.universe.currencies:
        if ccy not in fx_df.columns:
            continue
        samples = phase0_mtm_positive(fx_df[ccy], tenor_months=cfg.portfolio.tenor_years * 12)
        samples_by_ccy[ccy] = samples
        rows.append({"currency": ccy, **summarize_mtm_distribution(samples)})

    weights = {c: 1 / len(cfg.universe.currencies) for c in cfg.universe.currencies}
    portfolio_samples = weighted_portfolio_samples(samples_by_ccy, weights)
    return pd.DataFrame(rows), portfolio_samples


def main() -> None:
    st.set_page_config(page_title="Guarantee Vehicle Dashboard", layout="wide")
    st.title("Guarantee Vehicle Standalone Dashboard")
    st.caption("Upload Excel, inspect FX stats, and compute investor returns with leverage input.")

    cfg = _load_default_config()

    st.sidebar.header("Workbook mapping")
    cfg.data.excel.fx_sheet = st.sidebar.text_input("FX sheet", value=cfg.data.excel.fx_sheet)
    cfg.data.rates.sheet = st.sidebar.text_input("Rates sheet", value=cfg.data.rates.sheet)
    cfg.data.excel.fx_row_key_column = st.sidebar.number_input("FX row key column (0-based)", value=cfg.data.excel.fx_row_key_column, step=1)
    cfg.data.excel.dates_row_index = st.sidebar.number_input("FX dates row index (0-based)", value=cfg.data.excel.dates_row_index, step=1)
    cfg.data.excel.values_start_row_index = st.sidebar.number_input("FX values start row (0-based)", value=cfg.data.excel.values_start_row_index, step=1)
    cfg.data.excel.values_start_col_index = st.sidebar.number_input("FX values start col (0-based)", value=cfg.data.excel.values_start_col_index, step=1)

    st.sidebar.markdown("### Rate mapping")
    mapping_df = pd.DataFrame(
        {"currency": list(cfg.data.rates.mapping.keys()), "row_key": list(cfg.data.rates.mapping.values())}
    )
    edited_map = st.sidebar.data_editor(mapping_df, num_rows="dynamic", use_container_width=True)
    cfg.data.rates.mapping = {
        str(r["currency"]).strip().upper(): str(r["row_key"]).strip()
        for _, r in edited_map.iterrows()
        if str(r.get("currency", "")).strip() and str(r.get("row_key", "")).strip()
    }

    uploaded = st.file_uploader("Upload FX & rates workbook (.xlsx)", type=["xlsx"])
    if uploaded is None:
        st.info("Upload an Excel workbook to start.")
        return

    excel_bytes = uploaded.getvalue()
    try:
        data = load_data(BytesIO(excel_bytes), cfg)
        checks = validate_loaded_data(data, cfg)
    except Exception as exc:
        st.error(f"Failed to parse workbook: {exc}")
        st.stop()

    st.success("Workbook loaded successfully")
    st.write("Validation checks:")
    for c in checks:
        st.write(f"- {c}")

    c1, c2 = st.columns([2, 1])
    with c1:
        st.subheader("FX history preview")
        st.dataframe(data.fx.tail(12), use_container_width=True)
    with c2:
        st.subheader("Rates loaded")
        rates_preview = pd.DataFrame(
            [{"currency": k, "points": len(v), "last": float(v.iloc[-1]) if len(v) else np.nan} for k, v in data.rates.items()]
        )
        st.dataframe(rates_preview, use_container_width=True)

    ccy_stats_df, portfolio_samples = _phase0_stats(cfg, data.fx)
    if ccy_stats_df.empty:
        st.warning("No FX series matched current mapping/universe.")
        st.stop()

    st.subheader("Phase 0 FX MTM+ statistics")
    st.dataframe(ccy_stats_df, use_container_width=True)

    st.subheader("Investor returns")
    col_a, col_b, col_c = st.columns(3)
    leverage = col_a.slider("Leverage (Notional / Equity)", min_value=2.0, max_value=40.0, value=15.0, step=0.5)
    pd_annual = col_b.select_slider("Annual PD", options=cfg.credit.pd_scenarios_annual, value=cfg.credit.pd_scenarios_annual[1])
    mean_mtm_pos = col_c.number_input(
        "Override E[MTM+] fraction (leave 0 to use FX-derived)", min_value=0.0, max_value=1.0, value=0.0, step=0.001
    )

    inferred_mtm = float(np.mean(portfolio_samples))
    mtm_used = mean_mtm_pos if mean_mtm_pos > 0 else inferred_mtm
    expected_loss_rate = pd_annual * mtm_used

    returns = returns_for_leverage(cfg, leverage=leverage, expected_loss_rate=expected_loss_rate)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Equity ROE", f"{returns['equity_roe']:.2%}")
    m2.metric("Mezz return", f"{returns['mezz_return']:.2%}")
    m3.metric("Guarantor ROE", f"{returns['guarantor_roe']:.2%}")
    m4.metric("Expected loss (bps)", f"{expected_loss_rate*10000:.1f}")

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
    st.line_chart(pd.DataFrame(rows).set_index("leverage"), use_container_width=True)

    st.subheader("Download editable template workbook")
    template_bytes = _to_upload_template(cfg, data.fx, data.rates)
    st.download_button(
        label="Download template Excel (prefilled with current data)",
        data=template_bytes,
        file_name="guarantee_vehicle_template.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


if __name__ == "__main__":
    main()
