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


def generate_month_range(start_date: date, end_date: date) -> Set[date]:
    """Generate all months between start and end (inclusive)."""
    months = set()
    current = date(start_date.year, start_date.month, 1)
    end = date(end_date.year, end_date.month, 1)

    while current <= end:
        months.add(current)
        current = current + relativedelta(months=1)

    return months


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


HTML_STYLES = """
<style>
    * {
        box-sizing: border-box;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    }

    body {
        max-width: 1200px;
        margin: 0 auto;
        padding: 20px;
        background: #f5f5f5;
    }

    h1 {
        color: #333;
        border-bottom: 2px solid #007bff;
        padding-bottom: 10px;
    }

    .summary {
        background: white;
        padding: 20px;
        border-radius: 8px;
        margin-bottom: 20px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }

    .summary-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        gap: 15px;
    }

    .summary-item {
        text-align: center;
        padding: 15px;
        background: #f8f9fa;
        border-radius: 6px;
    }

    .summary-item .number {
        font-size: 2em;
        font-weight: bold;
        color: #007bff;
    }

    .summary-item .label {
        color: #666;
        font-size: 0.9em;
    }

    details {
        background: white;
        margin: 5px 0;
        border-radius: 6px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }

    details[open] > summary {
        border-bottom: 1px solid #eee;
    }

    summary {
        padding: 12px 15px;
        cursor: pointer;
        display: flex;
        justify-content: space-between;
        align-items: center;
        font-weight: 500;
    }

    summary:hover {
        background: #f8f9fa;
    }

    summary::marker {
        color: #007bff;
    }

    .brand-summary {
        font-size: 1.1em;
    }

    .model-summary {
        font-size: 1em;
        padding-left: 20px;
    }

    .model-year-item {
        padding: 10px 15px 10px 40px;
        border-bottom: 1px solid #f0f0f0;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }

    .model-year-item:last-child {
        border-bottom: none;
    }

    .status {
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.85em;
        font-weight: 500;
    }

    .status-ok {
        background: #d4edda;
        color: #155724;
    }

    .status-bad {
        background: #f8d7da;
        color: #721c24;
    }

    .date-range {
        color: #666;
        font-size: 0.85em;
        margin-left: 10px;
    }

    .missing-months {
        padding: 10px 15px 15px 60px;
        background: #fff5f5;
        font-size: 0.85em;
        color: #666;
    }

    .missing-months summary {
        padding: 5px 10px;
        font-size: 0.9em;
        color: #721c24;
    }

    .missing-list {
        padding: 10px;
        display: flex;
        flex-wrap: wrap;
        gap: 5px;
    }

    .missing-month {
        background: #f8d7da;
        color: #721c24;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.85em;
    }

    .content-wrapper {
        padding: 5px 15px 15px 15px;
    }

    .generated-at {
        text-align: center;
        color: #999;
        font-size: 0.85em;
        margin-top: 30px;
    }
</style>
"""


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


def analyze_coverage(df: pd.DataFrame) -> List[BrandCoverage]:
    """
    Analyze the price data to find coverage gaps.

    For each model year:
    1. Find first and last recorded month
    2. Generate expected months between them
    3. Find missing months (gaps)

    Returns list of BrandCoverage objects with full hierarchy.
    """
    brands: Dict[int, BrandCoverage] = {}

    # Ensure month_date is datetime.date
    df['month_date'] = pd.to_datetime(df['month_date']).dt.date

    # Group by model year to analyze each one
    for (brand_id, brand_code, brand_name, model_id, model_code, model_name,
         model_year_id, year_code, year_description), group in df.groupby([
            'brand_id', 'brand_code', 'brand_name',
            'model_id', 'model_code', 'model_name',
            'model_year_id', 'year_code', 'year_description'
         ]):

        # Get recorded months for this model year
        recorded_months = set(group['month_date'].tolist())
        first_month = min(recorded_months)
        last_month = max(recorded_months)

        # Generate expected months and find gaps
        expected_months = generate_month_range(first_month, last_month)
        missing_months = sorted(expected_months - recorded_months)

        # Create model year coverage
        my_coverage = ModelYearCoverage(
            model_year_id=model_year_id,
            year_code=year_code,
            year_description=year_description,
            first_month=first_month,
            last_month=last_month,
            recorded_months=recorded_months,
            missing_months=missing_months
        )

        # Add to hierarchy
        if brand_id not in brands:
            brands[brand_id] = BrandCoverage(
                brand_id=brand_id,
                brand_code=brand_code,
                brand_name=brand_name
            )

        brand = brands[brand_id]

        # Find or create model
        model = next((m for m in brand.models if m.model_id == model_id), None)
        if model is None:
            model = ModelCoverage(
                model_id=model_id,
                model_code=model_code,
                model_name=model_name
            )
            brand.models.append(model)

        model.model_years.append(my_coverage)

    # Sort brands by name
    return sorted(brands.values(), key=lambda b: b.brand_name)


