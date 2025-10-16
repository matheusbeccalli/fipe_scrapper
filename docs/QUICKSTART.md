# Quick Start Guide - FIPE Scraper

Get up and running in 5 minutes!

## Step 1: Setup

```bash
# Create and activate virtual environment
python -m venv venv

# Windows:
venv\Scripts\activate

# macOS/Linux:
source venv/bin/activate

# Upgrade pip (recommended)
python -m pip install --upgrade pip

# Install dependencies
pip install -r requirements.txt
```

**Note:** This scraper uses direct API calls (no browser required). Installation is fast and lightweight.

## Step 2: Create Database

```bash
python database_models.py
```

You should see: "Database created successfully!"

## Step 3: Configure Scraping Options (Optional)

To test or customize scraping, create a `.env` file:

```bash
# Copy example config
cp .env.example .env

# Edit .env and configure:

# Date range (optional - leave blank for all months 2001-present)
SCRAPE_START_DATE=2024-01
SCRAPE_END_DATE=2024-12

# Brand filtering (NEW! - leave disabled to scrape all brands)
BRAND_FILTER_ENABLED=true
BRAND_FILTER_CODES=6,59  # Audi and Volkswagen - see docs/BRAND_CODES.md for full list
```

**Brand Codes**: See [BRAND_CODES.md](BRAND_CODES.md) for the complete list of 98 available brands.

## Step 4: Run Scraper

```bash
# Run the API-based scraper (recommended - fast!)
python fipe_api_scraper.py
```

**Performance**: API-based scraping is 50-100x faster than browser-based approaches. The scraper will:
- Loop through ALL months (2001-present, or your configured range)
- Loop through ALL brands (50+)
- Loop through ALL models (thousands)
- Loop through ALL years
- Use adaptive rate limiting to avoid API throttling

If interrupted, just restart - it resumes automatically!

## Step 5: Check Progress

While scraping (or after):

```bash
# See database statistics
python utils.py

# Export data to CSV
python utils.py export
```

## Step 6: Analyze Data

```bash
# Run example queries
python docs/example_usage.py
```

## Common Issues

**Installation errors with pandas/numpy?**
- Upgrade pip: `python -m pip install --upgrade pip`
- The requirements.txt now uses `>=` to allow newer compatible versions
- Python 3.13+ users: pre-built wheels install automatically

**Getting rate limited (429 errors)?**
- The scraper uses adaptive rate limiting automatically
- Start with a small date range to test (e.g., one month)
- Check logs in `fipe_scraper.log` for patterns

**Still too slow?**
- Already using the fastest method (direct API calls)
- Limit date range in `.env` to scrape only recent months
- Use brand filtering to scrape priority brands first (see [docs/BRAND_CODES.md](../BRAND_CODES.md))
- Full historical scrape (250+ months, all brands) will take time even with API

**Need to stop?**
- Press `Ctrl+C`
- Progress is saved automatically
- Restart anytime - it continues where it left off

## File Overview

| File | Purpose |
|------|---------|
| `fipe_api_scraper.py` | **Main scraper - START HERE** (uses direct API calls) |
| `config.py` | All settings |
| `database_models.py` | Database structure |
| `utils.py` | Export & analyze data |
| `fipe_data.db` | Your database (created automatically) |
| `.env` | Optional configuration (copy from `.env.example`) |
| `docs/` | **Documentation and examples** |
| `docs/example_usage.py` | Code examples |
| `docs/BRAND_CODES.md` | Complete list of brand codes for filtering |
| `docs/QUICKSTART.md` | This guide |
| `docs/API_DOCUMENTATION.md` | API reference |

## What's Being Scraped?

For each combination of:
- Month (janeiro/2001 → presente)
- Brand (Volkswagen, Fiat, Chevrolet, etc.)
- Model (Gol, Uno, Onix, etc.)
- Year (2020 Gasolina, 2021 Flex, etc.)

The scraper saves:
- Price in BRL (Brazilian Real)
- FIPE code
- All metadata

## Next Steps

1. ✅ Run initial test
2. ✅ Let scraper run overnight
3. ✅ Export data to CSV
4. ✅ Analyze with pandas
5. 🎯 Create visualizations
6. 🎯 Build price alert system
7. 🎯 Create API for the data

## Need Help?

- Check `README.md` for detailed docs
- View logs in `fipe_scraper.log`
- Ask Claude for help with specific tasks!

## Working with Claude

Tell Claude what you want to do:
- "Fix this error in fipe_api_scraper.py"
- "Add a function to export only 2024 data"
- "Create a chart showing price trends"
- "Optimize the rate limiting strategy"
- "Add email notifications when scraping completes"

Claude can help you extend and customize the scraper!

---

**Remember**:
- API-based scraper is already optimized for speed
- Progress auto-saves automatically
- Start with a small date range to test
- Check logs frequently (`fipe_scraper.log`)
- Full historical scrape = hours (not days like browser-based)
