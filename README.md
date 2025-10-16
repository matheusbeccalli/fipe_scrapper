# FIPE Car Price Web Scraper

A Python web scraper that collects historical car price data from the FIPE (Fundação Instituto de Pesquisas Econômicas) table, Brazil's vehicle price reference.

## 🎉 Ultra-Fast API-Based Scraper

This scraper uses the FIPE REST API directly for **dramatically faster** scraping compared to traditional browser automation.

Please note: the performance is currently limited by the FIPE server (rate limits) but in theory the scraper can be much faster.

## 📋 What This Does

This scraper automatically:
- Makes direct HTTP requests to the FIPE API
- Loops through all available months (from January 2001 to present)
- Extracts data for all car brands, models, and years using concurrent async requests
- Saves the data to a SQLite database (or PostgreSQL/MySQL)
- Handles rate limiting with automatic retry logic
- Resumes if interrupted via checkpoint system
- Logs all activities for monitoring

## 🗂️ Project Structure

```
fipe_scraper/
├── requirements.txt          # Python dependencies
├── config.py                # Configuration settings
├── database_models.py       # Database schema (SQLAlchemy models)
├── fipe_api_scraper.py     # Main API scraper (RECOMMENDED)
├── README.md               # This file
├── .env                    # Environment variables (create this)
├── fipe_data.db           # SQLite database (created automatically)
└── docs/                   # Documentation
    ├── API_DOCUMENTATION.md    # Complete API reference
    ├── BRAND_CODES.md          # Brand codes for filtering
    └── QUICKSTART.md           # Quick start guide
```

## 🚀 Getting Started

### Prerequisites

- Python 3.8 or higher (Python 3.13+ recommended)
- Internet connection
- No browser needed!

### Installation

1. **Create a virtual environment (recommended):**
```bash
# On Windows
python -m venv venv
venv\Scripts\activate

# On macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

2. **Upgrade pip (recommended):**
```bash
python -m pip install --upgrade pip
```

3. **Install dependencies:**
```bash
pip install -r requirements.txt
```

4. **Create the database:**
```bash
python database_models.py
```

You should see output showing the tables being created.

5. **Configure scraping options (optional):**

Create a `.env` file from the example:
```bash
cp .env.example .env
```

Then edit `.env` to configure:

**Date Range Filtering:**
```bash
# Scrape specific date range (faster for testing)
SCRAPE_START_DATE=2024-01
SCRAPE_END_DATE=2024-01

# Scrape everything (leave empty or comment out)
# SCRAPE_START_DATE=
# SCRAPE_END_DATE=
```

**Brand Filtering (NEW!):**
```bash
# Enable brand filtering to scrape only specific brands
BRAND_FILTER_ENABLED=true
BRAND_FILTER_CODES=6,59  # Audi and Volkswagen

# Or scrape all brands (default)
# BRAND_FILTER_ENABLED=false
```

To find brand codes:
- See complete list in **[docs/BRAND_CODES.md](docs/BRAND_CODES.md)** (98 brands)
- Or query your database: `SELECT brand_code, brand_name FROM brands;`

## 🏃‍♂️ Running the Scraper

### Basic Usage

Simply run:
```bash
python fipe_api_scraper.py
```

The scraper will:
- Connect to the FIPE API
- Fetch data concurrently using async/await (3 workers by default)
- Handle rate limiting automatically with retries
- Save everything to `fipe_data.db`
- Create a log file `fipe_scraper.log`

### Configuration

The scraper uses conservative settings optimized for reliability:

```python
# In fipe_api_scraper.py __init__ method
max_concurrent_requests = 3    # Number of parallel requests
request_delay = 0.5            # Seconds between requests
max_retries = 5                # Retry attempts for rate limits
```

You can adjust these in the code if needed:
- **More speed**: Increase `max_concurrent_requests` to 5 (more 429 errors)
- **More reliable**: Keep at 3 or reduce to 2

## 📊 Database Schema

The data is organized in 5 tables:

1. **reference_months**: All available months (e.g., "dezembro/2024")
2. **brands**: Car manufacturers (e.g., "Volkswagen", "Fiat")
3. **car_models**: Car models within each brand (e.g., "Gol 1.0")
4. **model_years**: Years and fuel types (e.g., "2024 Gasolina")
5. **car_prices**: The actual price data (links everything together)

### Example Query

To get all prices for a specific car:

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database_models import CarPrice, ModelYear, CarModel, Brand, ReferenceMonth

engine = create_engine('sqlite:///fipe_data.db')
Session = sessionmaker(bind=engine)
session = Session()

# Get all prices for Volkswagen Gol
results = session.query(
    ReferenceMonth.month_date,
    Brand.brand_name,
    CarModel.model_name,
    ModelYear.year_description,
    CarPrice.price
).join(
    ModelYear, CarPrice.model_year_id == ModelYear.id
).join(
    CarModel, ModelYear.car_model_id == CarModel.id
).join(
    Brand, CarModel.brand_id == Brand.id
).join(
    ReferenceMonth, CarPrice.reference_month_id == ReferenceMonth.id
).filter(
    Brand.brand_name.like('%Volkswagen%'),
    CarModel.model_name.like('%Gol%')
).all()

for month, brand, model, year, price in results:
    print(f"{month}: {brand} {model} {year} - R$ {price:,.2f}")
```

## 🔧 How It Works

### The FIPE API
The scraper uses these endpoints:
1. `POST /ConsultarTabelaDeReferencia` - Get reference months (298 total)
2. `POST /ConsultarMarcas` - Get brands (~100 per month)
3. `POST /ConsultarModelos` - Get models (~50 per brand)
4. `POST /ConsultarAnoModelo` - Get years (~10 per model)
5. `POST /ConsultarValorComTodosParametros` - Get price data

