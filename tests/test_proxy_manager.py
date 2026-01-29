"""Unit tests for proxy_manager.py ProxyPool class."""

import pytest
from proxy_manager import ProxyPool, USER_AGENTS


class TestProxyPoolInit:
    """Tests for ProxyPool initialization."""

    def test_default_max_failures_is_5(self):
        """Default max_consecutive_failures should be 5."""
        pool = ProxyPool()
        assert pool.max_consecutive_failures == 5

    def test_custom_max_failures(self):
        """Custom max_consecutive_failures should be respected."""
        pool = ProxyPool(max_consecutive_failures=10)
        assert pool.max_consecutive_failures == 10

    def test_initial_state_is_empty(self):
        """New pool should have empty proxies list."""
        pool = ProxyPool()
        assert pool.proxies == []
        assert pool.failed_counts == {}
        assert pool.blacklist == set()
        assert pool.current_index == 0


class TestLoadProxies:
    """Tests for loading proxies from file."""

    def test_load_proxies_from_file(self, tmp_path):
        """Should load proxies from file."""
        proxy_file = tmp_path / "proxies.txt"
        proxy_file.write_text("http://1.2.3.4:80\nhttp://5.6.7.8:8080\n")

        pool = ProxyPool()
        count = pool.load_proxies(str(proxy_file))

        assert count == 2
        assert len(pool.proxies) == 2
        assert "http://1.2.3.4:80" in pool.proxies
        assert "http://5.6.7.8:8080" in pool.proxies

    def test_auto_prefix_http_for_bare_ip_port(self, tmp_path):
        """Bare ip:port should get http:// prefix automatically."""
        proxy_file = tmp_path / "proxies.txt"
        proxy_file.write_text("1.2.3.4:80\n")

        pool = ProxyPool()
        pool.load_proxies(str(proxy_file))

        assert pool.proxies[0] == "http://1.2.3.4:80"

    def test_preserve_existing_protocol_prefix(self, tmp_path):
        """Proxies with protocol prefix should be preserved as-is."""
        proxy_file = tmp_path / "proxies.txt"
        proxy_file.write_text(
            "http://1.1.1.1:80\n"
            "https://2.2.2.2:443\n"
            "socks4://3.3.3.3:1080\n"
            "socks5://4.4.4.4:1080\n"
        )

        pool = ProxyPool()
        pool.load_proxies(str(proxy_file))

        assert "http://1.1.1.1:80" in pool.proxies
        assert "https://2.2.2.2:443" in pool.proxies
        assert "socks4://3.3.3.3:1080" in pool.proxies
        assert "socks5://4.4.4.4:1080" in pool.proxies

    def test_skip_empty_lines_and_comments(self, tmp_path):
        """Empty lines and comments should be ignored."""
        proxy_file = tmp_path / "proxies.txt"
        proxy_file.write_text(
            "# This is a comment\n"
            "\n"
            "http://1.2.3.4:80\n"
            "   \n"
            "# Another comment\n"
            "http://5.6.7.8:80\n"
        )

        pool = ProxyPool()
        count = pool.load_proxies(str(proxy_file))

        assert count == 2
        assert len(pool.proxies) == 2

    def test_file_not_found_returns_zero(self):
        """Missing file should return 0 and not raise."""
        pool = ProxyPool()
        count = pool.load_proxies("/nonexistent/path/proxies.txt")
        assert count == 0
        assert pool.proxies == []

    def test_resets_state_on_reload(self, tmp_path):
        """Reloading should reset blacklist and failure counts."""
        proxy_file = tmp_path / "proxies.txt"
        proxy_file.write_text("http://1.1.1.1:80\n")

        pool = ProxyPool()
        pool.load_proxies(str(proxy_file))

        # Simulate some state
        pool.blacklist.add("http://old.proxy:80")
        pool.failed_counts["http://old.proxy:80"] = 5
        pool.current_index = 99

        # Reload
        proxy_file.write_text("http://2.2.2.2:80\n")
        pool.load_proxies(str(proxy_file))

        assert pool.blacklist == set()
        assert "http://old.proxy:80" not in pool.failed_counts
        assert pool.current_index == 0
        assert pool.proxies == ["http://2.2.2.2:80"]


