"""Integration tests for scraper's proxy rotation functionality."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestScraperWorkerPoolInit:
    """Tests for scraper's worker pool initialization."""

    def test_worker_pool_initialized_when_proxies_available(self, mocker, tmp_path):
        """WorkerPool should be created when PROXY_CONFIG.enabled=True and proxies exist."""
        # Create a temporary proxy file with proxies
        proxy_file = tmp_path / "proxies.txt"
        proxy_file.write_text("http://1.2.3.4:8080\nhttp://5.6.7.8:8080\n")

        mocker.patch.dict(
            "config.PROXY_CONFIG",
            {"enabled": True, "proxy_file": str(proxy_file), "max_consecutive_failures": 5},
        )
        mocker.patch("config.RESUME_CONFIG", {"enable_resume": False, "checkpoint_file": "test.json"})

        from fipe_api_scraper import FIPEAPIScraper

        scraper = FIPEAPIScraper()
        assert scraper.worker_pool is not None
        assert len(scraper.worker_pool.proxies) == 2

    def test_worker_pool_none_when_disabled(self, mocker):
        """WorkerPool should be None when PROXY_CONFIG.enabled=False."""
        mocker.patch.dict(
            "config.PROXY_CONFIG",
            {"enabled": False, "proxy_file": "proxies.txt", "max_consecutive_failures": 5},
        )
        mocker.patch("config.RESUME_CONFIG", {"enable_resume": False, "checkpoint_file": "test.json"})

        from fipe_api_scraper import FIPEAPIScraper

        scraper = FIPEAPIScraper()
        assert scraper.worker_pool is None

    def test_worker_pool_none_when_no_proxies_loaded(self, mocker, tmp_path):
        """WorkerPool should be None when proxy file is empty."""
        # Create an empty proxy file
        proxy_file = tmp_path / "proxies.txt"
        proxy_file.write_text("")

        mocker.patch.dict(
            "config.PROXY_CONFIG",
            {"enabled": True, "proxy_file": str(proxy_file), "max_consecutive_failures": 5},
        )
        mocker.patch("config.RESUME_CONFIG", {"enable_resume": False, "checkpoint_file": "test.json"})

        from fipe_api_scraper import FIPEAPIScraper

        scraper = FIPEAPIScraper()
        assert scraper.worker_pool is None


class TestProxyConfigStructure:
    """Tests for PROXY_CONFIG structure in config.py."""

    def test_proxy_config_has_required_keys(self):
        """PROXY_CONFIG should have enabled, proxy_file, and max_consecutive_failures."""
        from config import PROXY_CONFIG

        assert "enabled" in PROXY_CONFIG
        assert "proxy_file" in PROXY_CONFIG
        assert "max_consecutive_failures" in PROXY_CONFIG

    def test_proxy_config_types(self):
        """PROXY_CONFIG values should have correct types."""
        from config import PROXY_CONFIG

        assert isinstance(PROXY_CONFIG["enabled"], bool)
        assert isinstance(PROXY_CONFIG["proxy_file"], str)
        assert isinstance(PROXY_CONFIG["max_consecutive_failures"], int)

    def test_max_consecutive_failures_is_positive(self):
        """max_consecutive_failures should be positive."""
        from config import PROXY_CONFIG

        assert PROXY_CONFIG["max_consecutive_failures"] > 0


class TestWorkerPoolRequestFlow:
    """Tests for worker pool request flow."""

    @pytest.mark.asyncio
    async def test_worker_pool_submit_uses_random_user_agent(self, mocker, tmp_path):
        """Worker pool submit should use random User-Agent headers."""
        from proxy_manager import ProxyWorkerPool, USER_AGENTS

        # Create a worker pool with a test proxy
        pool = ProxyWorkerPool(
            proxies=["http://1.2.3.4:8080"],
            api_base_url="http://test.api",
            max_retries=1
        )

        # Verify that USER_AGENTS list is used for rotation
        assert len(USER_AGENTS) > 0
        assert pool._user_agents == USER_AGENTS

    @pytest.mark.asyncio
    async def test_worker_pool_creates_workers_for_each_proxy(self, mocker):
        """Worker pool should create one worker per proxy."""
        from proxy_manager import ProxyWorkerPool

        proxies = ["http://1.2.3.4:8080", "http://5.6.7.8:8080", "socks5://9.10.11.12:1080"]
        pool = ProxyWorkerPool(
            proxies=proxies,
            api_base_url="http://test.api",
            max_retries=3
        )

        # Start the pool to create workers
        await pool.start()

        try:
            assert len(pool.workers) == 3
            # Verify each worker has the correct proxy
            for i, worker in enumerate(pool.workers):
                assert worker.proxy == proxies[i]
                assert worker.worker_id == i
        finally:
            await pool.stop()


class TestProxySuccessFailureMarking:
    """Tests for proxy success/failure marking integration."""

    def test_mark_proxy_success_called_on_success(self, mocker):
        """mark_proxy_success should be available and callable."""
        from proxy_manager import ProxyPool

        pool = ProxyPool()
        # Should not raise even with None
        pool.mark_proxy_success(None)
        pool.mark_proxy_success("http://1.1.1.1:80")

    def test_mark_proxy_failed_called_on_failure(self, mocker):
        """mark_proxy_failed should be available and callable."""
        from proxy_manager import ProxyPool

        pool = ProxyPool()
        # Should not raise even with None
        pool.mark_proxy_failed(None)
        pool.mark_proxy_failed("http://1.1.1.1:80")
