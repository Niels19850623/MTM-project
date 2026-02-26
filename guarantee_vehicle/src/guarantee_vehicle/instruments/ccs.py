from __future__ import annotations

from dataclasses import dataclass

from guarantee_vehicle.market.curves import flat_discount_factor


@dataclass
class CCSParams:
    notional_usd: float
    spot_lcy_per_usd: float
    fixed_usd_rate: float
    fixed_lcy_rate: float
    tenor_years: int
    include_notional_exchange: bool = True


def mtm_ccs_lender(params: CCSParams, spot_now: float, t_years: float, usd_disc: float, lcy_disc: float) -> float:
    rem = max(params.tenor_years - t_years, 0.0)
    if rem == 0:
        return 0.0
    usd_leg = params.notional_usd * (1 + params.fixed_usd_rate * rem) * flat_discount_factor(usd_disc, rem)
    lcy_notional = params.notional_usd * params.spot_lcy_per_usd
    lcy_leg = (lcy_notional / spot_now) * (1 + params.fixed_lcy_rate * rem) * flat_discount_factor(lcy_disc, rem)
    return usd_leg - lcy_leg
