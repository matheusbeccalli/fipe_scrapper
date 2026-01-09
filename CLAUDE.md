# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Python web scraper for collecting historical car price data from the FIPE (Fundação Instituto de Pesquisas Econômicas) website, Brazil's vehicle price reference. The scraper uses direct HTTP requests to the FIPE REST API to extract price data for all car brands/models/years across all available months (from January 2001 to present), and stores the data in a relational database.

**Performance**: Uses async/await for concurrent requests with minimal memory footprint (~50MB). Full scrape of all available data takes approximately 24-48 hours with default conservative settings.

## Key Commands

### Environment Setup
```bash
# Create and activate virtual environment (Windows)
python -m venv venv
venv\Scripts\activate

# Create and activate virtual environment (macOS/Linux)
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment variables (optional)
cp .env.example .env
# Edit .env with your database credentials if not using SQLite

# Create database schema
python database_models.py
```

### Running the Scraper
```bash
# Run the main scraper
python fipe_api_scraper.py

# Monitor scraping progress in real-time
tail -f fipe_scraper.log
```

### Data Export and Analysis
```bash
# Show database statistics
python utils.py

# Export all data to CSV
python utils.py export

# Run example queries and analysis
python docs/example_usage.py
```

### Data Coverage Analysis
```bash
# Generate data coverage report (finds gaps in price data)
python coverage_report.py
# Output: coverage_report_YYYY-MM-DD.html
```

## Architecture

### Data Flow
The scraper follows a nested loop pattern to exhaustively collect all data:
1. **Months** → 2. **Brands** → 3. **Models** → 4. **Model Years** → 5. **Price Data**

Each level depends on the previous selection in the API request parameters (e.g., to get models, you must specify month + brand).

### Database Schema (5 tables, fully normalized)
- **reference_months**: Time periods for which data is available (e.g., "dezembro/2024")
- **brands**: Car manufacturers (Volkswagen, Fiat, etc.)
- **car_models**: Specific car models within each brand (linked to brands via brand_id)
- **model_years**: Year/fuel type combinations for each model (linked to car_models via car_model_id)
- **car_prices**: The actual price records (links reference_months and model_years)

The schema uses foreign keys and unique constraints to prevent duplicates and maintain referential integrity.

### Core Components

**fipe_api_scraper.py** (main scraper logic)
- `FIPEAPIScraper` class: High-performance scraper using async HTTP requests
- `_make_request()`: Makes API requests with retry logic and adaptive rate limiting
- `get_reference_months()`: Fetches all available time periods
- `get_brands()`: Fetches all car manufacturers for a specific month
- `get_models()`: Fetches all models for a brand
- `get_model_years()`: Fetches year/fuel combinations for a model
- `get_price()`: Fetches price data for a specific configuration
- `scrape_all_data()`: Main entry point with concurrent scraping
- `_flush_database_batch()`: Bulk database saves for performance
- `_brand_has_data_for_month()`: Smart skip logic to avoid re-scraping existing data

**database_models.py** (SQLAlchemy ORM models)
- Defines all 5 database tables using declarative_base
- `create_database()`: Factory function that creates tables and returns engine/Session

**config.py** (centralized configuration)
- All configurable settings including database URL, logging, date/brand filters
- Modify this file rather than hardcoding values in the scraper

**utils.py** (data export utilities)
- `FIPEDataExporter` class: Helper for exporting and analyzing scraped data
- Methods for CSV export, price history queries, statistics

**docs/example_usage.py** (demonstrates data queries)
- Examples of using the data with pandas and SQLAlchemy

### Important Technical Details

**API Endpoints**
The scraper uses the official FIPE REST API at `http://veiculos.fipe.org.br/api/veiculos`:
- `/ConsultarTabelaDeReferencia`: Get available months
- `/ConsultarMarcas`: Get brands for a month
- `/ConsultarModelos`: Get models for a brand
- `/ConsultarAnoModelo`: Get year/fuel combinations for a model
- `/ConsultarValorComTodosParametros`: Get price data

