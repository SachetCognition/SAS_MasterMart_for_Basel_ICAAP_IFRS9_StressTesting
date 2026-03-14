# SAS MasterMart — Python Migration

Complete Python translation of the SAS MasterMart for Basel ICAAP, IFRS9, and Stress Testing.

## Overview

This migration translates ~79 SAS files into Python using **Polars** for data manipulation and **DuckDB** for persistence, preserving all business logic exactly.

## Architecture

```
python_migration/
├── config/          # Settings translated from STARTSCRIPT.sas
├── lib/             # Shared libraries (macros, lookups, Excel reader, validation)
├── extract/         # Data ingestion (Oracle IW, Basel SGP, parameters, APS/PIL)
├── modules/
│   ├── car_base/    # Core CAR_BASE pipeline (21 modules)
│   ├── ru_nonbank/  # Non-bank exposure & NPL (11 modules)
│   ├── st_segment/  # Stress testing — 8 Basel asset classes (12 modules)
│   ├── rst_segment/ # Reverse stress testing (15 modules)
│   ├── st_country_fi/ # Country FI stress (3 modules)
│   ├── bis_check/   # Basel III CSRBB reporting (4 modules)
│   ├── ploan_acard/ # Credit card/P-loan modeling (7 modules)
│   └── rp_segment/  # Risk parameter segmentation (10 modules)
├── dags/            # Pipeline orchestrators (6 DAGs)
├── tests/           # Unit, integration, regression, performance tests
└── artifacts/       # Output directory
```

## Quick Start

```bash
# Install dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Run lint
ruff check .
```

## Pipeline Execution

Each pipeline is orchestrated by a DAG module:

```python
from config.settings import Config
from dags.car_base_dag import run_pipeline

config = Config.from_yaml("config/settings.yaml")
results = run_pipeline(config, datasets={})
```

## Key Design Decisions

| SAS Pattern | Python Equivalent |
|---|---|
| `%let` macro variables | `Config` dataclass fields |
| `PROC FORMAT` | `lib/lookups.py` dictionaries |
| `%ORA_Extract` macro | `lib/macros.ora_extract()` |
| `%ErrAdj` dynamic code gen | `lib/macros.error_adjustment()` → dict of rules |
| `%SGPImport` metadata-driven | `lib/excel_reader.import_sgp_excel()` |
| `%addFieldSuffix` | `lib/datasets.add_field_suffix()` |
| `PROC TABULATE` | `lib/report_writer.write_tabulate_report()` |
| SAS array loops | Vectorized Polars expressions |
| SAS data step merge | `pl.DataFrame.join()` |
| `libname` references | File paths in `Config` |

## Stress Testing Scenarios

All stress modules support 4 scenarios:
- **ST0**: Baseline (no stress)
- **ST1**: Mild stress
- **ST2**: Medium stress
- **ST3**: Severe stress

Parameters per scenario include: FI notch shifts, property YoY/haircuts, NPL targets, LGD, loan growth, derivative CE multiplier.

## Validation

Use `PipelineValidator` to compare Python outputs against SAS CSV exports:

```python
from lib.validation import PipelineValidator

validator = PipelineValidator()
report = validator.compare_datasets(
    sas_csv_path="path/to/sas_output.csv",
    python_df=my_dataframe,
    key_columns=["ACCT_ID"],
    tolerance=0.005,
)
validator.assert_match(report)
```

## Dependencies

- Python >= 3.11
- polars >= 0.20.0
- duckdb >= 0.10.0
- oracledb >= 2.0.0
- openpyxl >= 3.1.0
- xlsxwriter >= 3.1.0
- pyyaml >= 6.0
- pyarrow >= 14.0.0
