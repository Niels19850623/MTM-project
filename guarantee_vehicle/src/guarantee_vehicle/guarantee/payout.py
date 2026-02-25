from __future__ import annotations

from guarantee_vehicle.guarantee.contract import apply_attachment_detachment


def payout_default_only(mtm_lender: float, coverage_pct: float, attach_pct: float, detach_pct: float, notional: float) -> float:
    raw = coverage_pct * max(mtm_lender, 0.0)
    return apply_attachment_detachment(raw, attach_pct, detach_pct, notional)
