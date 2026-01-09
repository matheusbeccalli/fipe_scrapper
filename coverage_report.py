"""
FIPE Data Coverage Report Generator

Analyzes the database for gaps in price data and generates an HTML report
showing which model years have missing months between their first and last
recorded prices.

Usage:
    python coverage_report.py

Output:
    coverage_report_YYYY-MM-DD.html
"""

import pandas as pd
from sqlalchemy import create_engine, text
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
from typing import Dict, List, Set, Tuple, NamedTuple
from dataclasses import dataclass, field
import config


@dataclass
class ModelYearCoverage:
    """Coverage data for a single model year."""
    model_year_id: int
    year_code: str
    year_description: str
    first_month: date
    last_month: date
    recorded_months: Set[date]
    missing_months: List[date] = field(default_factory=list)

    @property
    def is_ok(self) -> bool:
        return len(self.missing_months) == 0

    @property
    def status_text(self) -> str:
        if self.is_ok:
            return "OK"
        return f"Missing {len(self.missing_months)} months"


@dataclass
class ModelCoverage:
    """Coverage data for a car model (aggregates model years)."""
    model_id: int
    model_code: str
    model_name: str
    model_years: List[ModelYearCoverage] = field(default_factory=list)

    @property
    def is_ok(self) -> bool:
        return all(my.is_ok for my in self.model_years)

    @property
    def status_text(self) -> str:
        if self.is_ok:
            return "OK"
        bad_count = sum(1 for my in self.model_years if not my.is_ok)
        return f"{bad_count} model year(s) with gaps"


@dataclass
class BrandCoverage:
    """Coverage data for a brand (aggregates models)."""
    brand_id: int
    brand_code: str
    brand_name: str
    models: List[ModelCoverage] = field(default_factory=list)

    @property
    def is_ok(self) -> bool:
        return all(m.is_ok for m in self.models)

    @property
    def status_text(self) -> str:
        if self.is_ok:
            return "OK"
        bad_count = sum(1 for m in self.models if not m.is_ok)
        return f"{bad_count} model(s) with gaps"


def get_database_connection():
    """Create database connection using config."""
    engine = create_engine(config.DATABASE_URL)
    return engine


def fetch_price_data(engine) -> pd.DataFrame:
    """
    Fetch all price records with their associated metadata.

    Returns a DataFrame with columns:
    - brand_id, brand_code, brand_name
    - model_id, model_code, model_name
    - model_year_id, year_code, year_description
    - month_date
    """
    query = """
    SELECT
        b.id as brand_id,
        b.brand_code,
        b.brand_name,
        cm.id as model_id,
        cm.model_code,
        cm.model_name,
        my.id as model_year_id,
        my.year_code,
        my.year_description,
        rm.month_date
    FROM car_prices cp
    JOIN reference_months rm ON cp.reference_month_id = rm.id
    JOIN model_years my ON cp.model_year_id = my.id
    JOIN car_models cm ON my.car_model_id = cm.id
    JOIN brands b ON cm.brand_id = b.id
    ORDER BY b.brand_name, cm.model_name, my.year_description, rm.month_date
    """

    df = pd.read_sql(query, engine)
    print(f"Fetched {len(df):,} price records")
    return df


if __name__ == "__main__":
    print("FIPE Data Coverage Report Generator")
    print("=" * 40)
    engine = get_database_connection()

    print("\nFetching price data...")
    df = fetch_price_data(engine)
    print(f"Data spans {df['month_date'].nunique()} unique months")
    print(f"Covering {df['brand_id'].nunique()} brands")
