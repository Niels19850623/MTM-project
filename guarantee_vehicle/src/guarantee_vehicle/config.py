from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, model_validator


class RunConfig(BaseModel):
    phase: int = Field(ge=0, le=4)
    seed: int
    time_step: Literal["monthly"]


class UniverseConfig(BaseModel):
    currencies: list[str]
    quote_convention: Literal["LCY_per_USD"]


class ExcelDataConfig(BaseModel):
    fx_sheet: str
    fx_row_key_column: int
    dates_row_index: int
    values_start_row_index: int
    values_start_col_index: int


class RatesConfig(BaseModel):
    enabled: bool = True
    sheet: str
    mapping: dict[str, str]


class DataConfig(BaseModel):
    excel: ExcelDataConfig
    rates: RatesConfig


class MixConfig(BaseModel):
    CCS: float
    NDF: float

    @model_validator(mode="after")
    def sum_to_1(self) -> "MixConfig":
        total = self.CCS + self.NDF
        if abs(total - 1.0) > 1e-8:
            raise ValueError(f"portfolio.mix must sum to 1.0, got {total}")
        return self


class PortfolioConfig(BaseModel):
    tenor_years: int = Field(gt=0)
    mix: MixConfig
    weighting: Literal["equal", "custom"]
    custom_weights: dict[str, float] = Field(default_factory=dict)
    notional_usd_total: float = Field(gt=0)


class FXDefaultDependenceConfig(BaseModel):
    enabled: bool = False
    method: str = "copula"
    strength: float = 0.0


class CreditConfig(BaseModel):
    pd_scenarios_annual: list[float]
    lgd: float = Field(gt=0, le=1)
    default_timing: Literal["constant_hazard"]
    fx_default_dependence: FXDefaultDependenceConfig


class GuaranteeConfig(BaseModel):
    trigger: Literal["default_only"]
    coverage_pct: float = Field(gt=0, le=1)
    payout: str
    collateralisation: str
    attachment_pct_notional: float = Field(ge=0, le=1)
    detachment_pct_notional: float = Field(gt=0, le=1)

    @model_validator(mode="after")
    def attachment_lt_detachment(self) -> "GuaranteeConfig":
        if self.attachment_pct_notional >= self.detachment_pct_notional:
            raise ValueError("guarantee.attachment_pct_notional must be less than detachment_pct_notional")
        return self


class EconomicsConfig(BaseModel):
    client_fee_bps_pa: float
    opex_bps_pa: float
    ndf_cost_addon_bps_pa: float = 0.0
    reserve_build_bps_pa: float = 0.0


class ConcentrationLimitsConfig(BaseModel):
    max_currency_weight: float
    max_single_counterparty_weight: float


class CapitalTargetConfig(BaseModel):
    label: str
    method: Literal["VaR", "ES"]
    confidence: float
    horizon_years: int
    addon_pct: float
    concentration_limits: ConcentrationLimitsConfig


class StackLayer(BaseModel):
    name: str
    type: Literal["equity", "mezz", "counter_guarantee"]
    attach_pct: float
    detach_pct: float
    coupon_pct: float | None = None
    fee_bps_on_guaranteed_amount: float | None = None
    guarantor_capital_factor: float | None = None


class AppConfig(BaseModel):
    run: RunConfig
    universe: UniverseConfig
    data: DataConfig
    portfolio: PortfolioConfig
    credit: CreditConfig
    guarantee: GuaranteeConfig
    economics: EconomicsConfig
    capital_target: CapitalTargetConfig
    capital_stack: list[StackLayer]

    @model_validator(mode="after")
    def validate_stack(self) -> "AppConfig":
        if not self.capital_stack:
            raise ValueError("capital_stack cannot be empty")
        return self


def load_config(path: str | Path) -> AppConfig:
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    return AppConfig.model_validate(raw)
