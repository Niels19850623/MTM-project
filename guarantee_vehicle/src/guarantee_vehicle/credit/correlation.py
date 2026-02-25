from __future__ import annotations

import numpy as np


def correlate_normals(chol: np.ndarray, z: np.ndarray) -> np.ndarray:
    return z @ chol.T