class TestGetNextProxy:
    """Tests for async proxy rotation."""

    @pytest.mark.asyncio
    async def test_round_robin_rotation(self, loaded_proxy_pool):
        """Should rotate through proxies in order."""
        pool = loaded_proxy_pool
        first = await pool.get_next_proxy()
        second = await pool.get_next_proxy()
        third = await pool.get_next_proxy()

        # All should be different (assuming 4 proxies loaded)
        assert first != second
        assert second != third

    @pytest.mark.asyncio
    async def test_skips_blacklisted_proxies(self, tmp_path):
        """Should skip over blacklisted proxies."""
        proxy_file = tmp_path / "proxies.txt"
        proxy_file.write_text("http://1.1.1.1:80\nhttp://2.2.2.2:80\n")

        pool = ProxyPool()
        pool.load_proxies(str(proxy_file))

        # Blacklist first proxy
        pool.blacklist.add("http://1.1.1.1:80")

        # Should get second proxy
        proxy = await pool.get_next_proxy()
        assert proxy == "http://2.2.2.2:80"

        # Should still get second proxy (only one available)
        proxy = await pool.get_next_proxy()
        assert proxy == "http://2.2.2.2:80"

    @pytest.mark.asyncio
    async def test_returns_none_when_all_blacklisted(self, tmp_path):
        """Should return None when all proxies are blacklisted."""
        proxy_file = tmp_path / "proxies.txt"
        proxy_file.write_text("http://1.1.1.1:80\nhttp://2.2.2.2:80\n")

        pool = ProxyPool()
        pool.load_proxies(str(proxy_file))

        # Blacklist all
        pool.blacklist.add("http://1.1.1.1:80")
        pool.blacklist.add("http://2.2.2.2:80")

        proxy = await pool.get_next_proxy()
        assert proxy is None

    @pytest.mark.asyncio
    async def test_returns_none_when_empty_pool(self):
        """Should return None when pool is empty."""
        pool = ProxyPool()
        proxy = await pool.get_next_proxy()
        assert proxy is None


class TestMarkProxySuccess:
    """Tests for marking proxies as successful."""

    def test_resets_failure_count_to_zero(self, loaded_proxy_pool):
        """Success should reset failure count."""
        pool = loaded_proxy_pool
        proxy = pool.proxies[0]

        # Simulate some failures
        pool.failed_counts[proxy] = 3

        pool.mark_proxy_success(proxy)
        assert pool.failed_counts[proxy] == 0

    def test_handles_none_proxy(self, proxy_pool):
        """Should not raise on None proxy."""
        pool = proxy_pool
        pool.mark_proxy_success(None)  # Should not raise

    def test_handles_unknown_proxy(self, proxy_pool):
        """Should not raise on unknown proxy."""
        pool = proxy_pool
        pool.mark_proxy_success("http://unknown:80")  # Should not raise


class TestMarkProxyFailed:
    """Tests for marking proxies as failed."""

    def test_increments_failure_count(self, loaded_proxy_pool):
        """Failure should increment failure count."""
        pool = loaded_proxy_pool
        proxy = pool.proxies[0]

        assert pool.failed_counts[proxy] == 0
        pool.mark_proxy_failed(proxy)
        assert pool.failed_counts[proxy] == 1
        pool.mark_proxy_failed(proxy)
        assert pool.failed_counts[proxy] == 2

    def test_blacklists_after_max_failures(self, tmp_path):
        """Should blacklist after max_consecutive_failures."""
        proxy_file = tmp_path / "proxies.txt"
        proxy_file.write_text("http://1.1.1.1:80\n")

        pool = ProxyPool(max_consecutive_failures=3)
        pool.load_proxies(str(proxy_file))
        proxy = pool.proxies[0]

        # Fail 2 times - not blacklisted yet
        pool.mark_proxy_failed(proxy)
        pool.mark_proxy_failed(proxy)
        assert proxy not in pool.blacklist

        # Third failure - should blacklist
        pool.mark_proxy_failed(proxy)
        assert proxy in pool.blacklist

    def test_handles_none_proxy(self, proxy_pool):
        """Should not raise on None proxy."""
        pool = proxy_pool
        pool.mark_proxy_failed(None)  # Should not raise

    def test_handles_unknown_proxy(self, proxy_pool):
        """Should not raise on unknown proxy."""
        pool = proxy_pool
        pool.mark_proxy_failed("http://unknown:80")  # Should not raise


