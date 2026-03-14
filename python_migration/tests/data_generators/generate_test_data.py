"""
Generate synthetic test data for pipeline testing.

Creates realistic DataFrames that mimic the structure of actual IW/Excel data
for unit and integration tests without requiring real data connections.
"""

from __future__ import annotations

import random
from datetime import date, timedelta

import polars as pl


def generate_car_data(n_rows: int = 500, seed: int = 42) -> pl.DataFrame:
    """Generate synthetic CAR (Capital Adequacy Ratio) exposure data."""
    random.seed(seed)
    port_cds = ["Ia", "Ib", "II", "III", "IV", "IVa", "V", "VI", "VII",
                "VIIIa", "VIIIb", "IX", "X", "B1", "B2", "B5", "B14", "B18"]
    bus_units = ["CBG", "CBIC", "WBG", "IBG", "BB", "CTU", "ORR", "OFD"]
    entities = ["KW", "CF", "SZ", "VC"]
    ccys = ["HKD", "USD", "CNY", "EUR", "GBP", "JPY", "SGD"]

    return pl.DataFrame({
        "ACCT_ID": [f"ACCT{i:06d}" for i in range(n_rows)],
        "RM_CUST_ID": [f"CUST{random.randint(1, n_rows // 5):05d}" for _ in range(n_rows)],
        "PORT_CD": [random.choice(port_cds) for _ in range(n_rows)],
        "IND_BUS_UNIT": [random.choice(bus_units) for _ in range(n_rows)],
        "FLAG_SRC": [random.choice(entities) for _ in range(n_rows)],
        "CCY_CD": [random.choice(ccys) for _ in range(n_rows)],
        "APPL_CRM_AMT_HKE": [round(random.uniform(100, 5_000_000), 2) for _ in range(n_rows)],
        "ORIG_CRM_AMT_HKE": [round(random.uniform(100, 5_000_000), 2) for _ in range(n_rows)],
        "RISK_WEIGHTED_AMT_HKE": [round(random.uniform(0, 3_000_000), 2) for _ in range(n_rows)],
        "APPL_RISK_WEIGHT": [random.choice([0, 10, 20, 35, 50, 75, 100, 150]) for _ in range(n_rows)],
        "CCF": [random.choice([0, 20, 50, 100]) for _ in range(n_rows)],
        "ECAI_RATING": [random.choice(["AAA", "AA", "A", "BBB", "BB", "B", "", None]) for _ in range(n_rows)],
        "NOTCH": [random.choice([1, 2, 3, 5, 8, 11, 15, 22, None]) for _ in range(n_rows)],
        "CMV_HKE": [round(random.uniform(0, 10_000_000), 2) for _ in range(n_rows)],
        "ORIG_LTV_RATIO": [round(random.uniform(0, 150), 2) for _ in range(n_rows)],
        "FILE_SRC": [random.choice(["SYSTEM", "MANUAL", "IX", "CBIC"]) for _ in range(n_rows)],
    })


def generate_stress_parameters() -> pl.DataFrame:
    """Generate synthetic stress parameter data."""
    segments = ["RML", "WBG", "IBG", "BB", "CTU", "ORR", "CBIC", "IBG_SGP"]
    rows = []
    for seg in segments:
        rows.append({
            "SEGMENT": seg,
            "NPL_TARGET_0": 0.01,
            "NPL_TARGET_1": 0.03,
            "NPL_TARGET_2": 0.05,
            "NPL_TARGET_3": 0.10,
            "LGD_0": 0.45,
            "LGD_1": 0.45,
            "LGD_2": 0.50,
            "LGD_3": 0.55,
            "NPL_COV_0": 0.60,
            "NPL_COV_1": 0.55,
            "NPL_COV_2": 0.50,
            "NPL_COV_3": 0.45,
            "LOAN_GROWTH_0": 0.05,
            "LOAN_GROWTH_1": 0.02,
            "LOAN_GROWTH_2": 0.00,
            "LOAN_GROWTH_3": -0.03,
        })
    return pl.DataFrame(rows)


