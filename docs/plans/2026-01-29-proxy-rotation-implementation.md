# Proxy Rotation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add proxy rotation with HTTP/SOCKS4/SOCKS5 support to avoid rate limiting when scraping FIPE data.

**Architecture:** Create a `ProxyPool` class in a new `proxy_manager.py` module that manages proxy rotation, failure tracking, and User-Agent randomization. Integrate with `FIPEAPIScraper._make_request()` to use proxies on each request.

**Tech Stack:** Python 3, aiohttp, aiohttp-socks, asyncio

---

## Task 1: Add aiohttp-socks Dependency

**Files:**
- Modify: `requirements.txt`

**Step 1: Add aiohttp-socks to requirements.txt**

Add this line after `aiohttp==3.13.0`:

```
aiohttp-socks==0.10.1
```

**Step 2: Install the dependency**

Run: `pip install aiohttp-socks==0.10.1`
Expected: Successfully installed aiohttp-socks

**Step 3: Commit**

```bash
git add requirements.txt
git commit -m "chore: add aiohttp-socks dependency for SOCKS proxy support"
```

---

## Task 2: Add PROXY_CONFIG to config.py

**Files:**
- Modify: `config.py:82` (after RESUME_CONFIG)

**Step 1: Add proxy configuration block**

Add after line 82 (after RESUME_CONFIG closing brace):

```python
# Proxy rotation configuration
PROXY_CONFIG = {
    'enabled': os.getenv('PROXY_ENABLED', 'true').lower() == 'true',
    'proxy_file': os.getenv('PROXY_FILE', 'proxies.txt'),
    'max_consecutive_failures': int(os.getenv('PROXY_MAX_FAILURES', '5')),
}
```

**Step 2: Commit**

```bash
git add config.py
git commit -m "feat(config): add PROXY_CONFIG for proxy rotation settings"
```

---

## Task 3: Create proxy_manager.py with USER_AGENTS List

**Files:**
- Create: `proxy_manager.py`

**Step 1: Create the file with User-Agent list**

