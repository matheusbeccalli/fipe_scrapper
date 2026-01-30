# Worker Pool Proxy Rotation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the current "new session per request" architecture with a Worker Pool where each worker owns a dedicated proxy+session, and work is distributed via an async queue for maximum throughput.

**Architecture:** Create a `ProxyWorkerPool` class that spawns N worker coroutines (one per proxy). Each worker owns a persistent `aiohttp.ClientSession` configured for its proxy. Work items (API requests) are submitted to a shared `asyncio.Queue`, and workers pull items, execute requests, and deliver results via `asyncio.Future`. This naturally load-balances: fast proxies process more requests.

**Tech Stack:** Python asyncio, aiohttp, aiohttp-socks (for SOCKS proxies)

---

## Task 1: Create ProxyWorker Class

**Files:**
- Modify: `proxy_manager.py` (add new class after `ProxyPool`)

**Step 1: Write the ProxyWorker class**

Add after the `ProxyPool` class (around line 246):

```python
@dataclass
class WorkItem:
    """A single API request to be processed by a worker."""
    endpoint: str
    data: Dict
    result: asyncio.Future
    headers: Dict


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
                    break

                # Execute the request
                result = await self._execute_request(work_item)

                # Deliver result
                if not work_item.result.done():
                    work_item.result.set_result(result)

                self.work_queue.task_done()
        finally:
            await self.stop()

    async def _execute_request(self, work_item: WorkItem) -> Optional[Dict]:
        """Execute a single request with retries."""
        url = f"{self.api_base_url}{work_item.endpoint}"

        for attempt in range(self.max_retries):
            try:
                if self._is_socks:
                    # SOCKS: session already has connector, no proxy param
                    async with self.session.post(
                        url,
                        data=work_item.data,
                        headers=work_item.headers,
                        timeout=aiohttp.ClientTimeout(total=30)
                    ) as response:
                        return await self._handle_response(response)
                else:
                    # HTTP: pass proxy as parameter
                    async with self.session.post(
                        url,
                        data=work_item.data,
                        headers=work_item.headers,
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
        elif response.status == 429:
            logger.warning(f"Worker {self.worker_id} rate limited, backing off")
            await asyncio.sleep(2.0)
            return None
        elif response.status == 520:
            logger.debug(f"Worker {self.worker_id} got 520, server overload")
            await asyncio.sleep(1.0)
            return None
        else:
            logger.debug(f"Worker {self.worker_id} got status {response.status}")
            return None
```

**Step 2: Add required imports at top of file**

Add to imports section (around line 1-15):

```python
from dataclasses import dataclass
```

**Step 3: Verify syntax**

Run: `python -m py_compile proxy_manager.py`
Expected: No output (success)

**Step 4: Commit**

```bash
git add proxy_manager.py
git commit -m "feat(proxy): add ProxyWorker class for persistent session per proxy"
```

---

## Task 2: Create ProxyWorkerPool Class

**Files:**
- Modify: `proxy_manager.py` (add after `ProxyWorker` class)

**Step 1: Write the ProxyWorkerPool class**

Add after `ProxyWorker` class:

```python
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
                 max_retries: int = 3, queue_size: int = 0):
        """
        Initialize the worker pool.

        Args:
            proxies: List of proxy URLs
            api_base_url: Base URL for API requests
            max_retries: Max retries per request
            queue_size: Max queue size (0 = unlimited)
        """
        self.proxies = proxies
        self.api_base_url = api_base_url
        self.max_retries = max_retries
        self.work_queue: asyncio.Queue = asyncio.Queue(maxsize=queue_size)
        self.workers: List[ProxyWorker] = []
        self.worker_tasks: List[asyncio.Task] = []
        self.is_running = False
        self._user_agents = USER_AGENTS

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
        result_future = asyncio.get_event_loop().create_future()

        # Build headers with random User-Agent
        headers = HEADERS.copy()
        headers['User-Agent'] = random.choice(self._user_agents)

        # Create work item
        work_item = WorkItem(
            endpoint=endpoint,
            data=data or {},
            result=result_future,
            headers=headers
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
```

**Step 2: Verify syntax**

Run: `python -m py_compile proxy_manager.py`
Expected: No output (success)

