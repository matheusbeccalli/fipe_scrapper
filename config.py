"""
Configuration file for FIPE scraper

This file contains all the settings and configurations needed for the scraper.
You can modify these values without changing the main scraper code.
"""

# Website configuration
FIPE_URL = "https://veiculos.fipe.org.br/"

# Element IDs on the website (these are the dropdown selectors)
ELEMENT_IDS = {
    'vehicle_type': 'carro',  # We're only interested in cars
    'reference_month': 'selectTabelaReferenciacarro',
    'brand': 'selectMarcacarro',
    'model': 'selectAnoModelocarro',
    'year': 'selectAnocarro',
}

# Selenium configuration
SELENIUM_CONFIG = {
    'headless': True,  # Set to False if you want to see the browser
    'implicit_wait': 10,  # Seconds to wait for elements to appear
    'page_load_timeout': 30,  # Seconds to wait for page to load
}

# Database configuration
DATABASE_URL = 'sqlite:///fipe_data.db'  # SQLite database file
# For PostgreSQL: 'postgresql://username:password@localhost/fipe_db'
# For MySQL: 'mysql+pymysql://username:password@localhost/fipe_db'

# Scraping behavior
SCRAPING_CONFIG = {
    'delay_between_requests': 2,  # Seconds to wait between requests (be polite!)
    'retry_attempts': 3,  # Number of times to retry failed requests
    'retry_delay': 5,  # Seconds to wait before retrying
}

# Logging configuration
LOG_CONFIG = {
    'log_file': 'fipe_scraper.log',
    'log_level': 'INFO',  # Options: DEBUG, INFO, WARNING, ERROR
    'rotation': '10 MB',  # Rotate log file when it reaches this size
}

# Date range configuration (optional)
# Leave None to scrape all available months
# Format: 'month_name/year' (e.g., 'janeiro/2020')
DATE_RANGE = {
    'start_month': None,  # e.g., 'janeiro/2020' or None for all
    'end_month': None,    # e.g., 'dezembro/2024' or None for all
}

# Resume scraping configuration
RESUME_CONFIG = {
    'enable_resume': True,  # If True, skips already scraped combinations
    'checkpoint_file': 'scraping_checkpoint.json',  # File to save progress
}
