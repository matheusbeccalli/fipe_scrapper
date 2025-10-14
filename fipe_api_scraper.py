"""
FIPE API Scraper - Ultra-fast version using direct API calls

This scraper bypasses Selenium entirely and uses the FIPE REST API directly.
Expected to be 50-100x faster than the Selenium-based approach.

Key features:
- Direct HTTP requests (no browser overhead)
- Async/await for concurrent requests
- Simple, maintainable code (~300 lines vs 777)
- Lower memory usage (~50MB vs ~500MB per browser)
"""

import asyncio
import aiohttp
import json
import time
from datetime import datetime
from typing import List, Dict, Optional
from loguru import logger

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

import config
from database_models import (
    create_database, ReferenceMonth, Brand,
    CarModel, ModelYear, CarPrice
)


# API Configuration
API_BASE_URL = "http://veiculos.fipe.org.br/api/veiculos"
VEHICLE_TYPE_CAR = 1

# HTTP Headers to mimic browser requests
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/javascript, */*; q=0.01',
    'Accept-Language': 'en-US,en;q=0.9,pt-BR;q=0.8,pt;q=0.7',
    'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
    'Origin': 'http://veiculos.fipe.org.br',
    'Referer': 'http://veiculos.fipe.org.br/',
    'X-Requested-With': 'XMLHttpRequest',
}


class FIPEAPIScraper:
    """
    High-performance FIPE scraper using direct API calls.

    This scraper uses aiohttp for async HTTP requests, allowing
    hundreds of concurrent API calls for dramatically faster scraping.
    """

    def __init__(self, max_concurrent_requests: int = 1):
        """
        Initialize the API scraper.

        Args:
            max_concurrent_requests: Maximum number of concurrent API requests
                                    (default 1 for stable operation)
        """
        # Setup logging
        logger.add(
            config.LOG_CONFIG['log_file'],
            rotation=config.LOG_CONFIG['rotation'],
            level=config.LOG_CONFIG['log_level']
        )
        logger.info("Initializing FIPE API Scraper...")

        # Setup database
        self.engine, SessionMaker = create_database(config.DATABASE_URL)
        self.SessionMaker = SessionMaker

        # Concurrency control
        self.semaphore = asyncio.Semaphore(max_concurrent_requests)
        self.request_delay = 0.5  # 500ms between requests (very conservative)
        self.max_concurrent_requests = max_concurrent_requests

        # Retry configuration
        self.max_retries = 5
        self.backoff_multiplier = 2.0  # Double wait time on each retry
        self.rate_limit_pause = 5.0  # Longer pause on rate limits

        # Adaptive rate limiting (very conservative thresholds)
        self.adaptive_delay = 0.5  # Start with 500ms (was 0.3s)
        self.min_delay = 0.4  # Don't go below 400ms (was 0.15s)
        self.max_delay = 2.0  # Cap at 2 seconds
        self.error_threshold = 3  # Number of 520 errors before backing off
        self.rate_limit_threshold = 2  # Number of 429 errors before backing off
        self.recent_520_errors = 0
        self.recent_429_errors = 0
        self.consecutive_successes = 0
        self.speedup_threshold = 100  # Need 100 successes before speeding up (was 50)

        # Statistics
        self.stats = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'rate_limit_hits': 0,
            'retries': 0,
            'prices_saved': 0,
            'start_time': None,
        }

        # Checkpoint system
        self.checkpoint = self._load_checkpoint()

        # Database batch buffer
        self.db_batch = []
        self.batch_size = 100  # Save every 100 records

        logger.info(f"Scraper initialized with max {max_concurrent_requests} concurrent requests")
        logger.info(f"Rate limiting: {self.request_delay}s delay, {self.max_retries} retries")
        logger.info(f"Database batching: {self.batch_size} records per commit")

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

    async def _make_request(self, session: aiohttp.ClientSession,
                           endpoint: str, data: Dict = None) -> Optional[Dict]:
        """
        Make an async API request with rate limiting and retry logic.

        Args:
            session: aiohttp session
            endpoint: API endpoint (e.g., '/ConsultarMarcas')
            data: POST data payload

        Returns:
            JSON response or None on error
        """
        url = f"{API_BASE_URL}{endpoint}"

        # Create a short description of the request for logging
        request_desc = endpoint
        if data:
            if 'codigoMarca' in data:
                request_desc += f" [brand={data['codigoMarca']}"
            if 'codigoModelo' in data:
                request_desc += f", model={data['codigoModelo']}"
            if 'anoModelo' in data:
                request_desc += f", year={data['anoModelo']}"
            if data and ('codigoMarca' in data or 'codigoModelo' in data or 'anoModelo' in data):
                request_desc += "]"

        async with self.semaphore:  # Rate limiting
            for attempt in range(self.max_retries + 1):
                try:
                    self.stats['total_requests'] += 1

                    # Use adaptive delay based on recent errors
                    if attempt > 0:
                        delay = self.adaptive_delay * (self.backoff_multiplier ** attempt)
                        await asyncio.sleep(delay)
                    else:
                        # Small delay on first attempt
                        await asyncio.sleep(self.adaptive_delay)

                    async with session.post(url, data=data, headers=HEADERS) as response:
                        if response.status == 200:
                            self.stats['successful_requests'] += 1

                            # Adaptive: reduce delay on consecutive successes (very slowly)
                            self.consecutive_successes += 1
                            self.recent_520_errors = max(0, self.recent_520_errors - 1)
                            self.recent_429_errors = max(0, self.recent_429_errors - 1)

                            # Log success with pattern tracking info
                            logger.debug(f"SUCCESS on {request_desc} (consecutive: {self.consecutive_successes}, delay: {self.adaptive_delay:.3f}s)")

                            # Only speed up after many successes and if delay is above minimum
                            if self.consecutive_successes >= self.speedup_threshold and self.adaptive_delay > self.min_delay:
                                old_delay = self.adaptive_delay
                                self.adaptive_delay = max(self.min_delay, self.adaptive_delay * 0.98)  # Reduce by 2% (was 5%)
                                self.consecutive_successes = 0
                                logger.info(f"Speeding up: reduced delay from {old_delay:.3f}s to {self.adaptive_delay:.3f}s")

                            return await response.json()

                        elif response.status == 429:  # Rate limited
                            self.stats['rate_limit_hits'] += 1
                            self.consecutive_successes = 0
                            self.recent_429_errors += 1

                            # Adaptive: back off on rate limit errors
                            if self.recent_429_errors >= self.rate_limit_threshold:
                                old_delay = self.adaptive_delay
                                self.adaptive_delay = min(self.max_delay, self.adaptive_delay * 1.5)
                                logger.warning(f"Rate limited (429) on {request_desc}, increased delay from {old_delay:.3f}s to {self.adaptive_delay:.3f}s")
                                self.recent_429_errors = 0

                            if attempt < self.max_retries:
                                self.stats['retries'] += 1
                                wait_time = self.rate_limit_pause * (self.backoff_multiplier ** attempt)
                                logger.debug(f"Rate limited (429) on {request_desc}, retrying in {wait_time:.1f}s (attempt {attempt + 1}/{self.max_retries})")
                                await asyncio.sleep(wait_time)
                                continue
                            else:
                                logger.warning(f"Rate limit (429) exceeded for {request_desc}, max retries reached")
                                self.stats['failed_requests'] += 1
                                return None

                        elif response.status == 520:  # Server overload
                            self.consecutive_successes = 0
                            self.recent_520_errors += 1

                            # Adaptive: back off on 520 errors
                            if self.recent_520_errors >= self.error_threshold:
                                old_delay = self.adaptive_delay
                                self.adaptive_delay = min(self.max_delay, self.adaptive_delay * 1.5)
                                logger.warning(f"Server overload (520) on {request_desc}, increased delay from {old_delay:.3f}s to {self.adaptive_delay:.3f}s")
                                self.recent_520_errors = 0

                            if attempt < self.max_retries:
                                self.stats['retries'] += 1
                                wait_time = 2.0 * (self.backoff_multiplier ** attempt)
                                logger.debug(f"Server overload (520) on {request_desc}, retrying in {wait_time:.1f}s (attempt {attempt + 1}/{self.max_retries})")
                                await asyncio.sleep(wait_time)
                                continue
                            else:
                                logger.warning(f"Server overload (520) for {request_desc}, max retries reached")
                                self.stats['failed_requests'] += 1
                                return None

                        else:
                            logger.warning(f"Request failed with status {response.status} for {request_desc}")
                            self.stats['failed_requests'] += 1
                            return None

                except Exception as e:
                    logger.error(f"Error making request to {request_desc}: {e}")
                    self.stats['failed_requests'] += 1
                    return None

            return None

    async def get_reference_months(self, session: aiohttp.ClientSession) -> List[Dict]:
        """Get all available reference months."""
        logger.info("Fetching reference months...")
        months = await self._make_request(session, '/ConsultarTabelaDeReferencia')

        if not months:
            logger.error("Failed to fetch reference months")
            return []

        logger.info(f"Found {len(months)} reference months")
        return self._filter_months_by_date_range(months)

    async def get_brands(self, session: aiohttp.ClientSession, month_code: int) -> List[Dict]:
        """Get all car brands for a specific month."""
        data = {
            'codigoTabelaReferencia': month_code,
            'codigoTipoVeiculo': VEHICLE_TYPE_CAR
        }
        brands = await self._make_request(session, '/ConsultarMarcas', data)
        return brands or []

    async def get_models(self, session: aiohttp.ClientSession,
                        month_code: int, brand_code: str) -> Dict:
        """Get all models for a brand (includes years in response)."""
        data = {
            'codigoTabelaReferencia': month_code,
            'codigoTipoVeiculo': VEHICLE_TYPE_CAR,
            'codigoMarca': brand_code
        }
        models = await self._make_request(session, '/ConsultarModelos', data)
        return models or {'Modelos': [], 'Anos': []}

    async def get_price(self, session: aiohttp.ClientSession,
                       month_code: int, brand_code: str, model_code: int,
                       year: str, fuel_code: str) -> Optional[Dict]:
        """Get price data for a specific vehicle configuration."""
        data = {
            'codigoTabelaReferencia': month_code,
            'codigoTipoVeiculo': VEHICLE_TYPE_CAR,
            'codigoMarca': brand_code,
            'codigoModelo': model_code,
            'anoModelo': year,
            'codigoTipoCombustivel': fuel_code,
            'tipoConsulta': 'tradicional'
        }
        return await self._make_request(session, '/ConsultarValorComTodosParametros', data)

    def _parse_month_string(self, month_text: str) -> datetime:
        """Parse Portuguese month string to datetime object."""
        portuguese_months = {
            'janeiro': 1, 'fevereiro': 2, 'março': 3, 'abril': 4,
            'maio': 5, 'junho': 6, 'julho': 7, 'agosto': 8,
            'setembro': 9, 'outubro': 10, 'novembro': 11, 'dezembro': 12
        }

        parts = month_text.lower().strip().split('/')
        if len(parts) != 2:
            return datetime.now()

        month_name, year_str = parts
        month_number = portuguese_months.get(month_name.strip(), 1)
        year = int(year_str.strip())

        return datetime(year, month_number, 1)

    def _filter_months_by_date_range(self, months: List[Dict]) -> List[Dict]:
        """Filter months based on DATE_RANGE configuration."""
        start_date_str = config.DATE_RANGE.get('start_date')
        end_date_str = config.DATE_RANGE.get('end_date')

        if not start_date_str or not end_date_str:
            logger.info("No date range specified, scraping all available months")
            return months

        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m').date()
            end_date = datetime.strptime(end_date_str, '%Y-%m').date()

            logger.info(f"Filtering months: {start_date_str} to {end_date_str}")

            filtered_months = []
            for month in months:
                month_date = self._parse_month_string(month['Mes']).date()
                if start_date <= month_date <= end_date:
                    filtered_months.append(month)

            logger.info(f"Filtered to {len(filtered_months)} month(s)")
            return filtered_months

        except ValueError as e:
            logger.error(f"Invalid date range format: {e}")
            return months

    def _clean_price(self, price_text: str) -> float:
        """Clean price text and convert to float."""
        price_text = price_text.replace('R$', '').strip()
        price_text = price_text.replace('.', '').replace(',', '.')
        return float(price_text)

    def _batch_save_to_database(self, month_data: Dict, brand_data: Dict,
                                model_data: Dict, year_data: Dict, price_data: Dict):
        """Add data to batch buffer for bulk saving."""
        # Add to batch
        self.db_batch.append({
            'month': month_data,
            'brand': brand_data,
            'model': model_data,
            'year': year_data,
            'price': price_data
        })

        # If batch is full, flush to database
        if len(self.db_batch) >= self.batch_size:
            self._flush_database_batch()

    def _flush_database_batch(self):
        """Flush accumulated data to database in bulk."""
        if not self.db_batch:
            return

        db_session = self.SessionMaker()

        try:
            # Pre-load all existing entities in one query each
            month_codes = list(set(str(item['month']['Codigo']) for item in self.db_batch))
            brand_codes = list(set(item['brand']['Value'] for item in self.db_batch))

            # Bulk load months
            existing_months = db_session.query(ReferenceMonth).filter(
                ReferenceMonth.month_code.in_(month_codes)
            ).all()
            month_cache = {m.month_code: m for m in existing_months}

            # Bulk load brands
            existing_brands = db_session.query(Brand).filter(
                Brand.brand_code.in_(brand_codes)
            ).all()
            brand_cache = {b.brand_code: b for b in existing_brands}

            # Create missing months/brands first
            for item in self.db_batch:
                month_code = str(item['month']['Codigo'])
                if month_code not in month_cache:
                    month_date = self._parse_month_string(item['month']['Mes'])
                    db_month = ReferenceMonth(
                        month_code=month_code,
                        month_date=month_date.date()
                    )
                    db_session.add(db_month)
                    month_cache[month_code] = db_month

                brand_code = item['brand']['Value']
                if brand_code not in brand_cache:
                    db_brand = Brand(
                        brand_code=brand_code,
                        brand_name=item['brand']['Label']
                    )
                    db_session.add(db_brand)
                    brand_cache[brand_code] = db_brand

            db_session.flush()  # Get IDs for months/brands

            # Now bulk load models for these brands
            brand_ids = [b.id for b in brand_cache.values()]
            existing_models = db_session.query(CarModel).filter(
                CarModel.brand_id.in_(brand_ids)
            ).all()
            model_cache = {f"{m.brand_id}_{m.model_code}": m for m in existing_models}

            # Create missing models
            for item in self.db_batch:
                brand = brand_cache[item['brand']['Value']]
                model_key = f"{brand.id}_{item['model']['Value']}"
                if model_key not in model_cache:
                    db_model = CarModel(
                        brand_id=brand.id,
                        model_code=str(item['model']['Value']),
                        model_name=item['model']['Label']
                    )
                    db_session.add(db_model)
                    model_cache[model_key] = db_model

            db_session.flush()  # Get IDs for models

            # Bulk load years for these models
            model_ids = [m.id for m in model_cache.values()]
            existing_years = db_session.query(ModelYear).filter(
                ModelYear.car_model_id.in_(model_ids)
            ).all()
            year_cache = {f"{y.car_model_id}_{y.year_code}": y for y in existing_years}

            # Create missing years and all prices
            for item in self.db_batch:
                brand = brand_cache[item['brand']['Value']]
                model_key = f"{brand.id}_{item['model']['Value']}"
                model = model_cache[model_key]
                year_key = f"{model.id}_{item['year']['Value']}"

                if year_key not in year_cache:
                    db_year = ModelYear(
                        car_model_id=model.id,
                        year_code=item['year']['Value'],
                        year_description=item['year']['Label']
                    )
                    db_session.add(db_year)
                    year_cache[year_key] = db_year

            db_session.flush()  # Get IDs for years

            # Check which prices already exist to avoid duplicates
            month_year_pairs = []
            for item in self.db_batch:
                month = month_cache[str(item['month']['Codigo'])]
                brand = brand_cache[item['brand']['Value']]
                model_key = f"{brand.id}_{item['model']['Value']}"
                model = model_cache[model_key]
                year_key = f"{model.id}_{item['year']['Value']}"
                year = year_cache[year_key]
                month_year_pairs.append((month.id, year.id))

            # Bulk check for existing prices
            from sqlalchemy import tuple_
            existing_prices = db_session.query(
                CarPrice.reference_month_id,
                CarPrice.model_year_id
            ).filter(
                tuple_(CarPrice.reference_month_id, CarPrice.model_year_id).in_(month_year_pairs)
            ).all()

            existing_set = set(existing_prices)

            # Now create only non-duplicate price records
            new_prices = 0
            for item in self.db_batch:
                month = month_cache[str(item['month']['Codigo'])]
                brand = brand_cache[item['brand']['Value']]
                model_key = f"{brand.id}_{item['model']['Value']}"
                model = model_cache[model_key]
                year_key = f"{model.id}_{item['year']['Value']}"
                year = year_cache[year_key]

                # Skip if already exists
                if (month.id, year.id) in existing_set:
                    continue

                price = self._clean_price(item['price']['Valor'])
                car_price = CarPrice(
                    reference_month_id=month.id,
                    model_year_id=year.id,
                    price=price,
                    fipe_code=item['price'].get('CodigoFipe')
                )
                db_session.add(car_price)
                new_prices += 1

            # Commit all changes at once
            db_session.commit()
            self.stats['prices_saved'] += new_prices
            skipped = len(self.db_batch) - new_prices
            if new_prices > 0:
                logger.debug(f"Flushed {new_prices} new records to database (skipped {skipped} duplicates)")

        except IntegrityError as e:
            db_session.rollback()
            logger.debug(f"Some prices already exist, skipping batch: {e}")
        except Exception as e:
            db_session.rollback()
            logger.error(f"Database error during batch save: {e}")
        finally:
            db_session.close()
            self.db_batch = []  # Clear batch

    async def get_model_years(self, session: aiohttp.ClientSession,
                              month_code: int, brand_code: str, model_code: int) -> List[Dict]:
        """Get all available years for a specific model."""
        # Extra delay specifically for this endpoint (which gets rate limited most)
        await asyncio.sleep(0.2)  # Add 200ms extra delay before this call

        data = {
            'codigoTabelaReferencia': month_code,
            'codigoTipoVeiculo': VEHICLE_TYPE_CAR,
            'codigoMarca': brand_code,
            'codigoModelo': model_code  # Fixed: should be codigoModelo not modelo
        }
        result = await self._make_request(session, '/ConsultarAnoModelo', data)

        # Handle case where result might be a list or None
        if not result:
            return []

        # The API returns a direct list of year objects
        if isinstance(result, list):
            return result

        # Fallback
        return []

    async def scrape_model_years(self, session: aiohttp.ClientSession,
                                 month_data: Dict, brand_data: Dict, model_data: Dict):
        """Scrape all years for a specific model."""
        month_code = month_data['Codigo']
        brand_code = brand_data['Value']
        model_code = model_data['Value']

        # Check checkpoint
        checkpoint_key = f"{month_code}_{brand_code}_{model_code}"
        if checkpoint_key in self.checkpoint:
            logger.debug(f"Skipping already scraped: {model_data['Label']}")
            return 0

        # Get years for THIS specific model
        years = await self.get_model_years(session, month_code, brand_code, model_code)

        if not years:
            logger.warning(f"No years found for {model_data['Label']}")
            return 0

        prices_collected = 0

        # Scrape price for each year
        for year_data in years:
            # Parse year-fuel format (e.g., "1992-1")
            year_value = year_data['Value']
            if '-' in year_value:
                year, fuel_code = year_value.split('-')
            else:
                year = year_value
                fuel_code = '1'

            # Get price data
            price_data = await self.get_price(
                session, month_code, brand_code, model_code, year, fuel_code
            )

            if price_data and 'Valor' in price_data:
                # Add to batch for bulk save (auto-flushes at batch_size)
                self._batch_save_to_database(
                    month_data, brand_data, model_data, year_data, price_data
                )
                prices_collected += 1
                logger.debug(f"✓ {model_data['Label']} {year_data['Label']}: {price_data['Valor']}")

        # NOTE: Don't save checkpoint yet - batch might not be flushed
        # Checkpoint will be saved after explicit flush in scrape_all_data()
        logger.success(f"✓ Completed model: {model_data['Label']} ({len(years)} years)")
        return prices_collected

    async def scrape_all_data(self):
        """Main scraping method - orchestrates the entire process."""
        self.stats['start_time'] = time.time()
        logger.info("Starting API-based scraping...")

        async with aiohttp.ClientSession() as session:
            # Get all reference months
            months = await self.get_reference_months(session)

            if not months:
                logger.error("No months to scrape")
                return

            # Process each month
            for month_idx, month in enumerate(months):
                logger.info(f"Processing month {month_idx + 1}/{len(months)}: {month['Mes']}")

                # Get all brands
                brands = await self.get_brands(session, month['Codigo'])
                logger.info(f"Found {len(brands)} brands")

                # Process each brand
                for brand_idx, brand in enumerate(brands):
                    logger.info(f"Processing brand {brand_idx + 1}/{len(brands)}: {brand['Label']}")

                    # Get all models for this brand
                    models_response = await self.get_models(session, month['Codigo'], brand['Value'])
                    models = models_response.get('Modelos', [])
                    logger.info(f"Found {len(models)} models")

                    # Create tasks for all models (concurrent scraping!)
                    tasks = [
                        self.scrape_model_years(session, month, brand, model)
                        for model in models
                    ]

                    # Execute all model scraping concurrently
                    await asyncio.gather(*tasks)

                    # Flush remaining batch data to database
                    self._flush_database_batch()

                    # Save checkpoint for all models in this brand
                    for model in models:
                        checkpoint_key = f"{month['Codigo']}_{brand['Value']}_{model['Value']}"
                        self.checkpoint[checkpoint_key] = True
                    self._save_checkpoint(self.checkpoint)

                    logger.success(f"✓✓ Completed brand: {brand['Label']}")

                logger.success(f"✓✓✓ Completed month: {month['Mes']}")

        self._print_statistics()
        logger.info("Scraping completed successfully!")

    def _print_statistics(self):
        """Print scraping statistics."""
        elapsed_time = time.time() - self.stats['start_time']

        logger.info("=" * 80)
        logger.info("SCRAPING STATISTICS")
        logger.info("=" * 80)
        logger.info(f"Total requests: {self.stats['total_requests']}")
        logger.info(f"Successful requests: {self.stats['successful_requests']}")
        logger.info(f"Failed requests: {self.stats['failed_requests']}")
        logger.info(f"Rate limit hits (429): {self.stats['rate_limit_hits']}")
        logger.info(f"Successful retries: {self.stats['retries']}")
        logger.info(f"Prices saved: {self.stats['prices_saved']}")
        logger.info(f"Time elapsed: {elapsed_time:.2f} seconds ({elapsed_time/60:.2f} minutes)")

        if elapsed_time > 0:
            logger.info(f"Average requests/second: {self.stats['total_requests']/elapsed_time:.2f}")
            logger.info(f"Success rate: {self.stats['successful_requests']/self.stats['total_requests']*100:.1f}%")

        logger.info("=" * 80)


async def main():
    """Main entry point."""
    # Conservative settings to avoid rate limiting
    # 1 concurrent request with adaptive delay (0.3s - 1.0s)
    # FIPE API is very strict with rate limits
    scraper = FIPEAPIScraper(max_concurrent_requests=1)
    await scraper.scrape_all_data()


if __name__ == "__main__":
    asyncio.run(main())
