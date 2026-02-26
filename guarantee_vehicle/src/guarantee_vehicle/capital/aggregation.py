from __future__ import annotations

import numpy as np


def weighted_portfolio_samples(samples_by_ccy: dict[str, np.ndarray], weights: dict[str, float]) -> np.ndarray:
    n = min(len(v) for v in samples_by_ccy.values())
    acc = np.zeros(n)
    for ccy, s in samples_by_ccy.items():
        acc += weights[ccy] * s[:n]
    return acc
