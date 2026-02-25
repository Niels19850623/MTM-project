from __future__ import annotations

import numpy as np


def hazard_from_annual_pd(pd_annual: float) -> float:
    return float(-np.log(1 - pd_annual))


def draw_default_times(pd_annual: float, tenor_years: int, n: int, seed: int) -> np.ndarray:
    lam = hazard_from_annual_pd(pd_annual)
    rng = np.random.default_rng(seed)
    u = rng.random(n)
    t = -np.log(1 - u) / lam
    t[t > tenor_years] = np.inf
    return t