def generate_html_report(brands: List[BrandCoverage], output_path: str) -> None:
    """Generate the HTML coverage report."""

    # Calculate summary stats
    total_brands = len(brands)
    total_models = sum(len(b.models) for b in brands)
    total_model_years = sum(len(m.model_years) for b in brands for m in b.models)
    ok_brands = sum(1 for b in brands if b.is_ok)
    ok_models = sum(1 for b in brands for m in b.models if m.is_ok)
    ok_model_years = sum(1 for b in brands for m in b.models for my in m.model_years if my.is_ok)

    html_parts = [
        "<!DOCTYPE html>",
        "<html lang='en'>",
        "<head>",
        "    <meta charset='UTF-8'>",
        "    <meta name='viewport' content='width=device-width, initial-scale=1.0'>",
        "    <title>FIPE Data Coverage Report</title>",
        HTML_STYLES,
        "</head>",
        "<body>",
        "    <h1>FIPE Data Coverage Report</h1>",
        "    <div class='summary'>",
        "        <div class='summary-grid'>",
        f"            <div class='summary-item'><div class='number'>{total_brands}</div><div class='label'>Brands ({ok_brands} OK)</div></div>",
        f"            <div class='summary-item'><div class='number'>{total_models:,}</div><div class='label'>Models ({ok_models:,} OK)</div></div>",
        f"            <div class='summary-item'><div class='number'>{total_model_years:,}</div><div class='label'>Model Years ({ok_model_years:,} OK)</div></div>",
        "        </div>",
        "    </div>",
    ]

    # Generate brand sections
    for brand in brands:
        brand_status_class = "status-ok" if brand.is_ok else "status-bad"
        html_parts.append(f"    <details>")
        html_parts.append(f"        <summary class='brand-summary'>")
        html_parts.append(f"            <span>{brand.brand_name}</span>")
        html_parts.append(f"            <span class='status {brand_status_class}'>{brand.status_text}</span>")
        html_parts.append(f"        </summary>")
        html_parts.append(f"        <div class='content-wrapper'>")

        for model in brand.models:
            model_status_class = "status-ok" if model.is_ok else "status-bad"
            html_parts.append(f"        <details>")
            html_parts.append(f"            <summary class='model-summary'>")
            html_parts.append(f"                <span>{model.model_name}</span>")
            html_parts.append(f"                <span class='status {model_status_class}'>{model.status_text}</span>")
            html_parts.append(f"            </summary>")

            for my in model.model_years:
                my_status_class = "status-ok" if my.is_ok else "status-bad"
                date_range = f"{my.first_month.strftime('%b %Y')} - {my.last_month.strftime('%b %Y')}"
                html_parts.append(f"            <div class='model-year-item'>")
                html_parts.append(f"                <span>{my.year_description}<span class='date-range'>({date_range})</span></span>")
                html_parts.append(f"                <span class='status {my_status_class}'>{my.status_text}</span>")
                html_parts.append(f"            </div>")

                # Add expandable missing months if there are gaps
                if my.missing_months:
                    html_parts.append(f"            <div class='missing-months'>")
                    html_parts.append(f"                <details>")
                    html_parts.append(f"                    <summary>Show missing months</summary>")
                    html_parts.append(f"                    <div class='missing-list'>")
                    for missing in my.missing_months:
                        html_parts.append(f"                        <span class='missing-month'>{missing.strftime('%b %Y')}</span>")
                    html_parts.append(f"                    </div>")
                    html_parts.append(f"                </details>")
                    html_parts.append(f"            </div>")

            html_parts.append(f"        </details>")

        html_parts.append(f"        </div>")
        html_parts.append(f"    </details>")

    # Footer
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    html_parts.extend([
        f"    <div class='generated-at'>Generated at {generated_at}</div>",
        "</body>",
        "</html>"
    ])

    # Write to file
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(html_parts))

    print(f"\nReport saved to: {output_path}")


if __name__ == "__main__":
    print("FIPE Data Coverage Report Generator")
    print("=" * 40)
    engine = get_database_connection()

    print("\nFetching price data...")
    df = fetch_price_data(engine)
    print(f"Data spans {df['month_date'].nunique()} unique months")
    print(f"Covering {df['brand_id'].nunique()} brands")

    print("\nAnalyzing coverage gaps...")
    brands = analyze_coverage(df)

    # Print summary
    total_model_years = sum(len(m.model_years) for b in brands for m in b.models)
    ok_model_years = sum(1 for b in brands for m in b.models for my in m.model_years if my.is_ok)
    print(f"Analyzed {total_model_years:,} model years")
    print(f"  OK: {ok_model_years:,}")
    print(f"  With gaps: {total_model_years - ok_model_years:,}")

    # Generate HTML report
    output_filename = f"coverage_report_{datetime.now().strftime('%Y-%m-%d')}.html"
    generate_html_report(brands, output_filename)