class TestIsSocksProxy:
    """Tests for SOCKS proxy detection."""

    def test_detects_socks4(self, proxy_pool):
        """Should detect socks4:// proxies."""
        assert proxy_pool.is_socks_proxy("socks4://1.2.3.4:1080") is True

    def test_detects_socks5(self, proxy_pool):
        """Should detect socks5:// proxies."""
        assert proxy_pool.is_socks_proxy("socks5://1.2.3.4:1080") is True

    def test_http_is_not_socks(self, proxy_pool):
        """HTTP proxy should not be detected as SOCKS."""
        assert proxy_pool.is_socks_proxy("http://1.2.3.4:80") is False

    def test_https_is_not_socks(self, proxy_pool):
        """HTTPS proxy should not be detected as SOCKS."""
        assert proxy_pool.is_socks_proxy("https://1.2.3.4:443") is False

    def test_none_is_not_socks(self, proxy_pool):
        """None should not be detected as SOCKS."""
        assert proxy_pool.is_socks_proxy(None) is False


class TestGetPoolStats:
    """Tests for pool statistics."""

    def test_returns_correct_counts(self, loaded_proxy_pool):
        """Should return accurate statistics."""
        pool = loaded_proxy_pool
        stats = pool.get_pool_stats()

        assert stats["total_proxies"] == 4
        assert stats["active_proxies"] == 4
        assert stats["blacklisted_proxies"] == 0
        assert stats["using_direct"] is False

    def test_counts_blacklisted_correctly(self, loaded_proxy_pool):
        """Should count blacklisted proxies."""
        pool = loaded_proxy_pool
        pool.blacklist.add(pool.proxies[0])

        stats = pool.get_pool_stats()

        assert stats["total_proxies"] == 4
        assert stats["active_proxies"] == 3
        assert stats["blacklisted_proxies"] == 1
        assert stats["using_direct"] is False

    def test_using_direct_true_when_all_blacklisted(self, loaded_proxy_pool):
        """using_direct should be True when all blacklisted."""
        pool = loaded_proxy_pool
        for proxy in pool.proxies:
            pool.blacklist.add(proxy)

        stats = pool.get_pool_stats()

        assert stats["using_direct"] is True

    def test_using_direct_true_when_empty_pool(self, proxy_pool):
        """using_direct should be True when pool is empty."""
        stats = proxy_pool.get_pool_stats()

        assert stats["total_proxies"] == 0
        assert stats["using_direct"] is True


class TestUserAgents:
    """Tests for User-Agent list and randomization."""

    def test_user_agents_list_has_50_plus_entries(self):
        """USER_AGENTS should have at least 50 entries."""
        assert len(USER_AGENTS) >= 50

    def test_all_user_agents_are_strings(self):
        """All User-Agents should be non-empty strings."""
        assert all(isinstance(ua, str) and len(ua) > 0 for ua in USER_AGENTS)

    def test_user_agents_look_like_browsers(self):
        """User-Agents should contain typical browser identifiers."""
        for ua in USER_AGENTS:
            assert any(
                browser in ua
                for browser in ["Mozilla", "Chrome", "Firefox", "Safari", "Edg"]
            )

    def test_get_random_user_agent_returns_from_list(self, proxy_pool):
        """get_random_user_agent should return a value from USER_AGENTS."""
        ua = proxy_pool.get_random_user_agent()
        assert ua in USER_AGENTS

    def test_get_random_user_agent_varies(self, proxy_pool):
        """get_random_user_agent should return different values over many calls."""
        # Call many times and check we get some variation
        user_agents = {proxy_pool.get_random_user_agent() for _ in range(100)}
        # With 50+ UAs and 100 calls, we should get at least a few different ones
        assert len(user_agents) > 1
