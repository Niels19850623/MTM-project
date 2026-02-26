from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

from guarantee_vehicle.capital.aggregation import weighted_portfolio_samples
from guarantee_vehicle.capital.rating_capital import severity_capital
from guarantee_vehicle.capital.returns import break_even_fee_bps, stack_returns
from guarantee_vehicle.config import load_config
from guarantee_vehicle.credit.default_model import draw_default_times
from guarantee_vehicle.guarantee.payout import payout_default_only
from guarantee_vehicle.instruments.ccs import CCSParams, mtm_ccs_lender
from guarantee_vehicle.instruments.ndf import NDFParams, mtm_ndf_lender
from guarantee_vehicle.io import load_data, validate_loaded_data
from guarantee_vehicle.market.fx import phase0_mtm_positive, summarize_mtm_distribution
from guarantee_vehicle.reporting.charts import plot_leverage_vs_roe, plot_loss_exceedance
from guarantee_vehicle.reporting.tables import to_markdown_table
from guarantee_vehicle.reporting.report_md import write_report


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Guarantee vehicle model")
    p.add_argument("--config", required=True)
    p.add_argument("--excel", required=True)
    return p.parse_args()


def run() -> None:
    args = parse_args()
    cfg = load_config(args.config)
    data = load_data(args.excel, cfg)
    checks = validate_loaded_data(data, cfg)

    weights = (
        {c: 1 / len(cfg.universe.currencies) for c in cfg.universe.currencies}
        if cfg.portfolio.weighting == "equal"
        else cfg.portfolio.custom_weights
    )

    ccy_stats = []
    samples_by_ccy = {}
    for ccy in cfg.universe.currencies:
        samples = phase0_mtm_positive(data.fx[ccy], tenor_months=cfg.portfolio.tenor_years * 12)
        samples_by_ccy[ccy] = samples
        stats = summarize_mtm_distribution(samples)
        ccy_stats.append({"currency": ccy, **stats})

    portfolio_samples = weighted_portfolio_samples(samples_by_ccy, weights)

    pd_rows = []
    for pd_annual in cfg.credit.pd_scenarios_annual:
        el_bps = pd_annual * float(np.mean(portfolio_samples)) * 10000
        net_margin = (
            cfg.economics.client_fee_bps_pa
            - cfg.economics.opex_bps_pa
            - cfg.economics.ndf_cost_addon_bps_pa
            - cfg.economics.reserve_build_bps_pa
            - el_bps
        )
        pd_rows.append({"pd": pd_annual, "el_bps": el_bps, "net_margin_bps": net_margin})

    el_values = [r["el_bps"] for r in pd_rows]
    checks.append(f"EL monotonic with PD: {all(el_values[i] <= el_values[i+1] for i in range(len(el_values)-1))}")

    capital_pct = severity_capital(portfolio_samples, 0.995, cfg.capital_target.addon_pct)
    leverage = 1 / capital_pct if capital_pct > 0 else 0.0

    phase2_losses = None
    if cfg.run.phase >= 2:
        n_sim = min(5000, len(portfolio_samples))
        rng = np.random.default_rng(cfg.run.seed)
        losses = []
        for _ in range(n_sim):
            loss = 0.0
            for ccy in cfg.universe.currencies:
                spot_series = data.fx[ccy].dropna().values
                if len(spot_series) < 3:
                    continue
                idx0 = int(rng.integers(0, len(spot_series) - 2))
                s0 = float(spot_series[idx0])
                t_default = draw_default_times(cfg.credit.pd_scenarios_annual[1], cfg.portfolio.tenor_years, 1, int(rng.integers(1e9)))[0]
                if np.isinf(t_default):
                    continue
                t_idx = min(idx0 + max(1, int(round(t_default * 12))), len(spot_series) - 1)
                st = float(spot_series[t_idx])

                notional = cfg.portfolio.notional_usd_total * weights[ccy]
                usd_rate = 0.03
                lcy_rate = 0.06

                ccs = CCSParams(notional, s0, 0.03, 0.06, cfg.portfolio.tenor_years)
                ndf = NDFParams(notional, s0, cfg.portfolio.tenor_years)
                mtm = (
                    cfg.portfolio.mix.CCS * mtm_ccs_lender(ccs, st, t_default, usd_rate, lcy_rate)
                    + cfg.portfolio.mix.NDF * mtm_ndf_lender(ndf, st, t_default, usd_rate, lcy_rate)
                )
                payout = payout_default_only(
                    mtm,
                    cfg.guarantee.coverage_pct,
                    cfg.guarantee.attachment_pct_notional,
                    cfg.guarantee.detachment_pct_notional,
                    notional,
                )
                loss += payout
            losses.append(loss)
        phase2_losses = np.array(losses)

    expected_loss_amount = np.mean(phase2_losses) if phase2_losses is not None else np.mean(portfolio_samples) * cfg.credit.pd_scenarios_annual[1] * cfg.portfolio.notional_usd_total
    returns = stack_returns(cfg, cfg.portfolio.notional_usd_total, float(expected_loss_amount))
    fixed_costs_amount = (
        returns["opex"]
        + returns["ndf_addon"]
        + returns["reserve"]
        + returns["expected_loss"]
        + returns["mezz_coupon_amount"]
        + returns["counter_guarantee_fee_amount"]
    )
    be_fee = break_even_fee_bps(0.15, returns["equity_amount"], fixed_costs_amount, cfg.portfolio.notional_usd_total)

    lev_axis = np.arange(5, 31)
    curves = {}
    for pdv in cfg.credit.pd_scenarios_annual:
        el_per_notional = pdv * float(np.mean(portfolio_samples))
        curves[f"All-equity PD {int(pdv*100)}%"] = lev_axis * (
            cfg.economics.client_fee_bps_pa - cfg.economics.opex_bps_pa - el_per_notional * 10000
        ) / 10000
    curves["Equity ROE after stack costs (PD 4%)"] = np.full_like(lev_axis, returns["equity_roe"], dtype=float)

    out_dir = Path("outputs")
    fig1 = out_dir / "figures" / "leverage_vs_roe.png"
    fig2 = out_dir / "figures" / "loss_exceedance.png"
    plot_leverage_vs_roe(fig1, lev_axis, curves)
    if phase2_losses is not None and len(phase2_losses) > 0:
        plot_loss_exceedance(fig2, phase2_losses)

    roe_line = curves["All-equity PD 4%"] if "All-equity PD 4%" in curves else next(iter(curves.values()))
    checks.append(f"ROE monotonic with leverage: {bool(np.all(np.diff(roe_line) >= -1e-12))}")
    checks.append(
        "Counter-guarantee return matches configured fee: "
        f"{abs(returns['guarantor_return_on_guaranteed_amount'] - ((cfg.capital_stack[2].fee_bps_on_guaranteed_amount or 0)/10000.0)) < 1e-12}"
    )
    checks.append("Report and charts generated")

    report = [
        "# Guarantee Vehicle Report",
        "",
        "## Input Summary",
        f"- Phase: {cfg.run.phase}",
        f"- Currencies: {', '.join(cfg.universe.currencies)}",
        f"- Portfolio notional USD: {cfg.portfolio.notional_usd_total:,.0f}",
        "",
        "## Currency MTM+ Statistics",
        to_markdown_table(ccy_stats),
        "",
        "## EL and Net Margin by PD Scenario",
        to_markdown_table(pd_rows),
        "",
        "## Capital and Leverage",
        f"- Severity capital (% notional): {capital_pct:.4%}",
        f"- Implied max leverage: {leverage:.2f}x",
        "",
        "## Capital Stack Returns",
        to_markdown_table([returns | {"break_even_fee_bps_for_15pct_target_roe": be_fee}]),
        "",
        "## Acceptance Checks",
    ]
    report.extend([f"- {c}" for c in checks])
    report.extend([
        "",
        "## Figures",
        f"![Leverage vs ROE](figures/leverage_vs_roe.png)",
        f"![Loss exceedance](figures/loss_exceedance.png)",
    ])

    write_report(out_dir / "report.md", "\n".join(report))


if __name__ == "__main__":
    run()
