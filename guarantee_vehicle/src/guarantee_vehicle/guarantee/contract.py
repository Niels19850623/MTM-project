from __future__ import annotations


def apply_attachment_detachment(loss: float, attach: float, detach: float, notional: float) -> float:
    lo = attach * notional
    hi = detach * notional
    return max(min(loss, hi) - lo, 0.0)
