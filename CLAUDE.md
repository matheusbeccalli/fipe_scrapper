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

**proxy_manager.py** (proxy rotation for rate limit avoidance)
- `ProxyPool` class: Loads and manages proxy list (used for loading proxies from file)
- `ProxyWorker` class: A worker that owns a dedicated proxy + persistent aiohttp session
  - Each worker pulls work from a shared queue and executes requests
  - Handles SOCKS vs HTTP proxy differences automatically
  - Includes retry logic with exponential backoff
  - Injects Cloudflare bypass cookies into requests
  - **Auto-disable**: Tracks consecutive 403/503 failures, disables worker after threshold (default: 5)
  - **Work requeue**: When disabled, requeues current work item so another worker can retry
- `ProxyWorkerPool` class: Manages a pool of ProxyWorkers for parallel requests
  - Creates one worker per proxy (e.g., 250 proxies = 250 concurrent workers)
  - Work items distributed via asyncio.Queue for natural load balancing
  - Fast proxies handle more requests, slow proxies don't block others
  - `submit(endpoint, data)`: Submit request to be processed by next available worker
  - `get_stats()`: Returns worker count, active/disabled workers, completed/failed requests
  - **Auto-removal**: Removes blocked proxies from `proxies.txt` automatically
- `WorkItem` dataclass: Encapsulates a single API request (endpoint, data, headers, cookies, result future)

**cloudflare_bypass.py** (Cloudflare protection bypass)
- `CloudflareBypass` class: Manages Cloudflare bypass sessions using cloudscraper25
  - Obtains clearance cookies by solving Cloudflare JavaScript challenges
  - Maintains multiple sessions for redundancy (round-robin)
  - Auto-refreshes sessions every 4 minutes (before 5-minute expiry)
  - Runs in background thread to not block async code
- `CloudflareSession` dataclass: Holds cookies, user-agent, and metadata
- Integrated with ProxyWorkerPool to inject cookies into all requests

### Utility Scripts (scripts/ folder)

**scripts/benchmark_proxies.py** (proxy performance testing)
- Tests all proxies in parallel to measure latency
- Automatically removes failed proxies from `proxies.txt`
- Compares proxy speed vs direct connection
- Run with: `python scripts/benchmark_proxies.py`

**scripts/test_cloudflare_bypass.py** (Cloudflare bypass testing)
- Tests direct connection, cloudscraper, and proxy combinations
- Verifies Cloudflare bypass cookies work with aiohttp
- Run with: `python scripts/test_cloudflare_bypass.py`

**scripts/benchmark_scraper.py** (scraper version comparison)
- Compares performance between scraper versions
- Run with: `python scripts/benchmark_scraper.py`

**scripts/debug_proxy_request.py** (proxy debugging)
- Debug tool to compare proxy vs direct request headers
- Run with: `python scripts/debug_proxy_request.py`

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
- Skip logic operates at the **model level**: brands are always processed (model list fetched), but individual models already in the checkpoint are skipped instantly
- This enables gap-filling: if a brand has partial data, only the missing models are scraped

**Rate Limiting & Performance**
- **Worker Pool Architecture**: Each proxy gets its own worker with persistent session
- Concurrency scales automatically with proxy count (250 proxies = 250 concurrent requests)
- Automatic retry with exponential backoff on 429 (rate limit) and 520 (server overload) errors
- Batch database commits (100 records per commit) for optimal performance
- Smart skip: automatically skips already-scraped models via checkpoint system
- Falls back to direct (non-proxy) requests if worker pool unavailable

**Cloudflare Bypass**
- Uses `cloudscraper25` to solve Cloudflare JavaScript challenges
- Obtains clearance cookies that are injected into all proxy requests
- Sessions auto-refresh every 4 minutes in the background
- Handles 403 (blocked) and 503 (challenge page) responses
- Falls back gracefully if cloudscraper25 is not installed

## Configuration Notes

All settings are in `config.py`:
- **DATABASE_URL**: SQLite by default, can use PostgreSQL/MySQL
- **LOG_CONFIG**: Logging level, file location, and rotation settings
- **DATE_RANGE**: Optional date filtering for scraping specific time periods
- **BRAND_FILTER**: Optional brand filtering for targeted scraping
- **RESUME_CONFIG**: Checkpoint system configuration
- **PROXY_CONFIG**: Proxy rotation settings (enabled, file path, failure threshold)

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
- The scraper uses a checkpoint system (`scraping_checkpoint.json`) to skip already-scraped models at the individual model level
- Brands are always processed (model list fetched), but models already in the checkpoint are skipped instantly
- This allows the scraper to detect and fill gaps at the model level within any brand
- Example workflow:
  1. First run: `BRAND_FILTER_CODES=6,59` (scrape Audi and Volkswagen for Jan-Dec 2024)
  2. Second run: Same brands — only models missing from checkpoint are re-scraped

