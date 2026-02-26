from __future__ import annotations

from guarantee_vehicle.config import AppConfig
from guarantee_vehicle.io.excel_loader import LoadedData


def validate_loaded_data(data: LoadedData, cfg: AppConfig) -> list[str]:
    checks: list[str] = []
    missing_fx = [c for c in cfg.universe.currencies if c not in data.fx.columns]
    if missing_fx:
        raise ValueError(f"Missing FX series for currencies: {missing_fx}")
    checks.append("FX series loaded for all configured currencies")

    if cfg.data.rates.enabled:
        missing_rates = [c for c in cfg.data.rates.mapping if c not in data.rates]
        if missing_rates:
            raise ValueError(
                "Missing rate rows for mapped currencies: "
                f"{missing_rates}. Update data.rates.mapping or workbook layout."
            )
        checks.append("Rate mappings resolved for all configured currencies")
    return checks
