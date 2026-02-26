from __future__ import annotations

from dataclasses import dataclass

from guarantee_vehicle.market.curves import forward_rate, flat_discount_factor


@dataclass
class NDFParams:
    notional_usd: float
    strike: float
    tenor_years: int


def mtm_ndf_lender(params: NDFParams, spot_now: float, t_years: float, usd_rate: float, lcy_rate: float) -> float:
    rem = max(params.tenor_years - t_years, 0.0)
    if rem == 0:
        return 0.0
    fwd = forward_rate(spot_now, usd_rate, lcy_rate, rem)
    payoff_usd = params.notional_usd * (fwd / params.strike - 1.0)
    return payoff_usd * flat_discount_factor(usd_rate, rem)