```python
"""
Proxy Pool Manager for FIPE Scraper

Manages a pool of HTTP/SOCKS4/SOCKS5 proxies with:
- Round-robin rotation on every request
- Failure tracking and automatic blacklisting
- User-Agent randomization
"""

import asyncio
import random
from typing import Optional, Dict, List
from loguru import logger

# 50+ realistic User-Agent strings
USER_AGENTS = [
    # Chrome on Windows (versions 120-130)
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    # Chrome on Mac
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    # Chrome on Linux
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
    # Firefox on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:130.0) Gecko/20100101 Firefox/130.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:129.0) Gecko/20100101 Firefox/129.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
    # Firefox on Mac
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:130.0) Gecko/20100101 Firefox/130.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:129.0) Gecko/20100101 Firefox/129.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:128.0) Gecko/20100101 Firefox/128.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:127.0) Gecko/20100101 Firefox/127.0",
    # Firefox on Linux
    "Mozilla/5.0 (X11; Linux x86_64; rv:130.0) Gecko/20100101 Firefox/130.0",
    "Mozilla/5.0 (X11; Linux x86_64; rv:129.0) Gecko/20100101 Firefox/129.0",
    "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0",
    "Mozilla/5.0 (X11; Linux x86_64; rv:127.0) Gecko/20100101 Firefox/127.0",
    # Safari on Mac
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.6 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    # Edge on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36 Edg/130.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36 Edg/129.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 Edg/128.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36 Edg/127.0.0.0",
    # Chrome on Android
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 14; SM-S928B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 13; SM-A546B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Mobile Safari/537.36",
    # Safari on iOS
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.6 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPad; CPU OS 17_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.6 Mobile/15E148 Safari/604.1",
]


class ProxyPool:
    """
    Manages a pool of proxies with rotation, failure tracking, and User-Agent randomization.

    Supports HTTP, SOCKS4, and SOCKS5 proxies via protocol prefix in proxy URLs.
    """

    def __init__(self, max_consecutive_failures: int = 5):
        """
        Initialize the proxy pool.

        Args:
            max_consecutive_failures: Number of consecutive failures before blacklisting a proxy
        """
        self.proxies: List[str] = []
        self.failed_counts: Dict[str, int] = {}
        self.blacklist: set = set()
        self.max_consecutive_failures = max_consecutive_failures
        self.current_index = 0
        self.lock = asyncio.Lock()
        self.request_count = 0
        self.stats_interval = 100  # Log stats every N requests

    def load_proxies(self, filepath: str) -> int:
        """
        Load proxies from a file.

        Expected format: one proxy per line
        - With protocol: http://ip:port, socks4://ip:port, socks5://ip:port
        - Without protocol (defaults to http): ip:port

        Args:
            filepath: Path to the proxies file

        Returns:
            Number of proxies loaded
        """
        self.proxies = []
        self.failed_counts = {}
        self.blacklist = set()
        self.current_index = 0

        try:
            with open(filepath, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue

                    # Add http:// prefix if no protocol specified
                    if not line.startswith(('http://', 'https://', 'socks4://', 'socks5://')):
                        line = f'http://{line}'

                    self.proxies.append(line)
                    self.failed_counts[line] = 0

            logger.info(f"Loaded {len(self.proxies)} proxies from {filepath}")
            return len(self.proxies)

        except FileNotFoundError:
            logger.warning(f"Proxy file not found: {filepath}")
            return 0
        except Exception as e:
            logger.error(f"Error loading proxies from {filepath}: {e}")
            return 0

    async def get_next_proxy(self) -> Optional[str]:
        """
        Get the next available proxy using round-robin rotation.

        Returns:
            Proxy URL string, or None if all proxies are blacklisted
        """
        async with self.lock:
            self.request_count += 1

            # Log stats periodically
            if self.request_count % self.stats_interval == 0:
                stats = self.get_pool_stats()
                logger.info(f"Proxy pool stats: {stats['active_proxies']} active, {stats['blacklisted_proxies']} blacklisted")

            if not self.proxies:
                return None

            # Find next non-blacklisted proxy
            attempts = 0
            while attempts < len(self.proxies):
                proxy = self.proxies[self.current_index]
                self.current_index = (self.current_index + 1) % len(self.proxies)

                if proxy not in self.blacklist:
                    return proxy

                attempts += 1

            # All proxies blacklisted
            logger.warning("All proxies exhausted, falling back to direct connection")
            return None

    def get_random_user_agent(self) -> str:
        """Get a random User-Agent string."""
        return random.choice(USER_AGENTS)

    def mark_proxy_success(self, proxy: Optional[str]) -> None:
        """
        Mark a proxy as successful, resetting its failure count.

        Args:
            proxy: The proxy URL that succeeded
        """
        if proxy and proxy in self.failed_counts:
            self.failed_counts[proxy] = 0

    def mark_proxy_failed(self, proxy: Optional[str]) -> None:
        """
        Mark a proxy as failed, incrementing its failure count.
        Blacklists the proxy after max_consecutive_failures.

        Args:
            proxy: The proxy URL that failed
        """
        if not proxy or proxy not in self.failed_counts:
            return

        self.failed_counts[proxy] += 1

        if self.failed_counts[proxy] >= self.max_consecutive_failures:
            self.blacklist.add(proxy)
            stats = self.get_pool_stats()
            logger.warning(
                f"Proxy {proxy} blacklisted after {self.max_consecutive_failures} failures "
                f"(active: {stats['active_proxies']})"
            )

    def is_socks_proxy(self, proxy: Optional[str]) -> bool:
        """
        Check if a proxy is a SOCKS proxy (requires special handling).

        Args:
            proxy: The proxy URL to check

        Returns:
            True if SOCKS4 or SOCKS5 proxy, False otherwise
        """
        if not proxy:
            return False
        return proxy.startswith(('socks4://', 'socks5://'))

    def get_pool_stats(self) -> Dict:
        """
        Get current proxy pool statistics.

        Returns:
            Dictionary with pool statistics
        """
        return {
            'total_proxies': len(self.proxies),
            'active_proxies': len(self.proxies) - len(self.blacklist),
            'blacklisted_proxies': len(self.blacklist),
            'using_direct': len(self.proxies) == 0 or len(self.blacklist) == len(self.proxies),
        }
```

