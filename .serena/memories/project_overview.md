# FIPE Scrapper - Project Overview

## Purpose
A Python web scraper for collecting historical car price data from the FIPE (Fundação Instituto de Pesquisas Econômicas) website, Brazil's official vehicle price reference. The scraper uses async HTTP requests to the FIPE REST API to extract price data for all car brands/models/years across all available months (from January 2001 to present).

## Tech Stack
- **Python 3.x** - Main language
- **SQLAlchemy 2.0+** - ORM and database management
- **aiohttp** - Async HTTP client for concurrent API requests
- **pandas** - Data processing and analysis
- **loguru** - Logging with rotation support
- **python-dotenv** - Environment variable management

## Database
- Default: SQLite (`fipe_data.db`)
- Supports PostgreSQL/MySQL via `DATABASE_URL` env var
- 5 normalized tables: reference_months, brands, car_models, model_years, car_prices

## Architecture
The scraper follows a nested loop pattern:
1. **Months** → 2. **Brands** → 3. **Models** → 4. **Model Years** → 5. **Price Data**

### Core Components
- `fipe_api_scraper.py` - Main scraper with `FIPEAPIScraper` class
- `database_models.py` - SQLAlchemy ORM models
- `config.py` - Centralized configuration
- `utils.py` - Data export utilities (`FIPEDataExporter` class)
- `coverage_report.py` - Generates HTML coverage reports

### Key Features
- Checkpoint/resume system (`scraping_checkpoint.json`)
- Adaptive rate limiting (starts at 500ms, adjusts based on errors)
- Batch database commits (100 records per commit)
- Smart skip for already-scraped data
