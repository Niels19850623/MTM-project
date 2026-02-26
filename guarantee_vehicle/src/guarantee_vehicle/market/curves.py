from __future__ import annotations

import numpy as np


def flat_discount_factor(rate: float, t_years: float) -> float:
    return float(np.exp(-rate * t_years))


def forward_rate(spot: float, r_dom: float, r_for: float, t_years: float) -> float:
    return float(spot * np.exp((r_dom - r_for) * t_years))
