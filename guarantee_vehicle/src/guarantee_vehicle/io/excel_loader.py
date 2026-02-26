from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from guarantee_vehicle.config import AppConfig


@dataclass
class LoadedData:
    fx: pd.DataFrame
    rates: dict[str, pd.Series]


def _read_sheet(path: str | Path, sheet_name: str) -> pd.DataFrame:
    return pd.read_excel(path, sheet_name=sheet_name, header=None, engine="openpyxl")


def load_fx_history(path: str | Path, cfg: AppConfig) -> pd.DataFrame:
    sheet = _read_sheet(path, cfg.data.excel.fx_sheet)
    date_row = cfg.data.excel.dates_row_index
    code_col = cfg.data.excel.fx_row_key_column
    start_row = cfg.data.excel.values_start_row_index
    start_col = cfg.data.excel.values_start_col_index

    date_values = pd.to_datetime(sheet.iloc[date_row, start_col:], errors="coerce")
    out: dict[str, pd.Series] = {}
    for row in range(start_row, sheet.shape[0]):
        ccy = sheet.iloc[row, code_col]
        if pd.isna(ccy):
            continue
        ccy_str = str(ccy).strip().upper()
        if ccy_str in cfg.universe.currencies:
            vals = pd.to_numeric(sheet.iloc[row, start_col:], errors="coerce")
            series = pd.Series(vals.values, index=date_values.values).dropna()
            if not series.empty:
                series.index = pd.to_datetime(series.index)
                out[ccy_str] = series.sort_index()

    fx_df = pd.DataFrame(out).sort_index().ffill().dropna(how="all")
    return fx_df


def load_rates(path: str | Path, cfg: AppConfig) -> dict[str, pd.Series]:
    if not cfg.data.rates.enabled:
        return {}

    sheet = _read_sheet(path, cfg.data.rates.sheet)
    rates: dict[str, pd.Series] = {}
    # simple mapping: first column contains key; remaining columns are time series
    for ccy, key in cfg.data.rates.mapping.items():
        matches = sheet.index[sheet.iloc[:, 0].astype(str).str.strip() == str(key).strip()].tolist()
        if not matches:
            continue
        row = matches[0]
        values = pd.to_numeric(sheet.iloc[row, 1:], errors="coerce").dropna()
        rates[ccy] = values.reset_index(drop=True)
    return rates


def load_data(path: str | Path, cfg: AppConfig) -> LoadedData:
    fx = load_fx_history(path, cfg)
    rates = load_rates(path, cfg)
    return LoadedData(fx=fx, rates=rates)