**Step 3: Commit**

```bash
git add proxy_manager.py
git commit -m "feat(proxy): add ProxyWorkerPool class for managing worker pool"
```

---

## Task 3: Write Unit Tests for Worker Pool

**Files:**
- Create: `tests/test_worker_pool.py`

**Step 1: Create the test file**

```python
"""Tests for ProxyWorkerPool."""
import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from aiohttp import ClientResponse

from proxy_manager import ProxyWorker, ProxyWorkerPool, WorkItem


class TestProxyWorker:
    """Tests for ProxyWorker class."""

    @pytest.mark.asyncio
    async def test_worker_starts_with_http_proxy(self):
        """Worker should create session for HTTP proxy."""
        queue = asyncio.Queue()
        worker = ProxyWorker(
            worker_id=0,
            proxy="http://127.0.0.1:8080",
            work_queue=queue,
            api_base_url="http://test.com"
        )

        await worker.start()

        assert worker.session is not None
        assert worker.is_running is True
        assert worker._is_socks is False

        await worker.stop()
        assert worker.session is None

    @pytest.mark.asyncio
    async def test_worker_starts_with_socks_proxy(self):
        """Worker should create session with connector for SOCKS proxy."""
        queue = asyncio.Queue()
        worker = ProxyWorker(
            worker_id=0,
            proxy="socks5://127.0.0.1:1080",
            work_queue=queue,
            api_base_url="http://test.com"
        )

        await worker.start()

        assert worker.session is not None
        assert worker.is_running is True
        assert worker._is_socks is True

        await worker.stop()


class TestProxyWorkerPool:
    """Tests for ProxyWorkerPool class."""

    @pytest.mark.asyncio
    async def test_pool_starts_workers(self):
        """Pool should start one worker per proxy."""
        proxies = [
            "http://127.0.0.1:8080",
            "http://127.0.0.1:8081",
            "socks5://127.0.0.1:1080",
        ]

        pool = ProxyWorkerPool(proxies, "http://test.com")
        await pool.start()

        assert len(pool.workers) == 3
        assert pool.is_running is True

        await pool.stop()
        assert pool.is_running is False

    @pytest.mark.asyncio
    async def test_pool_submit_raises_when_not_running(self):
        """Submit should raise if pool not started."""
        pool = ProxyWorkerPool(["http://127.0.0.1:8080"], "http://test.com")

        with pytest.raises(RuntimeError, match="not running"):
            await pool.submit("/test", {})

    @pytest.mark.asyncio
    async def test_pool_stats(self):
        """Pool should report stats correctly."""
        proxies = ["http://127.0.0.1:8080", "http://127.0.0.1:8081"]
        pool = ProxyWorkerPool(proxies, "http://test.com")

        await pool.start()
        stats = pool.get_stats()

        assert stats['workers'] == 2
        assert stats['is_running'] is True
        assert stats['requests_completed'] == 0

        await pool.stop()
```

**Step 2: Run the tests**

Run: `pytest tests/test_worker_pool.py -v`
Expected: All tests pass

**Step 3: Commit**

```bash
git add tests/test_worker_pool.py
git commit -m "test(proxy): add unit tests for ProxyWorker and ProxyWorkerPool"
```

---

## Task 4: Integrate Worker Pool into FIPEAPIScraper

**Files:**
- Modify: `fipe_api_scraper.py`

**Step 1: Add import for ProxyWorkerPool**

At top of file, modify imports (around line 20):

```python
from proxy_manager import ProxyPool, ProxyWorkerPool
```

**Step 2: Modify __init__ to create worker pool**

Replace the proxy pool initialization section in `__init__` (lines 127-141) with:

