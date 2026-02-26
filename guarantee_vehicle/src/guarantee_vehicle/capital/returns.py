from __future__ import annotations

from guarantee_vehicle.config import AppConfig


def bps_to_amount(bps: float, notional: float) -> float:
    return bps / 10000.0 * notional


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
