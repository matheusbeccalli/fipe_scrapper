# FIPE Car Price Web Scraper

A Python web scraper that collects historical car price data from the FIPE (Fundação Instituto de Pesquisas Econômicas) table, Brazil's vehicle price reference.

## 📋 What This Does

This scraper automatically:
- Navigates through the FIPE website using Selenium
- Loops through all available months (from January 2001 to present)
- Extracts data for all car brands, models, and years
- Saves the data to a SQLite database (or PostgreSQL/MySQL)
- Handles resuming if interrupted
- Logs all activities for monitoring

## 🗂️ Project Structure

```
fipe_scraper/
├── requirements.txt          # Python dependencies
├── config.py                # Configuration settings
├── database_models.py       # Database schema (SQLAlchemy models)
├── fipe_scraper.py         # Main scraper logic
├── README.md               # This file
├── .env                    # Environment variables (create this)
└── fipe_data.db           # SQLite database (created automatically)
```

## 🚀 Getting Started

### Prerequisites

- Python 3.8 or higher (Python 3.13+ recommended for best compatibility)
- Google Chrome browser installed
- Internet connection
- On Windows: No C compiler needed (uses pre-built wheels)

### Installation

1. **Create a project folder and navigate to it:**
```bash
mkdir fipe_scraper
cd fipe_scraper
```

2. **Import all the files I provided into this folder in VS Code**

3. **Create a virtual environment (recommended):**
```bash
# On Windows
python -m venv venv
venv\Scripts\activate

# On macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

4. **Upgrade pip (recommended):**
```bash
python -m pip install --upgrade pip
```

5. **Install dependencies:**
```bash
pip install -r requirements.txt
```

**Note:** The requirements.txt uses `>=` for version ranges to ensure compatibility with newer Python versions (like 3.13+). This allows pip to install the latest compatible versions with pre-built wheels.

6. **Create the database:**
```bash
python database_models.py
```

You should see output showing the tables being created.

## 🏃‍♂️ Running the Scraper

### Basic Usage

Simply run:
```bash
python fipe_scraper.py
```

The scraper will:
- Open Chrome (in headless mode by default)
- Start collecting data from all months, brands, models, and years
- Save everything to `fipe_data.db`
- Create a log file `fipe_scraper.log`

### Configuration

Edit `config.py` to customize:

```python
# See the browser while scraping
SELENIUM_CONFIG = {
    'headless': False,  # Change to False to see the browser
}

# Scrape faster or slower
SCRAPING_CONFIG = {
    'delay_between_requests': 1,  # Reduce delay (be careful!)
}

# Use a different database
DATABASE_URL = 'postgresql://user:password@localhost/fipe_db'
```

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
    ReferenceMonth.month_name,
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

## ⚠️ Important Notes

### **Note from FIPE Website**

According to FIPE's official notice:
- They do **NOT** provide bulk file downloads
- They do **NOT** provide an API
- Data must be queried model by model

**This scraper respects their terms by:**
- Adding delays between requests (default 2 seconds)
- Not overwhelming their servers
- Only collecting publicly available data

### Ethical Scraping

- The scraper includes delays to be respectful to the server
- You can increase delays in `config.py` if needed
- Consider running during off-peak hours
- Don't run multiple instances simultaneously

### Time Estimate

**Full scrape may take several hours or even days** depending on:
- Number of brands, models, years (thousands of combinations)
- Network speed
- Delay settings

**Recommendation**: Start with a test run on a single month to verify everything works.

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

## 🐛 Troubleshooting

### Browser Not Found

**Error**: `WebDriverException: Chrome not found`

**Solution**: Install Google Chrome or update the driver path in the code.

### Element Not Found

**Error**: `NoSuchElementException` or `TimeoutException`

**Possible causes**:
- FIPE website structure changed (you'll need to update element selectors)
- Internet connection issues
- Page loaded too slowly

**Solution**: 
- Increase timeouts in `config.py`
- Check if FIPE website is accessible
- Inspect the website to verify element IDs haven't changed

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
    rm.month_name,
    b.brand_name,
    cm.model_name,
    my.year_description,
    cp.price
FROM car_prices cp
JOIN reference_months rm ON cp.reference_month_id = rm.id
JOIN model_years my ON cp.model_year_id = my.id
JOIN car_models cm ON my.car_model_id = cm.id
JOIN brands b ON cm.brand_id = b.id
"""

df = pd.read_sql(query, engine)
print(df.head())

# Analyze price trends
average_by_brand = df.groupby('brand_name')['price'].mean()
print(average_by_brand.sort_values(ascending=False))
```

## 🤝 Working with Claude as an Agent

To use Claude Code (Anthropic's agentic coding tool) with this project:

1. Make sure all files are in your VS Code workspace
2. Open terminal in VS Code
3. You can ask Claude to:
   - Fix bugs in the scraper
   - Add new features (e.g., export to CSV)
   - Optimize the code
   - Create data visualizations
   - Modify the database schema

## 📝 Next Steps / Future Improvements

Potential enhancements you could ask Claude to help with:

1. **API Creation**: Build a REST API to serve the scraped data
2. **Data Visualization**: Create price trend charts with matplotlib/plotly
3. **Export Options**: Add CSV/Excel export functionality
4. **Scheduling**: Add automated daily scraping with cron/Task Scheduler
5. **Price Alerts**: Notify when prices drop below a threshold
6. **Data Validation**: Add checks for price anomalies
7. **Multi-threading**: Speed up scraping with concurrent requests
8. **Docker**: Containerize the application for easy deployment

## 📄 License

This is for educational purposes. Always respect the website's terms of service.

## ⚖️ Legal Disclaimer

This tool is for educational and research purposes. The data belongs to FIPE. Always verify you're complying with:
- Website terms of service
- Robots.txt file
- Applicable laws in your jurisdiction

Use responsibly and ethically.