**Step 2: Commit**

```bash
git add proxy_manager.py
git commit -m "feat: add ProxyPool class with User-Agent rotation

- ProxyPool manages HTTP/SOCKS4/SOCKS5 proxy rotation
- Round-robin proxy selection with blacklist support
- 50+ realistic User-Agent strings for rotation
- Automatic blacklisting after 5 consecutive failures
- Thread-safe with asyncio.Lock"
```

---

## Task 4: Modify FIPEAPIScraper.__init__ to Initialize Proxy Pool

**Files:**
- Modify: `fipe_api_scraper.py:65-126` (the __init__ method)

**Step 1: Add import at top of file**

Add after line 11 (after `from database_models import ...`):

```python
from proxy_manager import ProxyPool
```

**Step 2: Add proxy pool initialization in __init__**

Add after line 121 (after `self.batch_size = 100` line, before the logger.info statements):

```python
        # Proxy pool for rotation
        if config.PROXY_CONFIG.get('enabled', True):
            self.proxy_pool = ProxyPool(
                max_consecutive_failures=config.PROXY_CONFIG.get('max_consecutive_failures', 5)
            )
            proxy_file = config.PROXY_CONFIG.get('proxy_file', 'proxies.txt')
            proxy_count = self.proxy_pool.load_proxies(proxy_file)
            if proxy_count == 0:
                logger.warning("No proxies loaded, will use direct connections")
        else:
            self.proxy_pool = None
            logger.info("Proxy rotation disabled")
```

**Step 3: Commit**

```bash
git add fipe_api_scraper.py
git commit -m "feat(scraper): initialize ProxyPool in FIPEAPIScraper"
```

---

## Task 5: Modify _make_request to Use Proxy Rotation

**Files:**
- Modify: `fipe_api_scraper.py:228-344` (the _make_request method)

**Step 1: Add aiohttp_socks import at top of file**

Add after the proxy_manager import:

```python
from aiohttp_socks import ProxyConnector
```

**Step 2: Replace the _make_request method**

Replace the entire `_make_request` method (lines 228-344) with:

