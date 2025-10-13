# Quick Start Guide - FIPE Scraper

Get up and running in 5 minutes! 🚀

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

**Note:** If you're using Python 3.13+, the installation will automatically use the latest compatible versions with pre-built wheels. No C compiler needed!

## Step 2: Create Database

```bash
python database_models.py
```

You should see: "Database created successfully!"

## Step 3: Test Run (Optional)

Before running a full scrape, test with a small sample:

Edit `config.py` and change:
```python
SELENIUM_CONFIG = {
    'headless': False,  # See the browser
}
```

## Step 4: Run Scraper

```bash
python fipe_scraper.py
```

**Warning**: Full scrape takes MANY hours! The scraper will:
- Loop through ALL months (2001-present)
- Loop through ALL brands (50+)
- Loop through ALL models (thousands)
- Loop through ALL years

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
python example_usage.py
```

## Common Issues

**Installation errors with pandas/numpy?**
- Upgrade pip: `python -m pip install --upgrade pip`
- The requirements.txt now uses `>=` to allow newer compatible versions
- Python 3.13+ users: pre-built wheels install automatically

**Browser not opening?**
- Make sure Chrome is installed
- Try `headless: False` to see what's happening

**Taking too long?**
- This is normal! Full scrape = days
- Start with recent months only
- Check logs in `fipe_scraper.log`

**Need to stop?**
- Press `Ctrl+C`
- Progress is saved automatically
- Restart anytime - it continues where it left off

## File Overview

| File | Purpose |
|------|---------|
| `fipe_scraper.py` | Main scraper (START HERE) |
| `config.py` | All settings |
| `database_models.py` | Database structure |
| `utils.py` | Export & analyze data |
| `example_usage.py` | Code examples |
| `fipe_data.db` | Your database (created automatically) |

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
- "Fix this error in fipe_scraper.py"
- "Add a function to export only 2024 data"
- "Create a chart showing price trends"
- "Make the scraper faster"
- "Add email notifications when scraping completes"

Claude can help you extend and customize the scraper!

---

**Remember**: 
- Be patient (full scrape = very slow)
- Progress auto-saves
- Start small, scale up
- Check logs frequently
