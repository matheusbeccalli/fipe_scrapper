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
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait, Select
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
        Get all options from a dropdown menu.

        Tries native select element first, then falls back to Chosen jQuery plugin.

        Args:
            select_id: The base ID of the select element

        Returns:
            List of dictionaries with 'value' and 'text' keys
        """
        options = []

        try:
            # First, try to get options directly from the native select element
            logger.debug(f"Trying to get options from native select: {select_id}")
            select_element = self.driver.find_element(By.ID, select_id)
            option_elements = select_element.find_elements(By.TAG_NAME, "option")

            if len(option_elements) > 0:
                logger.debug(f"Found {len(option_elements)} options in native select element")
                for idx, option in enumerate(option_elements):
                    # Try multiple ways to get option text
                    option_text = option.text.strip()
                    if not option_text:
                        option_text = option.get_attribute('innerHTML').strip()
                    if not option_text:
                        option_text = option.get_attribute('innerText').strip()
                    if not option_text:
                        option_text = option.get_attribute('textContent').strip()

                    option_value = option.get_attribute('value')

                    # Debug: log first few options
                    if idx < 5:
                        logger.debug(f"  Option {idx}: text='{option_text}', value='{option_value}'")

                    # Skip completely empty options (no text)
                    if option_text:
                        options.append({
                            'value': str(idx),  # Use index as value (for Chosen compatibility)
                            'text': option_text
                        })

                logger.debug(f"Successfully extracted {len(options)} options from native select")
                if len(options) > 0:
                    logger.debug(f"First 3 options: {options[:3]}")
                return options

        except Exception as e:
            logger.debug(f"Could not get options from native select: {e}")

        # Fallback to Chosen plugin method
        try:
            # Click the dropdown to open it
            chosen_id = f"{select_id}_chosen"
            logger.debug(f"Falling back to Chosen dropdown: {chosen_id}")
            self._wait_and_click(chosen_id)

            # Wait for options to load
            time.sleep(1)

            # Find all option elements in the dropdown
            # The Chosen plugin creates li elements for each option
            results_id = f"{chosen_id} .chosen-results li"
            option_elements = self.driver.find_elements(By.CSS_SELECTOR, results_id)

            logger.debug(f"Found {len(option_elements)} option elements in Chosen dropdown")

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

            logger.debug(f"Successfully extracted {len(options)} options from Chosen dropdown")

        except Exception as e:
            logger.error(f"Error getting dropdown options for {select_id}: {e}")

        return options
    
    def _select_dropdown_option(self, select_id: str, option_value: str):
        """
        Select a specific option from a dropdown by its index.

        Uses JavaScript to change the hidden select element and trigger Chosen update.

        Args:
            select_id: The base ID of the select element
            option_value: The index of the option to select (as string)
        """
        try:
            logger.debug(f"Selecting option {option_value} in select {select_id}")

            # Use JavaScript to select the option and trigger change event
            # This works with Chosen plugin which hides the native select
            script = f"""
            var select = document.getElementById('{select_id}');
            if (select) {{
                select.selectedIndex = {option_value};
                // Trigger change event for Chosen to update
                var event = new Event('change', {{ bubbles: true }});
                select.dispatchEvent(event);
                // Also trigger jQuery change if available
                if (typeof jQuery !== 'undefined') {{
                    jQuery(select).trigger('change').trigger('chosen:updated');
                }}
                return true;
            }}
            return false;
            """

            result = self.driver.execute_script(script)

            if result:
                logger.debug(f"Successfully selected option {option_value} using JavaScript")
            else:
                logger.warning(f"JavaScript selection returned false for {select_id}")

            # Wait for any AJAX requests or page updates
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
            logger.info(f"Loading FIPE website: {config.FIPE_URL}")
            self.driver.get(config.FIPE_URL)

            # Wait for page to load completely
            time.sleep(3)

            logger.info(f"Current URL: {self.driver.current_url}")
            logger.info(f"Page title: {self.driver.title}")

            # Scroll down to the consultation form area
            logger.info("Scrolling to consultation form...")
            self.driver.execute_script("window.scrollTo(0, 800);")
            time.sleep(2)

            # Click on the car consultation accordion to expand it (if needed)
            try:
                car_accordion = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, "//h3[contains(text(), 'CARROS')]|//div[contains(text(), 'CONSULTA DE CARROS')]"))
                )
                car_accordion.click()
                time.sleep(2)
                logger.debug("Clicked car consultation accordion")
            except TimeoutException:
                logger.debug("Car accordion not found - likely already expanded")

            # Wait for the select element to be ready
            logger.info(f"Waiting for select element: {config.ELEMENT_IDS['reference_month']}")
            try:
                select_element = WebDriverWait(self.driver, 15).until(
                    EC.presence_of_element_located((By.ID, config.ELEMENT_IDS['reference_month']))
                )
                logger.info("Found select element")

                # Scroll to it
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", select_element)
                time.sleep(2)

            except TimeoutException:
                logger.error(f"Could not find select element: {config.ELEMENT_IDS['reference_month']}")
                raise

            # Give extra time for JavaScript to initialize
            time.sleep(2)

            # Get all reference months
            all_months = self._get_dropdown_options(config.ELEMENT_IDS['reference_month'])
            logger.info(f"Found {len(all_months)} reference months available")

            # Filter months by date range if configured
            months = self._filter_months_by_date_range(all_months)

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
                    for model_idx, model in enumerate(models):
                        # Check if this specific model was already scraped
                        model_checkpoint_key = f"{month['value']}_{brand['value']}_{model['value']}"
                        if model_checkpoint_key in self.checkpoint:
                            logger.debug(f"Skipping already scraped model: {model['text']}")
                            continue

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

                            # Click the "Pesquisar" (Search) button to submit and get price
                            try:
                                search_button = WebDriverWait(self.driver, 10).until(
                                    EC.presence_of_element_located((By.ID, config.ELEMENT_IDS['search_button']))
                                )
                                # Use JavaScript click as it's more reliable for links styled as buttons
                                self.driver.execute_script("arguments[0].click();", search_button)
                                logger.debug("Clicked Pesquisar button")
                                time.sleep(3)  # Wait for AJAX to load results or modal to appear

                                # Check if "no data" modal appeared
                                try:
                                    no_data_modal = self.driver.find_element(By.CSS_SELECTOR, ".jqmWindow:not(.jqmHide)")
                                    modal_text = no_data_modal.text.lower()
                                    if 'dados não encontrados' in modal_text or 'data not found' in modal_text:
                                        logger.warning(f"No data found for {model['text']} {year['text']} in {month['text']}")
                                        # Close the modal
                                        try:
                                            close_button = no_data_modal.find_element(By.CSS_SELECTOR, ".jqmClose")
                                            close_button.click()
                                            time.sleep(0.5)
                                        except:
                                            # If can't find close button, press escape
                                            self.driver.find_element(By.TAG_NAME, 'body').send_keys(Keys.ESCAPE)
                                            time.sleep(0.5)
                                        continue  # Skip to next year
                                except NoSuchElementException:
                                    # No modal, continue normally
                                    pass

                            except Exception as e:
                                logger.error(f"Could not click Pesquisar button: {e}")
                                # Continue anyway to attempt price extraction

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

                        # Save checkpoint after completing each model
                        self.checkpoint[model_checkpoint_key] = True
                        self._save_checkpoint(self.checkpoint)

                    # Mark brand as complete (for backward compatibility)
                    brand_checkpoint_key = f"{month['value']}_{brand['value']}"
                    self.checkpoint[brand_checkpoint_key] = True
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
            # Wait for the results table to appear using explicit wait
            # The table appears inside the resultadoConsultacarroFiltros div after AJAX completes
            logger.debug("Waiting for results table to appear...")

            try:
                # Wait up to 10 seconds for the table to appear
                results_table = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "#resultadoConsultacarroFiltros table"))
                )
                logger.debug("Results table found!")
            except TimeoutException:
                logger.error("Timeout waiting for results table")
                return None

            # Use JavaScript to find and extract the data
            # This is more reliable than CSS selectors which may vary
            script = """
            // Find the results container
            var container = document.getElementById('resultadoConsultacarroFiltros');
            if (!container) {
                return {error: 'Container not found'};
            }

            // Find the table
            var table = container.querySelector('table');
            if (!table) {
                return {error: 'Table not found', containerHtml: container.innerHTML.substring(0, 1000)};
            }

            // Extract all rows
            var rows = table.querySelectorAll('tbody tr');
            var data = {};

            for (var i = 0; i < rows.length; i++) {
                var cells = rows[i].querySelectorAll('td');
                if (cells.length >= 2) {
                    var label = cells[0].textContent.trim();
                    var value = cells[1].textContent.trim();
                    data[label] = value;
                }
            }

            return data;
            """

            result = self.driver.execute_script(script)

            # Check if we got an error
            if isinstance(result, dict) and 'error' in result:
                logger.error(f"JavaScript extraction error: {result['error']}")
                if 'containerHtml' in result:
                    logger.debug(f"Container HTML: {result['containerHtml'][:200]}")
                return None

            # Log what we extracted
            logger.debug(f"Extracted data from table: {result}")

            # Find price in the extracted data
            # Common keys: "Valor", "Preço", "Price"
            price_text = None
            fipe_code = None

            for key, value in result.items():
                key_lower = key.lower()
                if 'valor' in key_lower or 'preço' in key_lower or 'price' in key_lower:
                    price_text = value
                elif 'fipe' in key_lower or 'código' in key_lower:
                    fipe_code = value

            if not price_text:
                logger.warning(f"Could not find price in extracted data. Keys: {list(result.keys())}")
                return None

            # Clean price text (remove "R$", commas, etc.)
            price = self._clean_price(price_text)

            logger.debug(f"Extracted price: R$ {price:.2f}, FIPE code: {fipe_code}")

            return {
                'price': price,
                'fipe_code': fipe_code
            }

        except Exception as e:
            logger.warning(f"Could not extract price data: {e}")
            logger.debug(f"Exception details: {str(e)}")
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

    def _filter_months_by_date_range(self, months: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """
        Filter months list based on DATE_RANGE configuration.

        Args:
            months: List of month dictionaries from the website

        Returns:
            Filtered list of months within the configured date range
        """
        start_date_str = config.DATE_RANGE.get('start_date')
        end_date_str = config.DATE_RANGE.get('end_date')

        # If no date range specified, return all months
        if not start_date_str or not end_date_str:
            logger.info("No date range specified, scraping all available months")
            return months

        try:
            # Parse date range strings (format: YYYY-MM)
            start_date = datetime.strptime(start_date_str, '%Y-%m').date()
            end_date = datetime.strptime(end_date_str, '%Y-%m').date()

            logger.info(f"Filtering months: {start_date_str} to {end_date_str}")

            filtered_months = []
            for month in months:
                month_date = self._parse_month_string(month['text']).date()

                # Check if month is within range (inclusive)
                if start_date <= month_date <= end_date:
                    filtered_months.append(month)

            logger.info(f"Filtered to {len(filtered_months)} month(s) out of {len(months)} available")
            return filtered_months

        except ValueError as e:
            logger.error(f"Invalid date range format: {e}. Expected YYYY-MM format. Scraping all months.")
            return months
    
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
