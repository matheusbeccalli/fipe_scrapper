"""
FIPE Data Coverage Report Generator

Analyzes the database for gaps in price data and generates an HTML report
showing which model years have missing months between their first and last
recorded prices.

Usage:
    python coverage_report.py           # Fast report (no API verification)
    python coverage_report.py --verify  # Verify gaps against FIPE API

Output:
    coverage_report_YYYY-MM-DD.html
"""

import argparse
import asyncio
import pandas as pd
import aiohttp
from sqlalchemy import create_engine, text
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
from typing import Dict, List, Set, Optional
from dataclasses import dataclass, field
import config
from proxy_manager import ProxyPool, ProxyWorkerPool
from cloudflare_bypass import CloudflareBypass, CLOUDSCRAPER_AVAILABLE


# API Configuration (matching fipe_api_scraper.py)
API_BASE_URL = "http://veiculos.fipe.org.br/api/veiculos"
VEHICLE_TYPE_CAR = 1
API_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'application/json, text/javascript, */*; q=0.01',
    'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
    'Origin': 'http://veiculos.fipe.org.br',
    'Referer': 'http://veiculos.fipe.org.br/',
    'X-Requested-With': 'XMLHttpRequest',
}
API_REQUEST_DELAY = 0.5  # 500ms between requests


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
    # Fields for API verification (populated during analysis)
    brand_code: str = ""
    model_code: str = ""
    # Track filtered gaps during verification
    filtered_count: int = 0

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

    .verification-badge {
        background: white;
        padding: 12px 20px;
        border-radius: 8px;
        margin-bottom: 15px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        display: flex;
        align-items: center;
        gap: 10px;
    }

    .badge {
        padding: 6px 14px;
        border-radius: 20px;
        font-weight: 600;
        font-size: 0.9em;
    }

    .badge.verified {
        background: #d4edda;
        color: #155724;
    }

    .badge.unverified {
        background: #fff3cd;
        color: #856404;
    }

    .badge-info {
        color: #666;
        font-size: 0.9em;
    }

    .filtered-info {
        background: #e8f4fd;
        padding: 10px 20px;
        border-radius: 8px;
        margin-bottom: 15px;
        color: #0c5460;
        font-size: 0.9em;
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
            missing_months=missing_months,
            brand_code=str(brand_code),
            model_code=str(model_code)
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


# ============================================================================
# API Verification Functions
# ============================================================================

async def fetch_reference_months(session: aiohttp.ClientSession) -> Dict[date, int]:
    """
    Fetch all reference months from the FIPE API.

    Returns:
        Dict mapping date objects to month codes (e.g., {date(2024, 12, 1): 312})
    """
    url = f"{API_BASE_URL}/ConsultarTabelaDeReferencia"

    try:
        async with session.post(url, headers=API_HEADERS) as response:
            if response.status == 200:
                months = await response.json()

                # Portuguese month name to number mapping
                portuguese_months = {
                    'janeiro': 1, 'fevereiro': 2, 'março': 3, 'abril': 4,
                    'maio': 5, 'junho': 6, 'julho': 7, 'agosto': 8,
                    'setembro': 9, 'outubro': 10, 'novembro': 11, 'dezembro': 12
                }

                date_to_code = {}
                for month in months:
                    month_text = month.get('Mes', '').lower().strip()
                    code = month.get('Codigo')

                    parts = month_text.split('/')
                    if len(parts) == 2:
                        month_name = parts[0].strip()
                        year_str = parts[1].strip()
                        month_num = portuguese_months.get(month_name, 1)
                        try:
                            year = int(year_str)
                            date_to_code[date(year, month_num, 1)] = code
                        except ValueError:
                            pass

                return date_to_code
            else:
                print(f"Error fetching reference months: HTTP {response.status}")
                return {}
    except Exception as e:
        print(f"Error fetching reference months: {e}")
        return {}


async def check_price_exists(
    session: aiohttp.ClientSession,
    month_code: int,
    brand_code: str,
    model_code: str,
    year_code: str,
    max_retries: int = 3
) -> bool:
    """
    Check if a price exists on the FIPE API for a specific configuration.

    Args:
        session: aiohttp session
        month_code: Reference month code from API
        brand_code: Brand code
        model_code: Model code
        year_code: Year code (e.g., "2020-1" for 2020 gasoline)

    Returns:
        True if price data exists, False otherwise
    """
    url = f"{API_BASE_URL}/ConsultarValorComTodosParametros"

    # Parse year_code into year and fuel type
    # Format is typically "2020-1" where 1=gasoline, 2=alcohol, 3=diesel
    parts = year_code.split('-')
    if len(parts) == 2:
        year = parts[0]
        fuel_code = parts[1]
    else:
        year = year_code
        fuel_code = '1'  # Default to gasoline

    data = {
        'codigoTabelaReferencia': month_code,
        'codigoTipoVeiculo': VEHICLE_TYPE_CAR,
        'codigoMarca': brand_code,
        'codigoModelo': model_code,
        'anoModelo': year,
        'codigoTipoCombustivel': fuel_code,
        'tipoConsulta': 'tradicional'
    }

    for attempt in range(max_retries):
        try:
            await asyncio.sleep(API_REQUEST_DELAY)

            async with session.post(url, data=data, headers=API_HEADERS) as response:
                if response.status == 200:
                    result = await response.json()
                    # If we get valid data (has 'Valor' field), price exists
                    # If we get an error response, it typically has 'erro' field
                    if isinstance(result, dict) and 'Valor' in result:
                        return True
                    return False
                elif response.status in (429, 520):
                    # Rate limited or server overload - retry
                    wait_time = 2.0 * (2 ** attempt)
                    print(f"  API returned {response.status}, retrying in {wait_time:.1f}s...")
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    return False

        except Exception as e:
            if attempt < max_retries - 1:
                await asyncio.sleep(2.0)
                continue
            return False

    return False


async def verify_gaps(brands: List[BrandCoverage]) -> int:
    """
    Verify all detected gaps against the FIPE API.

    Removes gaps from missing_months if the API confirms no data exists.

    Args:
        brands: List of BrandCoverage objects with detected gaps

    Returns:
        Total number of gaps that were filtered out (data doesn't exist on FIPE)
    """
    # Count total gaps to verify
    total_gaps = sum(
        len(my.missing_months)
        for b in brands
        for m in b.models
        for my in m.model_years
        if my.missing_months
    )

    if total_gaps == 0:
        print("No gaps to verify.")
        return 0

    print(f"Verifying {total_gaps:,} gap(s) against FIPE API...")
    print("This may take a while. Press Ctrl+C to cancel.\n")

    total_filtered = 0
    verified = 0

    async with aiohttp.ClientSession() as session:
        # First, fetch reference months to map dates to codes
        print("Fetching reference months from API...")
        date_to_code = await fetch_reference_months(session)

        if not date_to_code:
            print("ERROR: Could not fetch reference months. Skipping verification.")
            return 0

        print(f"Found {len(date_to_code)} reference months in API.\n")

        # Iterate through all model years with gaps
        for brand in brands:
            for model in brand.models:
                for my in model.model_years:
                    if not my.missing_months:
                        continue

                    verified_missing = []
                    filtered_this_year = 0

                    for gap_date in my.missing_months:
                        verified += 1

                        # Get month code from date
                        month_code = date_to_code.get(gap_date)
                        if month_code is None:
                            # Date not in reference months = not a real gap
                            filtered_this_year += 1
                            continue

                        # Check if price exists on API
                        exists = await check_price_exists(
                            session,
                            month_code,
                            my.brand_code,
                            my.model_code,
                            my.year_code
                        )

                        if exists:
                            # True gap - data exists but we don't have it
                            verified_missing.append(gap_date)
                        else:
                            # Not a real gap - data doesn't exist on FIPE
                            filtered_this_year += 1

                        # Progress update
                        if verified % 10 == 0:
                            print(f"  Progress: {verified}/{total_gaps} verified, "
                                  f"{total_filtered + filtered_this_year} filtered")

                    # Update missing months to only include verified gaps
                    my.missing_months = verified_missing
                    my.filtered_count = filtered_this_year
                    total_filtered += filtered_this_year

    print(f"\nVerification complete:")
    print(f"  Total gaps checked: {total_gaps:,}")
    print(f"  Filtered out (no data on FIPE): {total_filtered:,}")
    print(f"  Verified true gaps: {total_gaps - total_filtered:,}")

    return total_filtered


def generate_html_report(brands: List[BrandCoverage], output_path: str, verified: bool = False, filtered_count: int = 0) -> None:
    """Generate the HTML coverage report."""

    # Calculate summary stats
    total_brands = len(brands)
    total_models = sum(len(b.models) for b in brands)
    total_model_years = sum(len(m.model_years) for b in brands for m in b.models)
    ok_brands = sum(1 for b in brands if b.is_ok)
    ok_models = sum(1 for b in brands for m in b.models if m.is_ok)
    ok_model_years = sum(1 for b in brands for m in b.models for my in m.model_years if my.is_ok)

    # Verification badge HTML
    if verified:
        verification_badge = """
        <div class='verification-badge'>
            <span class='badge verified'>&#x2713; Verified</span>
            <span class='badge-info'>Gaps verified against FIPE API</span>
        </div>
        """
        if filtered_count > 0:
            verification_badge += f"""
        <div class='filtered-info'>
            <strong>{filtered_count:,}</strong> potential gap(s) filtered out (data doesn't exist on FIPE)
        </div>
            """
    else:
        verification_badge = """
        <div class='verification-badge'>
            <span class='badge unverified'>Unverified</span>
            <span class='badge-info'>Run with --verify to check gaps against FIPE API</span>
        </div>
        """

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
        verification_badge,
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
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description="Generate FIPE data coverage report"
    )
    parser.add_argument(
        '--verify',
        action='store_true',
        help='Verify gaps against FIPE API (slower, but filters out false positives)'
    )
    args = parser.parse_args()

    print("FIPE Data Coverage Report Generator")
    print("=" * 40)
    if args.verify:
        print("Mode: VERIFIED (will query FIPE API)")
    else:
        print("Mode: FAST (no API verification)")

    engine = get_database_connection()

    print("\nFetching price data...")
    df = fetch_price_data(engine)
    print(f"Data spans {df['month_date'].nunique()} unique months")
    print(f"Covering {df['brand_id'].nunique()} brands")

    print("\nAnalyzing coverage gaps...")
    brands = analyze_coverage(df)

    # Print initial summary
    total_model_years = sum(len(m.model_years) for b in brands for m in b.models)
    initial_gaps = sum(1 for b in brands for m in b.models for my in m.model_years if not my.is_ok)
    print(f"Analyzed {total_model_years:,} model years")
    print(f"  OK: {total_model_years - initial_gaps:,}")
    print(f"  With potential gaps: {initial_gaps:,}")

    # Optionally verify gaps against FIPE API
    filtered_count = 0
    if args.verify:
        print("\n" + "=" * 40)
        filtered_count = asyncio.run(verify_gaps(brands))

        # Print updated summary after verification
        ok_model_years = sum(1 for b in brands for m in b.models for my in m.model_years if my.is_ok)
        print(f"\nAfter verification:")
        print(f"  OK: {ok_model_years:,}")
        print(f"  With true gaps: {total_model_years - ok_model_years:,}")

    # Generate HTML report
    output_filename = f"coverage_report_{datetime.now().strftime('%Y-%m-%d')}.html"
    generate_html_report(brands, output_filename, verified=args.verify, filtered_count=filtered_count)
