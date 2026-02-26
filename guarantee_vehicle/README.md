# Guarantee Vehicle Model

Python model for pricing and risk-managing a guarantee company that covers positive close-out MTM at default.

## Data requirement
This model reads FX and rates from a supplied Excel file. Provide the file path via `--excel`. If workbook layout differs, update `config.yaml` under `data.excel` and `data.rates.mapping`.

## Structure
Implements phase-driven workflow (0-4), with working Phase 0-2.

## Install
```bash
pip install -e .
```

## Run
```bash
python -m guarantee_vehicle.cli --config examples/config_example.yaml --excel "/path/to/FX Data and Interest rates.xlsx"
```

## Dashboard
Run a standalone browser dashboard with upload/download workflow:
```bash
streamlit run src/guarantee_vehicle/dashboard.py
```

Dashboard features:
- Upload your `.xlsx` directly in the app (no CLI path required).
- Adjust workbook mapping inputs (sheet names/row/column indices and rate keys) in the sidebar.
- Compute investor-level returns (equity ROE, mezz return, guarantor ROE) with leverage as a direct input.
- Download a prefilled template Excel file based on the currently loaded data so you can tweak and re-upload.

## Outputs
- `outputs/report.md`
- `outputs/figures/leverage_vs_roe.png`
- `outputs/figures/loss_exceedance.png` (Phase 2+)
