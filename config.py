"""
Configuration file for FIPE scraper

This file contains all the settings and configurations needed for the scraper.
You can modify these values without changing the main scraper code.

Environment variables can be set in a .env file (recommended for sensitive data)
or directly in your system environment.
"""

import os
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()

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
# Use DATABASE_URL environment variable, or default to SQLite
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///fipe_data.db')
# Examples for other databases (set in .env file):
# PostgreSQL: DATABASE_URL=postgresql://username:password@localhost/fipe_db
# MySQL: DATABASE_URL=mysql+pymysql://username:password@localhost/fipe_db

# Scraping behavior
SCRAPING_CONFIG = {
    'delay_between_requests': 2,  # Seconds to wait between requests (be polite!)
    'retry_attempts': 5,  # Number of times to retry failed requests
    'retry_delay': 5,  # Seconds to wait before retrying
}

# Logging configuration
LOG_CONFIG = {
    'log_file': os.getenv('LOG_FILE', 'fipe_scraper.log'),
    'log_level': os.getenv('LOG_LEVEL', 'INFO'),  # Options: DEBUG, INFO, WARNING, ERROR
    'rotation': os.getenv('LOG_ROTATION', '50 MB'),  # Rotate log file when it reaches this size
}

# Date range configuration (optional)
# Set to None to scrape all available months, or specify date range in YYYY-MM format
# Examples: '2024-01' for January 2024, '2020-12' for December 2020
DATE_RANGE = {
    'start_date': os.getenv('SCRAPE_START_DATE', '2024-01'),  # Format: 'YYYY-MM' or None for all
    'end_date': os.getenv('SCRAPE_END_DATE', '2024-01'),      # Format: 'YYYY-MM' or None for all
}

# Resume scraping configuration
RESUME_CONFIG = {
    'enable_resume': True,  # If True, skips already scraped combinations
    'checkpoint_file': 'scraping_checkpoint.json',  # File to save progress
}
