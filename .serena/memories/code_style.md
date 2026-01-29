# Code Style and Conventions

## Naming Conventions
- **Classes**: PascalCase (e.g., `FIPEAPIScraper`, `CarModel`, `FIPEDataExporter`)
- **Functions/Methods**: snake_case (e.g., `get_reference_months`, `scrape_all_data`)
- **Private methods**: Prefixed with `_` (e.g., `_make_request`, `_flush_database_batch`)
- **Constants**: UPPER_SNAKE_CASE (e.g., `API_BASE_URL`, `VEHICLE_TYPE_CAR`)
- **Variables**: snake_case (e.g., `request_delay`, `max_retries`)

## Type Hints
Type hints are used for function parameters and return types:
```python
def __init__(self, max_concurrent_requests: int = 1):
async def _make_request(self, endpoint: str, data: dict) -> Optional[dict]:
```

## Docstrings
Google-style docstrings are used:
```python
def __init__(self, max_concurrent_requests: int = 1):
    """
    Initialize the API scraper.

    Args:
        max_concurrent_requests: Maximum number of concurrent API requests
                                (default 1 for stable operation)
    """
```

## Configuration Pattern
- All configuration in `config.py`
- Environment variables loaded via python-dotenv
- Sensible defaults with env var overrides

## Logging
- Uses `loguru` library
- Log to file with rotation support
- Levels: DEBUG, INFO, WARNING, ERROR

## Database Pattern
- SQLAlchemy ORM with declarative_base
- Factory function `create_database()` returns engine and Session
- Foreign keys and unique constraints for data integrity

## Async Pattern
- Uses `async`/`await` with `aiohttp` for concurrent HTTP requests
- Semaphore for concurrency control
- Batch processing for database writes