**Checkpoint/Resume System**
- Progress is saved to `scraping_checkpoint.json` after each model is completed
- Format: `{month_code}_{brand_code}_{model_code}: true`
- Can be disabled in `config.py` via `RESUME_CONFIG['enable_resume']`
- Allows resuming after interruptions without re-scraping completed data

**Rate Limiting & Performance**
- Adaptive rate limiting (starts at 500ms, adjusts based on errors)
- Concurrent requests controlled by semaphore (default: 1 concurrent request)
- Automatic retry with exponential backoff on 429 (rate limit) and 520 (server overload) errors
- Batch database commits (100 records per commit) for optimal performance
- Smart skip: automatically skips brands that already have data for specified months

## Configuration Notes

All settings are in `config.py`:
- **DATABASE_URL**: SQLite by default, can use PostgreSQL/MySQL
- **LOG_CONFIG**: Logging level, file location, and rotation settings
- **DATE_RANGE**: Optional date filtering for scraping specific time periods
- **BRAND_FILTER**: Optional brand filtering for targeted scraping
- **RESUME_CONFIG**: Checkpoint system configuration

### Environment Variables
Configuration can be customized using environment variables (recommended for sensitive data):
- Create a `.env` file from `.env.example`: `cp .env.example .env`
- Configure database: `DATABASE_URL=postgresql://user:pass@localhost/fipe_db`
- Configure logging: `LOG_LEVEL=DEBUG`, `LOG_FILE=custom.log`
- Configure date range: `SCRAPE_START_DATE=2024-01`, `SCRAPE_END_DATE=2024-12`
- The `.env` file is ignored by git and will never be committed

### Date Range Filtering
By default, the scraper processes ALL available months (250+ months from 2001-present). To limit scraping to specific months:
- Set `SCRAPE_START_DATE` and `SCRAPE_END_DATE` in `.env` or `config.py`
- Format: `YYYY-MM` (e.g., `2024-01` for January 2024)
- Both dates are inclusive
- Useful for testing (scrape one month) or incremental updates (scrape recent months only)
- Set to `None` or comment out to scrape all available months

### Brand Filtering
By default, the scraper processes ALL available brands. To limit scraping to specific brands:
- Set `BRAND_FILTER_ENABLED=true` in `.env` or `config.py`
- Set `BRAND_FILTER_CODES` to comma-separated brand codes (e.g., `6,59` for Audi and Volkswagen)
- Brand codes are the same values used by the FIPE API (stored in `brands.brand_code` in database)
- See [docs/BRAND_CODES.md](docs/BRAND_CODES.md) for complete list of all 103 available brands (as of October 2025)
- Or query your database: `SELECT brand_code, brand_name FROM brands;`

**Smart Skip Behavior**:
- If a brand already has complete data for the specified date range, it will be automatically skipped
- This allows you to run the scraper with different brand selections without re-scraping existing data
- Example workflow:
  1. First run: `BRAND_FILTER_CODES=6,59` (scrape Audi and Volkswagen for Jan-Dec 2024)
  2. Second run: Remove filter or specify all brands (scraper will skip Audi/Volkswagen, scrape everything else)

**Use Cases**:
- Prioritize specific brands: Scrape your most important brands first, then fill in the rest later
- Testing: Scrape a single brand to test your setup before running a full scrape
- Incremental updates: Add new brands to your dataset without re-scraping existing ones

## Common Issues

**Rate Limiting (429 errors)**: If you see frequent 429 errors:
- The adaptive rate limiting will automatically slow down
- Consider reducing `max_concurrent_requests` in `fipe_api_scraper.py:869` (default is 1)
- Increase `request_delay` in the scraper initialization

**Server Overload (520 errors)**: If you see 520 errors:
- The FIPE API server is temporarily overloaded
- The scraper will automatically retry with exponential backoff
- Adaptive delay will increase to reduce server load

**API Changes**: If scraping fails with unexpected errors:
- The FIPE API structure may have changed
- Check API endpoints in `fipe_api_scraper.py:43-55`
- Verify request/response formats in the `_make_request()` method

**Performance**: Full scrape (all 298 months, all brands):
- Approximately 24-48 hours with default settings (1 concurrent request)
- Can be sped up by increasing concurrency, but risks rate limiting
- Use date/brand filtering for faster targeted scrapes