**Use Cases**:
- Prioritize specific brands: Scrape your most important brands first, then fill in the rest later
- Testing: Scrape a single brand to test your setup before running a full scrape
- Incremental updates: Add new brands to your dataset without re-scraping existing ones

### Proxy Rotation
The scraper supports proxy rotation to avoid rate limiting (429 errors) when scraping from a single IP. **Note: You must provide your own proxy list - the `proxies.txt` file is not included in the repository.**

**Setup:**
1. Create a `proxies.txt` file in the project root
2. Add one proxy per line in the format:
   ```
   ip:port                              # HTTP proxy (no auth)
   username:password@ip:port            # HTTP proxy with auth
   http://ip:port                       # HTTP proxy (explicit)
   http://username:password@ip:port     # HTTP proxy with auth (explicit)
   socks4://ip:port                     # SOCKS4 proxy
   socks5://ip:port                     # SOCKS5 proxy
   socks5://username:password@ip:port   # SOCKS5 proxy with auth
   ```
3. Configure in `.env`:
   ```bash
   PROXY_ENABLED=true
   PROXY_FILE=proxies.txt
   PROXY_MAX_FAILURES=5
   ```

**Features:**
- **Worker Pool**: Each proxy gets a dedicated worker with persistent session (connection reuse)
- **True parallelism**: All proxies work simultaneously (e.g., 250 proxies = 250 concurrent requests)
- **Natural load balancing**: Fast proxies handle more requests, slow proxies don't block others
- **Auto-disable**: Workers disabled after consecutive 403/503 failures (default: 5)
- **Auto-removal**: Blocked proxies automatically removed from `proxies.txt`
- **Work requeue**: In-flight requests requeued when worker disabled (not lost)
- User-Agent rotation: 50+ realistic browser strings
- SOCKS support: HTTP, SOCKS4, and SOCKS5 proxies via `aiohttp-socks`
- Graceful fallback: Falls back to direct connection when worker pool unavailable

**Performance Tip:** Run `python scripts/benchmark_proxies.py` to test your proxies and automatically remove dead ones.

**To disable proxy rotation:**
- Set `PROXY_ENABLED=false` in `.env`, or
- Don't create a `proxies.txt` file (scraper will use direct connections)

## Common Issues

**Rate Limiting (429 errors)**: If you see frequent 429 errors:
- Workers automatically retry with exponential backoff
- Consider using more proxies to distribute load
- Run `python scripts/benchmark_proxies.py` to remove slow/dead proxies

**Cloudflare Blocking (403 errors)**: If proxies are blocked by Cloudflare:
- Workers auto-disable after 5 consecutive 403/503 errors (configurable via `PROXY_MAX_FAILURES`)
- Blocked proxies are automatically removed from `proxies.txt`
- In-flight requests are requeued to other workers (not lost)
- Run `python scripts/test_cloudflare_bypass.py` to test bypass functionality
- Ensure `cloudscraper25` is installed: `pip install cloudscraper25`
- The bypass automatically obtains and injects clearance cookies
- Some proxy IPs may be permanently blocked by Cloudflare

**Server Overload (520 errors)**: If you see 520 errors:
- The FIPE API server is temporarily overloaded
- Workers automatically retry with backoff
- This is normal during heavy load periods

**Slow Proxies**: If scraping is slow despite many proxies:
- Run `python scripts/benchmark_proxies.py` to identify and remove slow proxies
- The worker pool naturally handles this (fast proxies do more work)
- Consider using paid proxies for better reliability

**API Changes**: If scraping fails with unexpected errors:
- The FIPE API structure may have changed
- Check API endpoints in `fipe_api_scraper.py:43-55`
- Verify request/response formats in the `_make_request()` method

**Performance**: Full scrape (all 298 months, all brands):
- With 250 proxies: significantly faster due to parallel requests
- Without proxies: Falls back to direct connection (slower, may hit rate limits)
- Use date/brand filtering for faster targeted scrapes
