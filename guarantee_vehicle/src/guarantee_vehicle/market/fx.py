from __future__ import annotations

import numpy as np
import pandas as pd


def phase0_mtm_positive(fx_series: pd.Series, tenor_months: int = 60) -> np.ndarray:
    s = fx_series.dropna().astype(float).values
    mtm_pos: list[float] = []
    for t0 in range(len(s) - 1):
        end = min(len(s), t0 + tenor_months + 1)
        for t in range(t0 + 1, end):
            mtm = max((s[t0] / s[t]) - 1.0, 0.0)
            mtm_pos.append(mtm)
    return np.array(mtm_pos, dtype=float)


def summarize_mtm_distribution(samples: np.ndarray) -> dict[str, float]:
    if len(samples) == 0:
        return {"p_positive": 0.0, "mean": 0.0, "p90": 0.0, "p99": 0.0, "p995": 0.0}
    return {
        "p_positive": float((samples > 0).mean()),
        "mean": float(samples.mean()),
        "p90": float(np.quantile(samples, 0.90)),
        "p99": float(np.quantile(samples, 0.99)),
        "p995": float(np.quantile(samples, 0.995)),
    }