```python
    async def _make_request(self, session: aiohttp.ClientSession,
                           endpoint: str, data: Dict = None) -> Optional[Dict]:
        """
        Make an async API request with rate limiting, retry logic, and proxy rotation.

        Args:
            session: aiohttp session (used for HTTP proxies and direct connections)
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

        # Get proxy and User-Agent for this request
        proxy = None
        if self.proxy_pool:
            proxy = await self.proxy_pool.get_next_proxy()

        # Build headers with rotated User-Agent
        headers = HEADERS.copy()
        if self.proxy_pool:
            headers['User-Agent'] = self.proxy_pool.get_random_user_agent()

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

                    # Make request - handle SOCKS vs HTTP proxies differently
                    response_data = await self._execute_request(
                        url, data, headers, proxy, request_desc
                    )

                    if response_data is not None:
                        return response_data

                    # Request failed, will retry if attempts remain
                    if attempt < self.max_retries:
                        self.stats['retries'] += 1
                        # Get a fresh proxy for retry
                        if self.proxy_pool:
                            proxy = await self.proxy_pool.get_next_proxy()
                        continue
                    else:
                        return None

                except Exception as e:
                    logger.error(f"Error making request to {request_desc}: {e}")
                    if self.proxy_pool and proxy:
                        self.proxy_pool.mark_proxy_failed(proxy)
                    self.stats['failed_requests'] += 1

                    if attempt < self.max_retries:
                        self.stats['retries'] += 1
                        # Get a fresh proxy for retry
                        if self.proxy_pool:
                            proxy = await self.proxy_pool.get_next_proxy()
                        continue
                    return None

            return None

    async def _execute_request(self, url: str, data: Dict, headers: Dict,
                               proxy: Optional[str], request_desc: str) -> Optional[Dict]:
        """
        Execute a single HTTP request, handling SOCKS and HTTP proxies appropriately.

        Args:
            url: Full URL to request
            data: POST data
            headers: Request headers
            proxy: Proxy URL or None for direct connection
            request_desc: Description for logging

        Returns:
            JSON response data or None on error
        """
        # Determine if we need a SOCKS connector
        use_socks = self.proxy_pool and proxy and self.proxy_pool.is_socks_proxy(proxy)

        try:
            if use_socks:
                # SOCKS proxy - need to create a new session with ProxyConnector
                connector = ProxyConnector.from_url(proxy)
                async with aiohttp.ClientSession(connector=connector) as socks_session:
                    async with socks_session.post(url, data=data, headers=headers) as response:
                        return await self._handle_response(response, proxy, request_desc)
            else:
                # HTTP proxy or direct connection
                async with aiohttp.ClientSession() as http_session:
                    async with http_session.post(url, data=data, headers=headers, proxy=proxy) as response:
                        return await self._handle_response(response, proxy, request_desc)

        except aiohttp.ClientProxyConnectionError as e:
            logger.debug(f"Proxy connection error on {request_desc} via {proxy}: {e}")
            if self.proxy_pool and proxy:
                self.proxy_pool.mark_proxy_failed(proxy)
            return None
        except aiohttp.ClientConnectorError as e:
            logger.debug(f"Connection error on {request_desc}: {e}")
            if self.proxy_pool and proxy:
                self.proxy_pool.mark_proxy_failed(proxy)
            return None
        except Exception as e:
            logger.debug(f"Request error on {request_desc}: {e}")
            if self.proxy_pool and proxy:
                self.proxy_pool.mark_proxy_failed(proxy)
            return None

    async def _handle_response(self, response: aiohttp.ClientResponse,
                               proxy: Optional[str], request_desc: str) -> Optional[Dict]:
        """
        Handle the HTTP response, updating stats and proxy status.

        Args:
            response: The aiohttp response object
            proxy: The proxy used (for marking success/failure)
            request_desc: Description for logging

        Returns:
            JSON response data or None on error
        """
        if response.status == 200:
            self.stats['successful_requests'] += 1

            # Mark proxy as successful
            if self.proxy_pool and proxy:
                self.proxy_pool.mark_proxy_success(proxy)

            # Adaptive: reduce delay on consecutive successes (very slowly)
            self.consecutive_successes += 1
            self.recent_520_errors = max(0, self.recent_520_errors - 1)
            self.recent_429_errors = max(0, self.recent_429_errors - 1)

            # Log success with pattern tracking info
            logger.debug(f"SUCCESS on {request_desc} (consecutive: {self.consecutive_successes}, delay: {self.adaptive_delay:.3f}s)")

            # Only speed up after many successes and if delay is above minimum
            if self.consecutive_successes >= self.speedup_threshold and self.adaptive_delay > self.min_delay:
                old_delay = self.adaptive_delay
                self.adaptive_delay = max(self.min_delay, self.adaptive_delay * 0.98)  # Reduce by 2%
                self.consecutive_successes = 0
                logger.info(f"Speeding up: reduced delay from {old_delay:.3f}s to {self.adaptive_delay:.3f}s")

            return await response.json()

        elif response.status == 429:  # Rate limited
            self.stats['rate_limit_hits'] += 1
            self.consecutive_successes = 0
            self.recent_429_errors += 1

            # Mark proxy as failed on rate limit
            if self.proxy_pool and proxy:
                self.proxy_pool.mark_proxy_failed(proxy)

            # Adaptive: back off on rate limit errors
            if self.recent_429_errors >= self.rate_limit_threshold:
                old_delay = self.adaptive_delay
                self.adaptive_delay = min(self.max_delay, self.adaptive_delay * 1.5)
                logger.warning(f"Rate limited (429) on {request_desc}, increased delay from {old_delay:.3f}s to {self.adaptive_delay:.3f}s")
                self.recent_429_errors = 0

            logger.debug(f"Rate limited (429) on {request_desc}")
            return None

        elif response.status == 520:  # Server overload
            self.consecutive_successes = 0
            self.recent_520_errors += 1

            # Mark proxy as failed on server overload
            if self.proxy_pool and proxy:
                self.proxy_pool.mark_proxy_failed(proxy)

            # Adaptive: back off on 520 errors
            if self.recent_520_errors >= self.error_threshold:
                old_delay = self.adaptive_delay
                self.adaptive_delay = min(self.max_delay, self.adaptive_delay * 1.5)
                logger.warning(f"Server overload (520) on {request_desc}, increased delay from {old_delay:.3f}s to {self.adaptive_delay:.3f}s")
                self.recent_520_errors = 0

            logger.debug(f"Server overload (520) on {request_desc}")
            return None

        else:
            logger.warning(f"Request failed with status {response.status} for {request_desc}")
            if self.proxy_pool and proxy:
                self.proxy_pool.mark_proxy_failed(proxy)
            self.stats['failed_requests'] += 1
            return None
```

