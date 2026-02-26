from __future__ import annotations

import numpy as np


def simulate_gbm_paths(s0: float, mu: float, sigma: float, dt: float, n_steps: int, n_paths: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    z = rng.normal(size=(n_paths, n_steps))
    increments = (mu - 0.5 * sigma**2) * dt + sigma * np.sqrt(dt) * z
    log_paths = np.cumsum(increments, axis=1)
    paths = np.concatenate([np.full((n_paths, 1), s0), s0 * np.exp(log_paths)], axis=1)
    return paths
