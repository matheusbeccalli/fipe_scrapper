# Proxy Rotation Tests - Implementation Handoff

## Context

We implemented a proxy rotation feature for the FIPE scraper to avoid rate limiting (429 errors). This document provides all the context needed to implement tests using pytest.

## Files to Test

### 1. `proxy_manager.py` (Primary - Unit Tests)

**Class:** `ProxyPool`

**Methods to test:**

| Method | Description | Test Priority |
|--------|-------------|---------------|
| `__init__` | Initialize with configurable `max_consecutive_failures` | Medium |
| `load_proxies(filepath)` | Load proxies from file, auto-prefix `http://` | High |
| `get_next_proxy()` | Async round-robin rotation, skip blacklisted | High |
| `get_random_user_agent()` | Return random User-Agent string | Low |
| `mark_proxy_success(proxy)` | Reset failure count to 0 | High |
| `mark_proxy_failed(proxy)` | Increment failures, blacklist after threshold | High |
| `is_socks_proxy(proxy)` | Detect socks4:// and socks5:// prefixes | Medium |
| `get_pool_stats()` | Return dict with total/active/blacklisted counts | Medium |

**Constants to verify:**
- `USER_AGENTS` list has 50+ entries
- All User-Agents are valid strings

### 2. `fipe_api_scraper.py` (Integration Tests)

**Methods affected by proxy rotation:**

| Method | What to test |
|--------|--------------|
| `__init__` | `self.proxy_pool` is initialized when `PROXY_CONFIG.enabled=True` |
| `_make_request` | Uses proxy from pool, rotates User-Agent |
| `_execute_request` | Handles SOCKS vs HTTP proxies differently |
| `_handle_response` | Marks proxy success/failure based on status code |

### 3. `config.py` (Verify Configuration)

- `PROXY_CONFIG` dict exists with keys: `enabled`, `proxy_file`, `max_consecutive_failures`

---

## Test Scenarios

### ProxyPool Unit Tests

```python
# test_proxy_manager.py

class TestProxyPoolInit:
    def test_default_max_failures_is_5(self):
        pass

    def test_custom_max_failures(self):
        pass

    def test_initial_state_is_empty(self):
        pass

class TestLoadProxies:
    def test_load_proxies_from_file(self, tmp_path):
        # Create temp file with proxies
        pass

    def test_auto_prefix_http_for_bare_ip_port(self, tmp_path):
        # "1.2.3.4:80" -> "http://1.2.3.4:80"
        pass

    def test_preserve_existing_protocol_prefix(self, tmp_path):
        # "socks5://1.2.3.4:80" stays as-is
        pass

    def test_skip_empty_lines_and_comments(self, tmp_path):
        # Lines starting with # should be ignored
        pass

    def test_file_not_found_returns_zero(self):
        pass

    def test_resets_state_on_reload(self, tmp_path):
        # Blacklist and counts should reset
        pass

class TestGetNextProxy:
    @pytest.mark.asyncio
    async def test_round_robin_rotation(self):
        pass

    @pytest.mark.asyncio
    async def test_skips_blacklisted_proxies(self):
        pass

    @pytest.mark.asyncio
    async def test_returns_none_when_all_blacklisted(self):
        pass

    @pytest.mark.asyncio
    async def test_returns_none_when_empty_pool(self):
        pass

    @pytest.mark.asyncio
    async def test_logs_stats_every_100_requests(self):
        pass

class TestMarkProxySuccess:
    def test_resets_failure_count_to_zero(self):
        pass

    def test_handles_none_proxy(self):
        pass

    def test_handles_unknown_proxy(self):
        pass

class TestMarkProxyFailed:
    def test_increments_failure_count(self):
        pass

    def test_blacklists_after_max_failures(self):
        pass

    def test_handles_none_proxy(self):
        pass

    def test_handles_unknown_proxy(self):
        pass

class TestIsSocksProxy:
    def test_detects_socks4(self):
        assert pool.is_socks_proxy("socks4://1.2.3.4:1080") == True

    def test_detects_socks5(self):
        assert pool.is_socks_proxy("socks5://1.2.3.4:1080") == True

    def test_http_is_not_socks(self):
        assert pool.is_socks_proxy("http://1.2.3.4:80") == False

    def test_none_is_not_socks(self):
        assert pool.is_socks_proxy(None) == False

class TestGetPoolStats:
    def test_returns_correct_counts(self):
        pass

    def test_using_direct_true_when_all_blacklisted(self):
        pass

    def test_using_direct_true_when_empty_pool(self):
        pass

class TestUserAgents:
    def test_user_agents_list_has_50_plus_entries(self):
        from proxy_manager import USER_AGENTS
        assert len(USER_AGENTS) >= 50

    def test_all_user_agents_are_strings(self):
        from proxy_manager import USER_AGENTS
        assert all(isinstance(ua, str) for ua in USER_AGENTS)

    def test_get_random_user_agent_returns_from_list(self):
        from proxy_manager import USER_AGENTS
        pool = ProxyPool()
        ua = pool.get_random_user_agent()
        assert ua in USER_AGENTS
```

