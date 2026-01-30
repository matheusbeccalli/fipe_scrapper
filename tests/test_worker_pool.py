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