```python
        # Proxy pool for rotation (legacy, kept for fallback)
        self.proxy_pool = None
        self.worker_pool = None

        if config.PROXY_CONFIG.get('enabled', True):
            proxy_file = config.PROXY_CONFIG.get('proxy_file', 'proxies.txt')

            # Load proxies using existing ProxyPool for the list
            temp_pool = ProxyPool(
                max_consecutive_failures=config.PROXY_CONFIG.get('max_consecutive_failures', 5)
            )
            proxy_count = temp_pool.load_proxies(proxy_file)

            if proxy_count > 0:
                # Create worker pool with loaded proxies
                self.worker_pool = ProxyWorkerPool(
                    proxies=temp_pool.proxies,
                    api_base_url=API_BASE_URL,
                    max_retries=self.max_retries
                )
                logger.info(f"Worker pool configured with {proxy_count} proxies")
            else:
                logger.warning("No proxies loaded, will use direct connections")
        else:
            logger.info("Proxy rotation disabled, using direct connections")

        logger.info(f"Scraper initialized (worker pool: {self.worker_pool is not None})")
        logger.info(f"Rate limiting: {self.request_delay}s delay, {self.max_retries} retries")
        logger.info(f"Database batching: {self.batch_size} records per commit")
```

**Step 3: Verify syntax**

Run: `python -m py_compile fipe_api_scraper.py`
Expected: No output (success)

**Step 4: Commit**

```bash
git add fipe_api_scraper.py
git commit -m "feat(scraper): integrate ProxyWorkerPool into FIPEAPIScraper init"
```

---

## Task 5: Modify _make_request to Use Worker Pool

**Files:**
- Modify: `fipe_api_scraper.py`

**Step 1: Replace _make_request method**

Replace the entire `_make_request` method (lines 243-325) with:

```python
    async def _make_request(self, session: aiohttp.ClientSession,
                           endpoint: str, data: Dict = None) -> Optional[Dict]:
        """
        Make an async API request.

        Uses worker pool if available, otherwise falls back to direct request.

        Args:
            session: aiohttp session (used only for direct/fallback requests)
            endpoint: API endpoint (e.g., '/ConsultarMarcas')
            data: POST data payload

        Returns:
            JSON response or None on error
        """
        self.stats['total_requests'] += 1

        # Use worker pool if available
        if self.worker_pool and self.worker_pool.is_running:
            result = await self.worker_pool.submit(endpoint, data)
            if result:
                self.stats['successful_requests'] += 1
            else:
                self.stats['failed_requests'] += 1
            return result

        # Fallback to direct request (no proxy)
        url = f"{API_BASE_URL}{endpoint}"

        for attempt in range(self.max_retries + 1):
            try:
                if attempt > 0:
                    delay = self.adaptive_delay * (self.backoff_multiplier ** attempt)
                    await asyncio.sleep(delay)
                else:
                    await asyncio.sleep(self.adaptive_delay)

                async with session.post(url, data=data, headers=HEADERS) as response:
                    if response.status == 200:
                        self.stats['successful_requests'] += 1
                        return await response.json()
                    elif response.status == 429:
                        self.stats['rate_limit_hits'] += 1
                        await asyncio.sleep(self.rate_limit_pause)
                    elif response.status == 520:
                        await asyncio.sleep(1.0)

            except Exception as e:
                logger.debug(f"Direct request error on {endpoint}: {e}")

            if attempt < self.max_retries:
                self.stats['retries'] += 1

        self.stats['failed_requests'] += 1
        return None
```

**Step 2: Verify syntax**

Run: `python -m py_compile fipe_api_scraper.py`
Expected: No output (success)

**Step 3: Commit**

```bash
git add fipe_api_scraper.py
git commit -m "feat(scraper): modify _make_request to use worker pool"
```

---

## Task 6: Start/Stop Worker Pool in scrape_all_data

**Files:**
- Modify: `fipe_api_scraper.py`

**Step 1: Add worker pool start at beginning of scrape_all_data**

In `scrape_all_data` method, after `self._block_windows_shutdown(block=True)` (around line 810), add:

```python
        # Start worker pool if configured
        if self.worker_pool:
            await self.worker_pool.start()
            logger.info(f"Worker pool started with {len(self.worker_pool.workers)} workers")
```

**Step 2: Add worker pool stop in the finally block**

In the `finally` block of `scrape_all_data` (around line 890), add before the shutdown unblock:

```python
            # Stop worker pool
            if self.worker_pool:
                await self.worker_pool.stop()
                logger.info("Worker pool stopped")
```

**Step 3: Verify syntax**

Run: `python -m py_compile fipe_api_scraper.py`
Expected: No output (success)

**Step 4: Commit**