def generate_master_scale_pd(n_notches: int = 22) -> pl.DataFrame:
    """Generate synthetic master scale PD data."""
    pds = [0.0001 * (1.5 ** i) for i in range(n_notches)]
    rw_long = [0, 10, 20, 20, 50, 50, 50, 100, 100, 100, 100, 100,
               100, 100, 150, 150, 150, 150, 150, 150, 150, 150]
    rw_short = [0, 20, 20, 50, 50, 100, 100, 100, 100, 150, 150, 150,
                150, 150, 150, 150, 150, 150, 150, 150, 150, 150]
    return pl.DataFrame({
        "NOTCH": list(range(1, n_notches + 1)),
        "PD_AVG": pds[:n_notches],
        "RW_LONG": rw_long[:n_notches],
        "RW_SHORT": rw_short[:n_notches],
        "RATING": [f"R{i:02d}" for i in range(1, n_notches + 1)],
    })


def generate_npl_data(n_rows: int = 100, seed: int = 42) -> pl.DataFrame:
    """Generate synthetic NPL (Non-Performing Loan) data."""
    random.seed(seed)
    bus_units = ["RML", "WBG", "IBG", "BB", "CTU", "CBIC"]
    return pl.DataFrame({
        "BU": [random.choice(bus_units) for _ in range(n_rows)],
        "ACCT_ID": [f"NPL{i:05d}" for i in range(n_rows)],
        "EXPOSURE": [round(random.uniform(1000, 1_000_000), 2) for _ in range(n_rows)],
        "NPL_FLAG": [random.choice([0, 0, 0, 0, 1]) for _ in range(n_rows)],
        "DAYS_PAST_DUE": [random.choice([0, 0, 0, 30, 60, 90, 180]) for _ in range(n_rows)],
    })


def generate_aps_data(n_rows: int = 200, seed: int = 42) -> pl.DataFrame:
    """Generate synthetic APS (Application Processing System) data."""
    random.seed(seed)
    base_date = date(2014, 1, 1)
    return pl.DataFrame({
        "APPLICATION_ID": [f"APP{i:06d}" for i in range(n_rows)],
        "ACCT_ID": [f"ACCT{i:06d}" for i in range(n_rows)],
        "APPL_DATE": [base_date + timedelta(days=random.randint(0, 365)) for _ in range(n_rows)],
        "IND_PRODUCT": [random.choice([10, 11, 12, 20, 30, 40]) for _ in range(n_rows)],
        "STATUS": [random.choice(["A", "D", "C", "P"]) for _ in range(n_rows)],
        "INCOME": [round(random.uniform(10000, 200000), 2) for _ in range(n_rows)],
        "CREDIT_LIMIT": [round(random.uniform(5000, 500000), 2) for _ in range(n_rows)],
        "FLAG_STAFF": [random.choice([0, 0, 0, 0, 1]) for _ in range(n_rows)],
        "FLAG_SUPPLEMENTARY": [random.choice([0, 0, 0, 0, 1]) for _ in range(n_rows)],
    })


def generate_rating_data(n_rows: int = 50, seed: int = 42) -> pl.DataFrame:
    """Generate synthetic credit rating data."""
    random.seed(seed)
    ratings = ["AAA", "AA+", "AA", "AA-", "A+", "A", "A-",
               "BBB+", "BBB", "BBB-", "BB+", "BB", "BB-",
               "B+", "B", "B-", "CCC", "D"]
    return pl.DataFrame({
        "RM_CUST_ID": [f"CUST{i:05d}" for i in range(n_rows)],
        "CCY_GROUP": [random.choice(["HKD", "USD", "CNY"]) for _ in range(n_rows)],
        "ECAI_RATING": [random.choice(ratings) for _ in range(n_rows)],
        "NOTCH": [random.randint(1, 22) for _ in range(n_rows)],
        "FLAG_TARGET": [random.choice([0, 1]) for _ in range(n_rows)],
    })
