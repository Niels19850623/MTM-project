from __future__ import annotations

from guarantee_vehicle.config import AppConfig


def bps_to_amount(bps: float, notional: float) -> float:
    return bps / 10000.0 * notional


def _stack_base_percents(cfg: AppConfig) -> tuple[float, float, float, float | None, float | None, float | None]:
    equity_pct = 0.0
    mezz_pct = 0.0
    cg_pct = 0.0
    mezz_coupon = None
    cg_fee_bps = None
    cg_cap_factor = None

    for layer in cfg.capital_stack:
        layer_pct = layer.detach_pct - layer.attach_pct
        if layer.type == "equity":
            equity_pct += layer_pct
        elif layer.type == "mezz":
            mezz_pct += layer_pct
            mezz_coupon = layer.coupon_pct if layer.coupon_pct is not None else mezz_coupon
        elif layer.type == "counter_guarantee":
            cg_pct += layer_pct
            cg_fee_bps = layer.fee_bps_on_guaranteed_amount if layer.fee_bps_on_guaranteed_amount is not None else cg_fee_bps
            cg_cap_factor = layer.guarantor_capital_factor if layer.guarantor_capital_factor is not None else cg_cap_factor

    return equity_pct, mezz_pct, cg_pct, mezz_coupon, cg_fee_bps, cg_cap_factor


def returns_for_leverage(
    cfg: AppConfig,
    leverage: float,
    expected_loss_rate: float,
) -> dict[str, float]:
    """Compute investor returns for a target leverage (Notional/Equity).

    Expected loss rate is expressed as fraction of notional (e.g. 0.003 = 30 bps).
    Mezz and counter-guarantee capital percentages are scaled from config stack
    in proportion to equity so investor mix remains comparable as leverage changes.
    """
    if leverage <= 0:
        raise ValueError("leverage must be > 0")

    equity_base, mezz_base, cg_base, mezz_coupon, cg_fee_bps, cg_cap_factor = _stack_base_percents(cfg)
    if equity_base <= 0:
        raise ValueError("capital_stack must include a positive-width equity layer")

    equity_pct = 1.0 / leverage
    scale = equity_pct / equity_base
    mezz_pct = mezz_base * scale
    cg_pct = cg_base * scale

    total_cap_pct = equity_pct + mezz_pct + cg_pct
    if total_cap_pct >= 1.0:
        raise ValueError(
            f"target leverage {leverage:.2f}x implies capital stack {total_cap_pct:.2%} of notional; reduce leverage"
        )

    gross_fee_rate = cfg.economics.client_fee_bps_pa / 10000.0
    opex_rate = cfg.economics.opex_bps_pa / 10000.0
    addon_rate = (cfg.economics.ndf_cost_addon_bps_pa + cfg.economics.reserve_build_bps_pa) / 10000.0

    mezz_coupon_rate = (mezz_coupon or 0.0) * mezz_pct
    cg_fee_rate = ((cg_fee_bps or 0.0) / 10000.0) * cg_pct

    equity_residual_rate = gross_fee_rate - opex_rate - addon_rate - expected_loss_rate - mezz_coupon_rate - cg_fee_rate
    equity_roe = equity_residual_rate / equity_pct if equity_pct > 0 else 0.0

    guarantor_return = (cg_fee_bps or 0.0) / 10000.0 if cg_pct > 0 else 0.0
    guarantor_roe = guarantor_return / cg_cap_factor if (cg_cap_factor and cg_pct > 0) else 0.0

    return {
        "leverage": leverage,
        "equity_pct": equity_pct,
        "mezz_pct": mezz_pct,
        "counter_guarantee_pct": cg_pct,
        "gross_fee_rate": gross_fee_rate,
        "expected_loss_rate": expected_loss_rate,
        "equity_roe": equity_roe,
        "mezz_return": mezz_coupon or 0.0,
        "guarantor_return_on_guaranteed_amount": guarantor_return,
        "guarantor_roe": guarantor_roe,
    }


def stack_returns(cfg: AppConfig, notional: float, expected_loss_amount: float) -> dict[str, float]:
    gross = bps_to_amount(cfg.economics.client_fee_bps_pa, notional)
    opex = bps_to_amount(cfg.economics.opex_bps_pa, notional)
    ndf_addon = bps_to_amount(cfg.economics.ndf_cost_addon_bps_pa, notional)
    reserve = bps_to_amount(cfg.economics.reserve_build_bps_pa, notional)

    mezz_coupon = 0.0
    cg_fee = 0.0
    equity_amt = 0.0
    mezz_amt = 0.0
    cg_amt = 0.0
    cg_cap_factor = None

    for layer in cfg.capital_stack:
        layer_amt = (layer.detach_pct - layer.attach_pct) * notional
        if layer.type == "equity":
            equity_amt += layer_amt
        elif layer.type == "mezz":
            mezz_amt += layer_amt
            mezz_coupon += (layer.coupon_pct or 0.0) * layer_amt
        elif layer.type == "counter_guarantee":
            cg_amt += layer_amt
            cg_fee += (layer.fee_bps_on_guaranteed_amount or 0.0) / 10000.0 * layer_amt
            cg_cap_factor = layer.guarantor_capital_factor

    residual_to_equity = gross - opex - ndf_addon - reserve - expected_loss_amount - mezz_coupon - cg_fee
    equity_roe = residual_to_equity / equity_amt if equity_amt > 0 else 0.0
    guarantor_return = cg_fee / cg_amt if cg_amt > 0 else 0.0
    guarantor_roe = guarantor_return / cg_cap_factor if cg_cap_factor else 0.0

    return {
        "gross_premium": gross,
        "opex": opex,
        "ndf_addon": ndf_addon,
        "reserve": reserve,
        "expected_loss": expected_loss_amount,
        "mezz_coupon_amount": mezz_coupon,
        "counter_guarantee_fee_amount": cg_fee,
        "equity_residual": residual_to_equity,
        "equity_amount": equity_amt,
        "equity_roe": equity_roe,
        "mezz_return": cfg.capital_stack[1].coupon_pct if len(cfg.capital_stack) > 1 and cfg.capital_stack[1].coupon_pct else 0.0,
        "guarantor_return_on_guaranteed_amount": guarantor_return,
        "guarantor_roe": guarantor_roe,
    }


def break_even_fee_bps(target_roe: float, equity_amount: float, fixed_costs_amount: float, notional: float) -> float:
    required = target_roe * equity_amount + fixed_costs_amount
    return required / notional * 10000.0
