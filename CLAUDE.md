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

## Common Issues

**Website Structure Changes**: If scraping fails with `NoSuchElementException`, the FIPE website structure may have changed. Check:
- Element IDs in `config.py`
- CSS selectors in `_get_dropdown_options()` and `_extract_price_data()`

**Performance**: Full scrape takes days due to:
- Thousands of brand/model/year combinations
- 250+ months of historical data
- Mandatory delays between requests
