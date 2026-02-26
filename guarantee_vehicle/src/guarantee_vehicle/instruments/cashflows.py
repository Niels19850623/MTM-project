from __future__ import annotations


def generate_monthly_schedule(tenor_years: int) -> list[float]:
    n = tenor_years * 12
    return [i / 12.0 for i in range(1, n + 1)]
