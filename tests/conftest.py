"""Shared fixtures for FIPE scraper tests."""

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
    proxy_file.write_text(
        "http://1.1.1.1:80\n"
        "http://2.2.2.2:80\n"
        "socks5://3.3.3.3:1080\n"
        "4.4.4.4:80\n"
    )
    pool = ProxyPool()
    pool.load_proxies(str(proxy_file))
    return pool
