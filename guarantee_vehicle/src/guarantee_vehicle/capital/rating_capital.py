from __future__ import annotations

import numpy as np


def severity_capital(samples: np.ndarray, quantile: float, addon_pct: float) -> float:
    sev = float(np.quantile(samples, quantile))
    return sev * (1 + addon_pct)


def var_or_es(losses: np.ndarray, confidence: float, method: str) -> float:
    v = float(np.quantile(losses, confidence))
    if method == "VaR":
        return v
    tail = losses[losses >= v]
    return float(tail.mean()) if len(tail) else v
