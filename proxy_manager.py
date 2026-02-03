"""
Proxy Pool Manager for FIPE Scraper

Manages a pool of HTTP/SOCKS4/SOCKS5 proxies with:
- Round-robin rotation on every request
- Failure tracking and automatic blacklisting
- User-Agent randomization
"""

import asyncio
import random
from dataclasses import dataclass
from typing import Optional, Dict, List

import aiohttp
from aiohttp_socks import ProxyConnector
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

# Default headers for API requests
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/javascript, */*; q=0.01',
    'Accept-Language': 'en-US,en;q=0.9,pt-BR;q=0.8,pt;q=0.7',
    'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
    'Origin': 'http://veiculos.fipe.org.br',
    'Referer': 'http://veiculos.fipe.org.br/',
}


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
        - Authenticated: username:password@ip:port (defaults to http)
        - Authenticated with protocol: socks5://username:password@ip:port

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


@dataclass
class WorkItem:
    """A single API request to be processed by a worker."""
    endpoint: str
    data: Dict
    result: asyncio.Future
    headers: Dict
    cookies: Optional[Dict] = None  # Cloudflare bypass cookies


class ProxyWorker:
    """
    A worker that owns a proxy and persistent session.
    Pulls work items from a queue and executes requests.
    """

    def __init__(self, worker_id: int, proxy: str, work_queue: asyncio.Queue,
                 api_base_url: str, max_retries: int = 3):
        self.worker_id = worker_id
        self.proxy = proxy
        self.work_queue = work_queue
        self.api_base_url = api_base_url
        self.max_retries = max_retries
        self.session: Optional[aiohttp.ClientSession] = None
        self.is_running = False
        self.requests_completed = 0
        self.requests_failed = 0
        self._is_socks = proxy.startswith(('socks4://', 'socks5://'))

    async def start(self):
        """Create the persistent session and start processing."""
        if self._is_socks:
            connector = ProxyConnector.from_url(self.proxy)
            self.session = aiohttp.ClientSession(connector=connector)
        else:
            self.session = aiohttp.ClientSession()

        self.is_running = True
        logger.debug(f"Worker {self.worker_id} started with proxy {self.proxy[:30]}...")

    async def stop(self):
        """Stop the worker and close the session."""
        self.is_running = False
        if self.session:
            await self.session.close()
            self.session = None

    async def run(self):
        """Main worker loop - pull work items and execute requests."""
        await self.start()

        try:
            while self.is_running:
                try:
                    # Wait for work with timeout to allow graceful shutdown
                    work_item = await asyncio.wait_for(
                        self.work_queue.get(),
                        timeout=1.0
                    )
                except asyncio.TimeoutError:
                    continue

                if work_item is None:  # Shutdown signal
                    # Note: No task_done() for shutdown signal - it's not a real work item
                    # and the pool uses asyncio.gather() to wait for workers, not queue.join()
                    break

                try:
                    # Execute the request
                    result = await self._execute_request(work_item)

                    # Deliver result
                    if not work_item.result.done():
                        try:
                            work_item.result.set_result(result)
                        except Exception as e:
                            logger.warning(f"Worker {self.worker_id} failed to deliver result: {e}")
                finally:
                    self.work_queue.task_done()
        finally:
            await self.stop()

    async def _execute_request(self, work_item: WorkItem) -> Optional[Dict]:
        """Execute a single request with retries."""
        if not self.session:
            return None
        url = f"{self.api_base_url}{work_item.endpoint}"

        # Build cookie header string if cookies provided
        cookie_header = None
        if work_item.cookies:
            cookie_header = "; ".join(f"{k}={v}" for k, v in work_item.cookies.items())

        for attempt in range(self.max_retries):
            try:
                # Merge headers with cookie if present
                headers = work_item.headers.copy()
                if cookie_header:
                    headers['Cookie'] = cookie_header

                if self._is_socks:
                    # SOCKS: session already has connector, no proxy param
                    async with self.session.post(
                        url,
                        data=work_item.data,
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=30)
                    ) as response:
                        return await self._handle_response(response)
                else:
                    # HTTP: pass proxy as parameter
                    async with self.session.post(
                        url,
                        data=work_item.data,
                        headers=headers,
                        proxy=self.proxy,
                        timeout=aiohttp.ClientTimeout(total=30)
                    ) as response:
                        return await self._handle_response(response)

            except Exception as e:
                logger.debug(f"Worker {self.worker_id} request failed (attempt {attempt+1}): {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(0.5 * (attempt + 1))
                continue

        self.requests_failed += 1
        return None

    async def _handle_response(self, response: aiohttp.ClientResponse) -> Optional[Dict]:
        """Handle HTTP response, return JSON or None."""
        if response.status == 200:
            self.requests_completed += 1
            return await response.json()
        elif response.status == 403:
            # Cloudflare block - log and return None
            logger.warning(f"Worker {self.worker_id} blocked by Cloudflare (403)")
            self.requests_failed += 1
            await asyncio.sleep(1.0)
            return None
        elif response.status == 429:
            logger.warning(f"Worker {self.worker_id} rate limited, backing off")
            await asyncio.sleep(2.0)
            return None
        elif response.status == 520:
            logger.debug(f"Worker {self.worker_id} got 520, server overload")
            await asyncio.sleep(1.0)
            return None
        elif response.status == 503:
            # Cloudflare challenge page
            logger.warning(f"Worker {self.worker_id} got Cloudflare challenge (503)")
            await asyncio.sleep(2.0)
            return None
        else:
            logger.debug(f"Worker {self.worker_id} got status {response.status}")
            return None


class ProxyWorkerPool:
    """
    Manages a pool of ProxyWorkers for parallel request processing.

    Usage:
        pool = ProxyWorkerPool(proxies, api_base_url)
        await pool.start()
        result = await pool.submit('/ConsultarMarcas', {'codigoTabelaReferencia': 123})
        await pool.stop()
    """

    def __init__(self, proxies: List[str], api_base_url: str,
                 max_retries: int = 3, queue_size: int = 0,
                 cloudflare_bypass=None):
        """
        Initialize the worker pool.

        Args:
            proxies: List of proxy URLs
            api_base_url: Base URL for API requests
            max_retries: Max retries per request
            queue_size: Max queue size (0 = unlimited)
            cloudflare_bypass: Optional CloudflareBypass instance for Cloudflare protection
        """
        self.proxies = proxies
        self.api_base_url = api_base_url
        self.max_retries = max_retries
        self.work_queue: asyncio.Queue = asyncio.Queue(maxsize=queue_size)
        self.workers: List[ProxyWorker] = []
        self.worker_tasks: List[asyncio.Task] = []
        self.is_running = False
        self._user_agents = USER_AGENTS
        self._cloudflare_bypass = cloudflare_bypass

    async def start(self):
        """Start all workers."""
        if self.is_running:
            return

        self.is_running = True

        # Create a worker for each proxy
        for i, proxy in enumerate(self.proxies):
            worker = ProxyWorker(
                worker_id=i,
                proxy=proxy,
                work_queue=self.work_queue,
                api_base_url=self.api_base_url,
                max_retries=self.max_retries
            )
            self.workers.append(worker)

            # Start worker as background task
            task = asyncio.create_task(worker.run())
            self.worker_tasks.append(task)

        logger.info(f"ProxyWorkerPool started with {len(self.workers)} workers")

    async def stop(self):
        """Stop all workers gracefully."""
        if not self.is_running:
            return

        self.is_running = False

        # Send shutdown signal to all workers
        for _ in self.workers:
            await self.work_queue.put(None)

        # Wait for all workers to finish
        if self.worker_tasks:
            await asyncio.gather(*self.worker_tasks, return_exceptions=True)

        self.workers.clear()
        self.worker_tasks.clear()

        logger.info("ProxyWorkerPool stopped")

    async def submit(self, endpoint: str, data: Dict = None) -> Optional[Dict]:
        """
        Submit a request to be processed by a worker.

        Args:
            endpoint: API endpoint (e.g., '/ConsultarMarcas')
            data: POST data

        Returns:
            JSON response or None on error
        """
        if not self.is_running:
            raise RuntimeError("Worker pool is not running")

        # Create future for result delivery
        result_future = asyncio.get_running_loop().create_future()

        # Build headers with random User-Agent
        headers = HEADERS.copy()
        
        # Get Cloudflare bypass cookies and user-agent if available
        cookies = None
        if self._cloudflare_bypass and self._cloudflare_bypass.has_valid_session():
            cookies, cf_user_agent = self._cloudflare_bypass.get_session()
            if cf_user_agent:
                # Use the same user-agent that obtained the cookies
                headers['User-Agent'] = cf_user_agent
            else:
                headers['User-Agent'] = random.choice(self._user_agents)
        else:
            headers['User-Agent'] = random.choice(self._user_agents)

        # Create work item
        work_item = WorkItem(
            endpoint=endpoint,
            data=data or {},
            result=result_future,
            headers=headers,
            cookies=cookies
        )

        # Submit to queue
        await self.work_queue.put(work_item)

        # Wait for result
        return await result_future

    def get_stats(self) -> Dict:
        """Get pool statistics."""
        total_completed = sum(w.requests_completed for w in self.workers)
        total_failed = sum(w.requests_failed for w in self.workers)

        return {
            'workers': len(self.workers),
            'queue_size': self.work_queue.qsize(),
            'requests_completed': total_completed,
            'requests_failed': total_failed,
            'is_running': self.is_running,
        }
