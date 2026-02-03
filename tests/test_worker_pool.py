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

    @pytest.mark.asyncio
    async def test_503_increments_requests_failed(self):
        """503 response should increment requests_failed counter."""
        queue = asyncio.Queue()
        worker = ProxyWorker(
            worker_id=0,
            proxy="http://127.0.0.1:8080",
            work_queue=queue,
            api_base_url="http://test.com"
        )
        await worker.start()

        # Create mock response with 503 status
        mock_response = MagicMock(spec=ClientResponse)
        mock_response.status = 503

        assert worker.requests_failed == 0

        # Handle 503 response
        with patch('asyncio.sleep', new_callable=AsyncMock):
            result = await worker._handle_response(mock_response)

        assert result is None
        assert worker.requests_failed == 1

        await worker.stop()

    @pytest.mark.asyncio
    async def test_worker_disables_after_consecutive_failures(self):
        """Worker should disable after max_consecutive_failures 403 errors."""
        queue = asyncio.Queue()
        worker = ProxyWorker(
            worker_id=0,
            proxy="http://127.0.0.1:8080",
            work_queue=queue,
            api_base_url="http://test.com",
            max_consecutive_failures=3,
        )
        await worker.start()

        mock_response = MagicMock(spec=ClientResponse)
        mock_response.status = 403

        assert worker.is_running is True

        with patch('asyncio.sleep', new_callable=AsyncMock):
            # First two failures - still running
            await worker._handle_response(mock_response)
            assert worker.is_running is True
            await worker._handle_response(mock_response)
            assert worker.is_running is True
            # Third failure - should disable
            await worker._handle_response(mock_response)
            assert worker.is_running is False

        assert worker.consecutive_failures == 3
        await worker.stop()

    @pytest.mark.asyncio
    async def test_consecutive_failures_reset_on_success(self):
        """Consecutive failures counter should reset on 200 response."""
        queue = asyncio.Queue()
        worker = ProxyWorker(
            worker_id=0,
            proxy="http://127.0.0.1:8080",
            work_queue=queue,
            api_base_url="http://test.com",
            max_consecutive_failures=3,
        )
        await worker.start()

        mock_403 = MagicMock(spec=ClientResponse)
        mock_403.status = 403

        mock_200 = MagicMock(spec=ClientResponse)
        mock_200.status = 200
        mock_200.json = AsyncMock(return_value={"data": "test"})

        with patch('asyncio.sleep', new_callable=AsyncMock):
            # Two failures
            await worker._handle_response(mock_403)
            await worker._handle_response(mock_403)
            assert worker.consecutive_failures == 2

            # Success resets counter
            await worker._handle_response(mock_200)
            assert worker.consecutive_failures == 0

            # Two more failures - still running (not 3 consecutive)
            await worker._handle_response(mock_403)
            await worker._handle_response(mock_403)
            assert worker.is_running is True

        await worker.stop()

    @pytest.mark.asyncio
    async def test_work_item_requeued_when_worker_disabled(self):
        """When worker is disabled, current work item should be requeued."""
        queue = asyncio.Queue()
        worker = ProxyWorker(
            worker_id=0,
            proxy="http://127.0.0.1:8080",
            work_queue=queue,
            api_base_url="http://test.com",
            max_consecutive_failures=1,  # Disable on first 403
        )
        await worker.start()

        # Create a work item
        result_future = asyncio.get_running_loop().create_future()
        work_item = WorkItem(
            endpoint="/test",
            data={},
            result=result_future,
            headers={},
            cookies=None,
        )

        # Simulate the scenario: worker processes this item and gets 403
        # The work item should be put back on the queue
        mock_response = MagicMock(spec=ClientResponse)
        mock_response.status = 403

        # Set up the worker state as if it's processing this work item
        worker._current_work_item = work_item

        with patch('asyncio.sleep', new_callable=AsyncMock):
            await worker._handle_response(mock_response)

        # Worker should be disabled
        assert worker.is_running is False

        # Work item should be back on the queue
        assert queue.qsize() == 1
        requeued_item = await queue.get()
        assert requeued_item is work_item

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