### Key Features
- **Async/Await**: Uses `aiohttp` for concurrent HTTP requests
- **Rate Limiting**: Automatic retry with exponential backoff for HTTP 429 errors
- **Conservative Settings**: 3 concurrent requests, 0.5s delay between requests
- **Checkpoint System**: Saves progress after each model, resume anytime
- **Detailed Statistics**: Shows success rate, request counts, timing

See [docs/API_DOCUMENTATION.md](docs/API_DOCUMENTATION.md) for complete endpoint details.

## ⚠️ Important Notes

### Rate Limiting

The FIPE API implements rate limiting (HTTP 429 errors). The scraper handles this automatically:
- Default: multiple concurrent requests with configurable delay
- Automatic retry with exponential backoff (up to 5 attempts)
- If rate limited, waits 5-10-20 seconds before retry

### Ethical Scraping

- The scraper includes delays to be respectful to the server
- Conservative concurrency settings prevent overwhelming the API
- Consider running during off-peak hours for large scrapes
- Don't run multiple instances simultaneously

## 🔄 Resuming Interrupted Scrapes

If the scraper is interrupted:
1. It automatically saves progress to `scraping_checkpoint.json`
2. When restarted, it will skip already-scraped data
3. You can disable this in `config.py`:

```python
RESUME_CONFIG = {
    'enable_resume': False,  # Disable resume feature
}
```

## 🎯 Brand Filtering (Smart Skip Feature)

The scraper can now filter by specific brands and automatically skip brands that already have complete data:

### How It Works

1. **Enable brand filtering** in `.env`:
```bash
BRAND_FILTER_ENABLED=true
BRAND_FILTER_CODES=6,59  # Audi and Volkswagen
```

2. **Smart skip behavior**: If you later change the filter or remove it entirely, the scraper will automatically skip brands that already have complete data for your specified date range.

### Example Workflow

**Scenario**: You want to prioritize Audi and Volkswagen, then scrape other brands later.

**Step 1** - Scrape priority brands:
```bash
# In .env
SCRAPE_START_DATE=2024-01
SCRAPE_END_DATE=2024-12
BRAND_FILTER_ENABLED=true
BRAND_FILTER_CODES=6,59  # Audi (6) and Volkswagen (59) - see docs/BRAND_CODES.md
```
Run scraper → Gets all Audi and Volkswagen data for 2024

**Step 2** - Scrape remaining brands:
```bash
# In .env
SCRAPE_START_DATE=2024-01
SCRAPE_END_DATE=2024-12
BRAND_FILTER_ENABLED=false  # Or remove the filter
```
Run scraper → Automatically skips Audi and Volkswagen (already complete), scrapes all other brands

### Benefits

- **Prioritize important brands**: Get data for your most important brands first
- **No duplicate scraping**: Smart detection prevents re-scraping existing data
- **Flexible workflow**: Can scrape brands in any order or combination
- **Faster testing**: Test with a single brand before running full scrape

## 🐛 Troubleshooting

### Rate Limiting (HTTP 429)

**Symptom**: Many "Rate limited (429)" warnings in logs

**Solution**:
- Reduce `max_concurrent_requests` to 2 or 1
- Increase `request_delay` to 1.0 second
- The scraper will retry automatically, but may be slower

### Connection Errors

**Error**: `aiohttp.ClientError` or timeout errors

**Solution**:
- Check your internet connection
- Check if FIPE website is accessible: http://veiculos.fipe.org.br/
- The scraper will retry failed requests automatically

### Database Errors

**Error**: `IntegrityError` or `OperationalError`

**Solution**:
- Delete `fipe_data.db` and run `python database_models.py` again
- Check database URL in `config.py`

## 📈 Analyzing the Data

Once you have data, you can use pandas to analyze it:

```python
import pandas as pd
from sqlalchemy import create_engine

engine = create_engine('sqlite:///fipe_data.db')

# Load all data into a DataFrame
query = """
SELECT
    rm.month_date,
    b.brand_name,
    cm.model_name,
    my.year_description,
    cp.price,
    cp.fipe_code
FROM car_prices cp
JOIN reference_months rm ON cp.reference_month_id = rm.id
JOIN model_years my ON cp.model_year_id = my.id
JOIN car_models cm ON my.car_model_id = cm.id
JOIN brands b ON cm.brand_id = b.id
ORDER BY rm.month_date DESC
"""

df = pd.read_sql(query, engine)
print(df.head())

# Analyze price trends
average_by_brand = df.groupby('brand_name')['price'].mean()
print(average_by_brand.sort_values(ascending=False))
```

## 📝 Next Steps / Future Improvements

Potential enhancements:

1. **API Creation**: Build a REST API to serve the scraped data
2. **Data Visualization**: Create price trend charts with matplotlib/plotly
3. **Export Options**: Add CSV/Excel export functionality
4. **Scheduling**: Add automated daily scraping with cron/Task Scheduler
5. **Price Alerts**: Notify when prices drop below a threshold
6. **Data Validation**: Add checks for price anomalies
7. **Docker**: Containerize the application for easy deployment

## 📄 License

This is for educational purposes. Always respect the website's terms of service.

## ⚖️ Legal Disclaimer

This tool is for educational and research purposes. The data belongs to FIPE. Always verify you're complying with:
- Website terms of service
- Robots.txt file
- Applicable laws in your jurisdiction

Use responsibly and ethically.
