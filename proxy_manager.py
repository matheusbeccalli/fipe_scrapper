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