```bash
git add fipe_api_scraper.py
git commit -m "feat(scraper): start/stop worker pool in scrape_all_data lifecycle"
```

---

## Task 7: Remove Semaphore (No Longer Needed)

**Files:**
- Modify: `fipe_api_scraper.py`

**Step 1: Remove semaphore from __init__**

In `__init__`, remove or comment out these lines (around lines 88-90):

```python
        # Concurrency control - no longer needed with worker pool
        # self.semaphore = asyncio.Semaphore(max_concurrent_requests)
        self.request_delay = 0.1
        # self.max_concurrent_requests = max_concurrent_requests  # Remove this line
```

**Step 2: Update __init__ signature**

Change `def __init__(self, max_concurrent_requests: int = 1):` to:

```python
    def __init__(self):
```

And remove the docstring reference to `max_concurrent_requests`.

**Step 3: Update main() function**

Change `main()` (around line 973) from:

```python
async def main():
    """Main entry point."""
    scraper = FIPEAPIScraper(max_concurrent_requests=100)
    await scraper.scrape_all_data()
```

To:

```python
async def main():
    """Main entry point."""
    scraper = FIPEAPIScraper()
    await scraper.scrape_all_data()
```

**Step 4: Verify syntax**

Run: `python -m py_compile fipe_api_scraper.py`
Expected: No output (success)

**Step 5: Commit**

```bash
git add fipe_api_scraper.py
git commit -m "refactor(scraper): remove semaphore, concurrency now managed by worker pool"
```

---

## Task 8: Delete Unused _execute_request and _handle_response Methods

**Files:**
- Modify: `fipe_api_scraper.py`

**Step 1: Remove _execute_request method**

Delete the entire `_execute_request` method (lines 327-371).

**Step 2: Remove _handle_response method**

Delete the entire `_handle_response` method (lines 373-452).

**Step 3: Verify syntax**

Run: `python -m py_compile fipe_api_scraper.py`
Expected: No output (success)

**Step 4: Commit**

```bash
git add fipe_api_scraper.py
git commit -m "refactor(scraper): remove unused _execute_request and _handle_response methods"
```

---

## Task 9: Add Worker Pool Stats to _print_statistics

**Files:**
- Modify: `fipe_api_scraper.py`

**Step 1: Update _print_statistics method**

In `_print_statistics` (around line 895), add after the existing stats:

```python
        # Worker pool stats
        if self.worker_pool:
            pool_stats = self.worker_pool.get_stats()
            logger.info(f"Worker pool: {pool_stats['workers']} workers, "
                       f"{pool_stats['requests_completed']} completed, "
                       f"{pool_stats['requests_failed']} failed")
```

**Step 2: Verify syntax**

Run: `python -m py_compile fipe_api_scraper.py`
Expected: No output (success)

**Step 3: Commit**

```bash
git add fipe_api_scraper.py
git commit -m "feat(scraper): add worker pool stats to statistics output"
```

---

## Task 10: Integration Test - Run Scraper with Worker Pool

**Files:**
- None (manual test)

**Step 1: Test with a small date range**

Create a test .env or modify config temporarily:

```bash
SCRAPE_START_DATE=2024-01
SCRAPE_END_DATE=2024-01
BRAND_FILTER_ENABLED=true
BRAND_FILTER_CODES=6
```

**Step 2: Run the scraper**

Run: `python fipe_api_scraper.py`

Expected output should show:
- "Worker pool started with X workers"
- Requests being processed (check logs)
- "Worker pool stopped" at end

**Step 3: Verify performance improvement**

Compare request throughput in logs vs previous runs. With 250 proxies, you should see significantly higher throughput.

**Step 4: Commit final state**

```bash
git add -A
git commit -m "feat: complete worker pool implementation for parallel proxy rotation"
```

---

## Summary

After completing all tasks:

1. **ProxyWorker**: Each worker owns a proxy + persistent session
2. **ProxyWorkerPool**: Manages workers, distributes work via queue
3. **FIPEAPIScraper**: Uses worker pool for all API requests
4. **Performance**: Fast proxies handle more work, slow proxies don't block others
5. **Cleanup**: Removed semaphore and unused methods

Expected performance improvement: **20-40% faster** with mixed-speed proxies, potentially more with highly varied proxy latencies.
