"""
FIPE Car Price Web Scraper

This script scrapes historical car price data from the FIPE website.
It uses Selenium to interact with the JavaScript-heavy website.

Main workflow:
1. Initialize browser and database
2. Loop through all reference months
3. For each month, loop through all brands
4. For each brand, loop through all models
5. For each model, loop through all years
6. Extract and save price data to database
"""

import time
import json
from datetime import datetime
from typing import List, Dict, Optional

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager

from loguru import logger
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

import config
from database_models import (
    create_database, ReferenceMonth, Brand, 
    CarModel, ModelYear, CarPrice
)


class FIPEScraper:
    """
    Main scraper class for FIPE website.
    
    This class handles all the web scraping logic using Selenium to interact
    with the dynamic JavaScript elements on the FIPE website.
    """
    
    def __init__(self):
        """Initialize the scraper with browser and database connections."""
        # Setup logging
        logger.add(
            config.LOG_CONFIG['log_file'],
            rotation=config.LOG_CONFIG['rotation'],
            level=config.LOG_CONFIG['log_level']
        )
        logger.info("Initializing FIPE Scraper...")
        
        # Setup browser
        self.driver = self._setup_browser()
        
        # Setup database
        self.engine, SessionMaker = create_database(config.DATABASE_URL)
        self.db_session = SessionMaker()
        
        # Load checkpoint if resume is enabled
        self.checkpoint = self._load_checkpoint()
        
        logger.info("Scraper initialized successfully!")
    
    def _setup_browser(self) -> webdriver.Chrome:
        """
        Setup and configure the Chrome browser for Selenium.
        
        Returns:
            WebDriver instance configured for scraping
        """
        chrome_options = Options()
        
        # Run in headless mode (no visible browser window)
        if config.SELENIUM_CONFIG['headless']:
            chrome_options.add_argument('--headless')
        
        # Additional options for stability
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        
        # Create the driver
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        # Set timeouts
        driver.implicitly_wait(config.SELENIUM_CONFIG['implicit_wait'])
        driver.set_page_load_timeout(config.SELENIUM_CONFIG['page_load_timeout'])
        
        return driver
    
    def _load_checkpoint(self) -> Dict:
        """Load scraping progress from checkpoint file."""
        if not config.RESUME_CONFIG['enable_resume']:
            return {}
        
        try:
            with open(config.RESUME_CONFIG['checkpoint_file'], 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return {}
    
    def _save_checkpoint(self, checkpoint_data: Dict):
        """Save scraping progress to checkpoint file."""
        if config.RESUME_CONFIG['enable_resume']:
            with open(config.RESUME_CONFIG['checkpoint_file'], 'w') as f:
                json.dump(checkpoint_data, f, indent=2)
    
    def _wait_and_click(self, element_id: str, timeout: int = 10):
        """
        Wait for an element to be clickable and then click it.
        
        Args:
            element_id: The HTML element ID
            timeout: Maximum seconds to wait
        """
        element = WebDriverWait(self.driver, timeout).until(
            EC.element_to_be_clickable((By.ID, element_id))
        )
        element.click()
        time.sleep(0.5)  # Small delay after click
    
    def _get_dropdown_options(self, select_id: str) -> List[Dict[str, str]]:
        """
        Get all options from a dropdown menu (Chosen jQuery plugin).
        
        The FIPE website uses the Chosen plugin which creates a custom dropdown.
        We need to click the dropdown, then extract all the options.
        
        Args:
            select_id: The base ID of the select element
            
        Returns:
            List of dictionaries with 'value' and 'text' keys
        """
        options = []
        
        try:
            # Click the dropdown to open it
            chosen_id = f"{select_id}_chosen"
            self._wait_and_click(chosen_id)
            
            # Wait for options to load
            time.sleep(1)
            
            # Find all option elements in the dropdown
            # The Chosen plugin creates li elements for each option
            results_id = f"{chosen_id} .chosen-results li"
            option_elements = self.driver.find_elements(By.CSS_SELECTOR, results_id)
            
            for option in option_elements:
                # Get the data-option-array-index attribute (the value)
                option_index = option.get_attribute('data-option-array-index')
                option_text = option.text
                
                if option_text and option_index:
                    options.append({
                        'value': option_index,
                        'text': option_text
                    })
            
            # Close the dropdown by clicking somewhere else
            self.driver.find_element(By.TAG_NAME, 'body').click()
            
        except Exception as e:
            logger.error(f"Error getting dropdown options for {select_id}: {e}")
        
        return options
    
    def _select_dropdown_option(self, select_id: str, option_value: str):
        """
        Select a specific option from a dropdown by its value.
        
        Args:
            select_id: The base ID of the select element
            option_value: The value/index of the option to select
        """
        try:
            # Click to open dropdown
            chosen_id = f"{select_id}_chosen"
            self._wait_and_click(chosen_id)
            
            # Find and click the specific option
            option_selector = f"{chosen_id} .chosen-results li[data-option-array-index='{option_value}']"
            option = WebDriverWait(self.driver, 5).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, option_selector))
            )
            option.click()
            
            time.sleep(config.SCRAPING_CONFIG['delay_between_requests'])
            
        except Exception as e:
            logger.error(f"Error selecting option {option_value} for {select_id}: {e}")
    
    def scrape_all_data(self):
        """
        Main method to scrape all FIPE data.
        
        This method orchestrates the entire scraping process:
        1. Load the website
        2. Select the car category
        3. Loop through all months, brands, models, and years
        4. Extract and save data
        """
        logger.info("Starting data scraping...")
        
        try:
            # Load the FIPE website
            self.driver.get(config.FIPE_URL)
            time.sleep(3)  # Wait for page to fully load
            
            # Click on "Consulta de Carros e Utilitários Pequenos"
            car_button = self.driver.find_element(
                By.CSS_SELECTOR, 
                f"a[data-slug='{config.ELEMENT_IDS['vehicle_type']}']"
            )
            car_button.click()
            time.sleep(2)
            
            # Get all reference months
            months = self._get_dropdown_options(config.ELEMENT_IDS['reference_month'])
            logger.info(f"Found {len(months)} reference months")
            
            # Loop through each month
            for month_idx, month in enumerate(months):
                logger.info(f"Processing month {month_idx + 1}/{len(months)}: {month['text']}")
                
                # Select this month
                self._select_dropdown_option(
                    config.ELEMENT_IDS['reference_month'],
                    month['value']
                )
                
                # Save month to database
                db_month = self._save_reference_month(month)
                
                # Get all brands for this month
                brands = self._get_dropdown_options(config.ELEMENT_IDS['brand'])
                logger.info(f"Found {len(brands)} brands")
                
                # Loop through each brand
                for brand_idx, brand in enumerate(brands):
                    logger.info(f"Processing brand {brand_idx + 1}/{len(brands)}: {brand['text']}")
                    
                    # Check checkpoint
                    checkpoint_key = f"{month['value']}_{brand['value']}"
                    if checkpoint_key in self.checkpoint:
                        logger.info(f"Skipping already scraped: {checkpoint_key}")
                        continue
                    
                    # Select this brand
                    self._select_dropdown_option(
                        config.ELEMENT_IDS['brand'],
                        brand['value']
                    )
                    
                    # Save brand to database
                    db_brand = self._save_brand(brand)
                    
                    # Get all models for this brand
                    models = self._get_dropdown_options(config.ELEMENT_IDS['model'])
                    logger.info(f"Found {len(models)} models")
                    
                    # Loop through each model
                    for model in models:
                        # Select this model
                        self._select_dropdown_option(
                            config.ELEMENT_IDS['model'],
                            model['value']
                        )
                        
                        # Save model to database
                        db_model = self._save_car_model(db_brand, model)
                        
                        # Get all years for this model
                        years = self._get_dropdown_options(config.ELEMENT_IDS['year'])

                        # Loop through each year
                        for year_idx, year in enumerate(years):
                            # Select this year
                            self._select_dropdown_option(
                                config.ELEMENT_IDS['year'],
                                year['value']
                            )

                            # Save year to database
                            db_year = self._save_model_year(db_model, year)

                            # Extract price data from the results
                            price_data = self._extract_price_data()

                            # Save price to database
                            if price_data:
                                self._save_price(db_month, db_year, price_data)
                                logger.info(f"✓ Completed: {model['text']} {year['text']} - R$ {price_data['price']:.2f}")

                        # Log completion of all years for this model
                        logger.success(f"✓ Completed all {len(years)} year(s) for model: {model['text']}")

                    # Save checkpoint after completing a brand
                    self.checkpoint[checkpoint_key] = True
                    self._save_checkpoint(self.checkpoint)

                # Log completion of the entire reference month
                logger.success(f"✓✓ Completed all data for reference month: {month['text']}")

            logger.info("Scraping completed successfully!")
            
        except Exception as e:
            logger.error(f"Error during scraping: {e}")
            raise
        
        finally:
            self.cleanup()
    
    def _extract_price_data(self) -> Optional[Dict]:
        """
        Extract the price data from the results area.
        
        After selecting all options, FIPE displays the price information.
        This method extracts that data.
        
        Returns:
            Dictionary with price information or None if not found
        """
        try:
            # Wait for results to load
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "resultado-padrao"))
            )
            
            # Extract price (usually in a specific div or td element)
            # You'll need to inspect the website to find the exact selector
            price_element = self.driver.find_element(By.CSS_SELECTOR, ".resultado-padrao td:nth-child(2)")
            price_text = price_element.text
            
            # Clean price text (remove "R$", commas, etc.)
            price = self._clean_price(price_text)
            
            # Extract FIPE code if available
            try:
                fipe_code_element = self.driver.find_element(By.CSS_SELECTOR, ".codigo-fipe")
                fipe_code = fipe_code_element.text
            except NoSuchElementException:
                fipe_code = None
            
            return {
                'price': price,
                'fipe_code': fipe_code
            }
            
        except Exception as e:
            logger.warning(f"Could not extract price data: {e}")
            return None
    
    def _clean_price(self, price_text: str) -> float:
        """
        Clean price text and convert to float.

        Example: "R$ 45.678,90" -> 45678.90

        Args:
            price_text: Raw price text from website

        Returns:
            Price as float
        """
        # Remove currency symbol and spaces
        price_text = price_text.replace('R$', '').strip()

        # In Brazilian format, . is thousands separator and , is decimal
        price_text = price_text.replace('.', '').replace(',', '.')

        return float(price_text)

    def _parse_month_string(self, month_text: str) -> datetime:
        """
        Parse Portuguese month string to datetime object.

        Example: "dezembro/2024" -> datetime(2024, 12, 1)

        Args:
            month_text: Month string in Portuguese format (e.g., "dezembro/2024")

        Returns:
            datetime object (set to first day of month)
        """
        # Portuguese month names mapping
        portuguese_months = {
            'janeiro': 1, 'fevereiro': 2, 'março': 3, 'abril': 4,
            'maio': 5, 'junho': 6, 'julho': 7, 'agosto': 8,
            'setembro': 9, 'outubro': 10, 'novembro': 11, 'dezembro': 12
        }

        # Split month and year (e.g., "dezembro/2024" -> ["dezembro", "2024"])
        parts = month_text.lower().split('/')
        if len(parts) != 2:
            logger.warning(f"Unexpected month format: {month_text}")
            return datetime.now()  # Fallback to current date

        month_name, year_str = parts

        # Get month number from Portuguese name
        month_number = portuguese_months.get(month_name.strip())
        if not month_number:
            logger.warning(f"Unknown month name: {month_name}")
            return datetime.now()  # Fallback to current date

        # Parse year
        try:
            year = int(year_str.strip())
        except ValueError:
            logger.warning(f"Invalid year: {year_str}")
            return datetime.now()  # Fallback to current date

        # Return datetime object (first day of the month)
        return datetime(year, month_number, 1)
    
    # Database saving methods
    
    def _save_reference_month(self, month_data: Dict) -> ReferenceMonth:
        """Save or retrieve reference month from database."""
        month = self.db_session.query(ReferenceMonth).filter_by(
            month_code=month_data['value']
        ).first()

        if not month:
            # Parse the month string to datetime
            month_date = self._parse_month_string(month_data['text'])

            month = ReferenceMonth(
                month_code=month_data['value'],
                month_date=month_date.date()  # Store as date object
            )
            self.db_session.add(month)
            self.db_session.commit()

        return month
    
    def _save_brand(self, brand_data: Dict) -> Brand:
        """Save or retrieve brand from database."""
        brand = self.db_session.query(Brand).filter_by(
            brand_code=brand_data['value']
        ).first()
        
        if not brand:
            brand = Brand(
                brand_code=brand_data['value'],
                brand_name=brand_data['text']
            )
            self.db_session.add(brand)
            self.db_session.commit()
        
        return brand
    
    def _save_car_model(self, brand: Brand, model_data: Dict) -> CarModel:
        """Save or retrieve car model from database."""
        model = self.db_session.query(CarModel).filter_by(
            brand_id=brand.id,
            model_code=model_data['value']
        ).first()
        
        if not model:
            model = CarModel(
                brand_id=brand.id,
                model_code=model_data['value'],
                model_name=model_data['text']
            )
            self.db_session.add(model)
            self.db_session.commit()
        
        return model
    
    def _save_model_year(self, car_model: CarModel, year_data: Dict) -> ModelYear:
        """Save or retrieve model year from database."""
        year = self.db_session.query(ModelYear).filter_by(
            car_model_id=car_model.id,
            year_code=year_data['value']
        ).first()
        
        if not year:
            year = ModelYear(
                car_model_id=car_model.id,
                year_code=year_data['value'],
                year_description=year_data['text']
            )
            self.db_session.add(year)
            self.db_session.commit()
        
        return year
    
    def _save_price(self, month: ReferenceMonth, year: ModelYear, price_data: Dict):
        """Save price data to database."""
        try:
            price = CarPrice(
                reference_month_id=month.id,
                model_year_id=year.id,
                price=price_data['price'],
                fipe_code=price_data.get('fipe_code')
            )
            self.db_session.add(price)
            self.db_session.commit()
            
        except IntegrityError:
            # This combination already exists, skip it
            self.db_session.rollback()
            logger.debug(f"Price already exists for month {month.id}, year {year.id}")
    
    def cleanup(self):
        """Clean up resources (close browser and database connections)."""
        logger.info("Cleaning up...")
        if self.driver:
            self.driver.quit()
        if self.db_session:
            self.db_session.close()


def main():
    """Main entry point for the scraper."""
    scraper = FIPEScraper()
    scraper.scrape_all_data()


if __name__ == "__main__":
    main()