**Step 3: Commit**

```bash
git add fipe_api_scraper.py
git commit -m "feat(scraper): integrate proxy rotation into _make_request

- Rotate proxy on each request via ProxyPool
- Rotate User-Agent header on each request
- Handle SOCKS proxies with ProxyConnector
- Mark proxies as failed on 429/520/connection errors
- Fall back to direct connection when all proxies exhausted"
```

---

## Task 6: Update proxies.txt Format

**Files:**
- Modify: `proxies.txt`

**Step 1: Add protocol prefixes to existing proxies**

The current format `ip:port` will work (auto-prefixed with `http://`), but for clarity and to demonstrate the format, add a comment header:

Add at the top of `proxies.txt`:

```
# FIPE Scraper Proxy List
# Format: protocol://ip:port (one per line)
# Supported protocols: http://, socks4://, socks5://
# Lines without protocol prefix default to http://
#
# Example:
# http://192.168.1.1:8080
# socks5://192.168.1.2:1080
#
```

**Step 2: Commit**

```bash
git add proxies.txt
git commit -m "docs(proxies): add format documentation header to proxies.txt"
```

---

## Task 7: Test the Implementation

**Files:**
- None (manual testing)

**Step 1: Run a quick test scrape**

Run: `python fipe_api_scraper.py`

**Expected behavior:**
1. Log shows "Loaded X proxies from proxies.txt"
2. Requests use different proxies (visible at DEBUG level)
3. Failed proxies get blacklisted after 5 failures
4. When all proxies fail, falls back to direct connection

**Step 2: Check logs**

Run: `tail -f fipe_scraper.log | grep -E "(proxy|Proxy|USER)"`

Look for:
- "Loaded 469 proxies from proxies.txt"
- "Proxy pool stats: X active, Y blacklisted"
- "Proxy ... blacklisted after 5 failures"

**Step 3: If working correctly, commit any final adjustments**

```bash
git add -A
git commit -m "test: verify proxy rotation working correctly"
```

---

## Summary

| Task | Description | Files |
|------|-------------|-------|
| 1 | Add aiohttp-socks dependency | requirements.txt |
| 2 | Add PROXY_CONFIG to config | config.py |
| 3 | Create ProxyPool class | proxy_manager.py (new) |
| 4 | Initialize proxy pool in scraper | fipe_api_scraper.py |
| 5 | Integrate proxy rotation in _make_request | fipe_api_scraper.py |
| 6 | Document proxies.txt format | proxies.txt |
| 7 | Test the implementation | (manual) |