### Integration Tests (with mocking)

```python
# test_scraper_proxy_integration.py

class TestScraperProxyInit:
    def test_proxy_pool_initialized_when_enabled(self, mocker):
        # Mock config.PROXY_CONFIG['enabled'] = True
        pass

    def test_proxy_pool_none_when_disabled(self, mocker):
        # Mock config.PROXY_CONFIG['enabled'] = False
        pass

    def test_logs_warning_when_no_proxies_loaded(self, mocker):
        pass

class TestMakeRequestWithProxy:
    @pytest.mark.asyncio
    async def test_uses_proxy_from_pool(self, mocker):
        # Mock proxy_pool.get_next_proxy() and verify it's used
        pass

    @pytest.mark.asyncio
    async def test_rotates_user_agent(self, mocker):
        # Verify headers include rotated User-Agent
        pass

    @pytest.mark.asyncio
    async def test_marks_proxy_success_on_200(self, mocker):
        pass

    @pytest.mark.asyncio
    async def test_marks_proxy_failed_on_429(self, mocker):
        pass

    @pytest.mark.asyncio
    async def test_marks_proxy_failed_on_520(self, mocker):
        pass

    @pytest.mark.asyncio
    async def test_gets_fresh_proxy_on_retry(self, mocker):
        pass

    @pytest.mark.asyncio
    async def test_falls_back_to_direct_when_no_proxies(self, mocker):
        # proxy_pool.get_next_proxy() returns None
        pass
```

---

## Test Setup Requirements

### Dependencies to add to requirements.txt (or requirements-dev.txt)

```
pytest>=7.0.0
pytest-asyncio>=0.21.0
pytest-mock>=3.10.0
aioresponses>=0.7.4  # For mocking aiohttp requests
```

### pytest configuration (pyproject.toml or pytest.ini)

```toml
# pyproject.toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

### Suggested test file structure

```
tests/
├── __init__.py
├── conftest.py              # Shared fixtures
├── test_proxy_manager.py    # Unit tests for ProxyPool
└── test_scraper_integration.py  # Integration tests
```

### Key fixtures (conftest.py)

```python
import pytest
from proxy_manager import ProxyPool

@pytest.fixture
def proxy_pool():
    """Fresh ProxyPool instance for each test."""
    return ProxyPool(max_consecutive_failures=5)

@pytest.fixture
def loaded_proxy_pool(tmp_path):
    """ProxyPool with proxies loaded from temp file."""
    proxy_file = tmp_path / "proxies.txt"
    proxy_file.write_text("""
http://1.1.1.1:80
http://2.2.2.2:80
socks5://3.3.3.3:1080
4.4.4.4:80
""")
    pool = ProxyPool()
    pool.load_proxies(str(proxy_file))
    return pool

@pytest.fixture
def mock_config(mocker):
    """Mock config.PROXY_CONFIG."""
    return mocker.patch('fipe_api_scraper.config.PROXY_CONFIG', {
        'enabled': True,
        'proxy_file': 'proxies.txt',
        'max_consecutive_failures': 5,
    })
```

---

## Special Considerations

1. **Async tests**: Use `@pytest.mark.asyncio` decorator and `pytest-asyncio` plugin for testing `get_next_proxy()` and scraper methods.

2. **File I/O**: Use `tmp_path` fixture (built into pytest) for creating temporary proxy files.

3. **Mocking HTTP requests**: Use `aioresponses` library to mock aiohttp requests without hitting real servers.

4. **Thread safety**: `ProxyPool` uses `asyncio.Lock` - tests should verify concurrent access doesn't cause issues.

5. **Logging**: Some tests may need to capture log output to verify warnings/info messages.

6. **No real proxies needed**: All tests should use mocked or local test data, never real proxy servers.

---

## Running Tests

```bash
# Install test dependencies
pip install pytest pytest-asyncio pytest-mock aioresponses

# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_proxy_manager.py

# Run with coverage
pip install pytest-cov
pytest --cov=proxy_manager --cov=fipe_api_scraper --cov-report=html
```

---

## Current Code References

- `proxy_manager.py` - Lines 1-180 (full file)
- `fipe_api_scraper.py:27-28` - Imports (ProxyPool, ProxyConnector)
- `fipe_api_scraper.py:126-137` - Proxy pool initialization in `__init__`
- `fipe_api_scraper.py:240-453` - `_make_request`, `_execute_request`, `_handle_response` methods
- `config.py:84-88` - `PROXY_CONFIG` definition
