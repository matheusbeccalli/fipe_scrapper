# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Python web scraper for collecting historical car price data from the FIPE (Fundação Instituto de Pesquisas Econômicas) website, Brazil's vehicle price reference. The scraper uses Selenium to navigate the JavaScript-heavy FIPE website, extracts price data for all car brands/models/years across all available months (from January 2001 to present), and stores the data in a relational database.

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
# Run the main scraper (takes hours/days for full scrape)
python fipe_scraper.py
```

### Data Export and Analysis
```bash
# Show database statistics
python utils.py

# Export all data to CSV
python utils.py export

# Run example queries and analysis
python example_usage.py
```

## Architecture

### Data Flow
The scraper follows a nested loop pattern to exhaustively collect all data:
1. **Months** → 2. **Brands** → 3. **Models** → 4. **Model Years** → 5. **Price Data**

Each level depends on the previous selection in the web interface.

### Database Schema (5 tables, fully normalized)
- **reference_months**: Time periods for which data is available (e.g., "dezembro/2024")
- **brands**: Car manufacturers (Volkswagen, Fiat, etc.)
- **car_models**: Specific car models within each brand (linked to brands via brand_id)
- **model_years**: Year/fuel type combinations for each model (linked to car_models via car_model_id)
- **car_prices**: The actual price records (links reference_months and model_years)

The schema uses foreign keys and unique constraints to prevent duplicates and maintain referential integrity.

### Core Components

**fipe_scraper.py** (main scraper logic)
- `FIPEScraper` class: Main scraper orchestrating the entire workflow
- `_setup_browser()`: Configures Chrome with Selenium WebDriver
- `_get_dropdown_options()`: Extracts options from Chosen jQuery dropdown plugin
- `_select_dropdown_option()`: Selects specific dropdown values
- `scrape_all_data()`: Main entry point that loops through all combinations
- `_extract_price_data()`: Scrapes price information from result page
- Database save methods: `_save_reference_month()`, `_save_brand()`, `_save_car_model()`, `_save_model_year()`, `_save_price()`

**database_models.py** (SQLAlchemy ORM models)
- Defines all 5 database tables using declarative_base
- `create_database()`: Factory function that creates tables and returns engine/Session

**config.py** (centralized configuration)
- All configurable settings including element IDs, delays, database URL, logging
- Modify this file rather than hardcoding values in the scraper

**utils.py** (data export utilities)
- `FIPEDataExporter` class: Helper for exporting and analyzing scraped data
- Methods for CSV export, price history queries, statistics

**example_usage.py** (demonstrates data queries)
- Examples of using the data with pandas and SQLAlchemy

### Important Technical Details

**Selenium Element Interaction**
The FIPE website uses the Chosen jQuery plugin for dropdowns, which creates custom HTML instead of standard `<select>` elements. The scraper must:
1. Click the dropdown to open it (`{select_id}_chosen`)
2. Find `<li>` elements with `data-option-array-index` attributes
3. Click the specific option by its index

**Checkpoint/Resume System**
- Progress is saved to `scraping_checkpoint.json` after each brand is completed
- Format: `{month_value}_{brand_value}: true`
- Can be disabled in `config.py` via `RESUME_CONFIG['enable_resume']`

**Ethical Scraping Considerations**
- Default 2-second delay between requests (`SCRAPING_CONFIG['delay_between_requests']`)
- Headless browser mode to reduce resource usage
- Resume capability to avoid re-scraping on interruptions
- FIPE provides no API, requires model-by-model scraping per their terms

## Configuration Notes

All settings are in `config.py`:
- **ELEMENT_IDS**: CSS selectors for FIPE website elements (may break if website changes)
- **SELENIUM_CONFIG**: Browser behavior (set `headless: False` to see browser during debugging)
- **SCRAPING_CONFIG**: Delays and retry logic
- **DATABASE_URL**: SQLite by default, can use PostgreSQL/MySQL

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
- See [BRAND_CODES.md](BRAND_CODES.md) for complete list of all 98 available brands
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

**Website Structure Changes**: If scraping fails with `NoSuchElementException`, the FIPE website structure may have changed. Check:
- Element IDs in `config.py`
- CSS selectors in `_get_dropdown_options()` and `_extract_price_data()`

**Performance**: Full scrape takes days due to:
- Thousands of brand/model/year combinations
- 250+ months of historical data
- Mandatory delays between requests
