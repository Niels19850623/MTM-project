from __future__ import annotations

from guarantee_vehicle.config import AppConfig


def compute_stack_amounts(cfg: AppConfig, notional: float) -> dict[str, float]:
    return {layer.name: (layer.detach_pct - layer.attach_pct) * notional for layer in cfg.capital_stack}
