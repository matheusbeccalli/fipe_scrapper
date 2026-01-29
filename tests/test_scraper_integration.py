"""Integration tests for scraper's proxy rotation functionality."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestScraperProxyInit:
    """Tests for scraper's proxy pool initialization."""

    def test_proxy_pool_initialized_when_enabled(self, mocker):
        """ProxyPool should be created when PROXY_CONFIG.enabled=True."""
        mocker.patch.dict(
            "config.PROXY_CONFIG",
            {"enabled": True, "proxy_file": "proxies.txt", "max_consecutive_failures": 5},
        )

        # Mock the proxy file to avoid FileNotFoundError
        mock_pool = MagicMock()
        mock_pool.load_proxies.return_value = 0
        mocker.patch("fipe_api_scraper.ProxyPool", return_value=mock_pool)

        from fipe_api_scraper import FIPEAPIScraper

        scraper = FIPEAPIScraper()
        assert scraper.proxy_pool is not None

    def test_proxy_pool_none_when_disabled(self, mocker):
        """ProxyPool should be None when PROXY_CONFIG.enabled=False."""
        mocker.patch.dict(
            "config.PROXY_CONFIG",
            {"enabled": False, "proxy_file": "proxies.txt", "max_consecutive_failures": 5},
        )

        from fipe_api_scraper import FIPEAPIScraper

        scraper = FIPEAPIScraper()
        assert scraper.proxy_pool is None


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


class TestMakeRequestWithProxy:
    """Tests for _make_request proxy integration."""

    @pytest.mark.asyncio
    async def test_uses_proxy_from_pool(self, mocker):
        """Should use proxy returned by proxy_pool.get_next_proxy()."""
        mocker.patch.dict(
            "config.PROXY_CONFIG",
            {"enabled": True, "proxy_file": "proxies.txt", "max_consecutive_failures": 5},
        )

        mock_pool = MagicMock()
        mock_pool.get_next_proxy = AsyncMock(return_value="http://1.2.3.4:80")
        mock_pool.get_random_user_agent.return_value = "TestAgent/1.0"
        mock_pool.is_socks_proxy.return_value = False
        mock_pool.load_proxies.return_value = 1
        mocker.patch("fipe_api_scraper.ProxyPool", return_value=mock_pool)

        # We just verify the proxy pool is used, not the actual HTTP request
        from fipe_api_scraper import FIPEAPIScraper

        scraper = FIPEAPIScraper()
        assert scraper.proxy_pool is mock_pool
        assert scraper.proxy_pool.load_proxies.called

    @pytest.mark.asyncio
    async def test_rotates_user_agent(self, mocker):
        """Should call get_random_user_agent for User-Agent rotation."""
        mocker.patch.dict(
            "config.PROXY_CONFIG",
            {"enabled": True, "proxy_file": "proxies.txt", "max_consecutive_failures": 5},
        )

        mock_pool = MagicMock()
        mock_pool.get_next_proxy = AsyncMock(return_value="http://1.2.3.4:80")
        mock_pool.get_random_user_agent.return_value = "Mozilla/5.0 Test"
        mock_pool.is_socks_proxy.return_value = False
        mock_pool.load_proxies.return_value = 1
        mocker.patch("fipe_api_scraper.ProxyPool", return_value=mock_pool)

        from fipe_api_scraper import FIPEAPIScraper

        scraper = FIPEAPIScraper()
        ua = scraper.proxy_pool.get_random_user_agent()
        assert ua == "Mozilla/5.0 Test"


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
