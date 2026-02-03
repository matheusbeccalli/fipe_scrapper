"""
Cloudflare bypass module using cloudscraper25.

This module provides Cloudflare bypass capabilities by obtaining session cookies
that can be shared with aiohttp workers.
"""

import asyncio
import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Dict, Optional, List
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

# Import cloudscraper25 with fallback
try:
    import cloudscraper25 as cloudscraper
    CLOUDSCRAPER_AVAILABLE = True
except ImportError:
    CLOUDSCRAPER_AVAILABLE = False
    logger.warning("cloudscraper25 not installed. Run: pip install cloudscraper25")


@dataclass
class CloudflareSession:
    """Holds Cloudflare bypass cookies and metadata."""
    cookies: Dict[str, str] = field(default_factory=dict)
    user_agent: str = ""
    obtained_at: float = 0.0
    proxy: Optional[str] = None
    
    @property
    def age_seconds(self) -> float:
        """Return age of session in seconds."""
        return time.time() - self.obtained_at
    
    def is_expired(self, max_age_seconds: float = 300) -> bool:
        """Check if session is expired (default 5 minutes)."""
        return self.age_seconds > max_age_seconds


class CloudflareBypass:
    """
    Manages Cloudflare bypass sessions using cloudscraper25.
    
    This class obtains Cloudflare clearance cookies that can be reused
    in aiohttp sessions to bypass Cloudflare protection.
    
    Usage:
        bypass = CloudflareBypass(target_url="http://veiculos.fipe.org.br/api/veiculos")
        await bypass.start()
        
        # Get cookies for aiohttp
        cookies, user_agent = bypass.get_session()
        
        # Use in aiohttp
        async with aiohttp.ClientSession(cookies=cookies) as session:
            headers = {"User-Agent": user_agent}
            async with session.get(url, headers=headers) as response:
                ...
        
        await bypass.stop()
    """
    
    def __init__(
        self,
        target_url: str,
        proxies: Optional[List[str]] = None,
        refresh_interval: float = 240.0,  # Refresh every 4 minutes (before 5min expiry)
        max_sessions: int = 5,  # Keep multiple sessions for redundancy
    ):
        """
        Initialize Cloudflare bypass manager.
        
        Args:
            target_url: The URL to obtain Cloudflare cookies for
            proxies: Optional list of proxy URLs to use for obtaining sessions
            refresh_interval: How often to refresh sessions (seconds)
            max_sessions: Maximum number of sessions to maintain
        """
        self.target_url = target_url
        self.proxies = proxies or []
        self.refresh_interval = refresh_interval
        self.max_sessions = max_sessions
        
        self._sessions: List[CloudflareSession] = []
        self._lock = threading.Lock()
        self._executor = ThreadPoolExecutor(max_workers=3, thread_name_prefix="cf_bypass")
        self._refresh_task: Optional[asyncio.Task] = None
        self._running = False
        self._session_index = 0
    
    def _obtain_session_sync(self, proxy: Optional[str] = None) -> Optional[CloudflareSession]:
        """
        Obtain Cloudflare bypass session synchronously (runs in thread).
        
        This method uses cloudscraper25 to solve Cloudflare challenges and
        obtain clearance cookies.
        """
        if not CLOUDSCRAPER_AVAILABLE:
            logger.error("cloudscraper25 not available")
            return None
        
        try:
            # Create scraper with browser emulation
            scraper = cloudscraper.create_scraper(
                browser={
                    'browser': 'chrome',
                    'platform': 'windows',
                    'mobile': False
                }
            )
            
            # Set up proxy if provided
            proxies_dict = None
            if proxy:
                proxies_dict = {
                    "http": proxy,
                    "https": proxy
                }
            
            logger.info(f"Obtaining Cloudflare session (proxy: {proxy or 'direct'})...")
            
            # Make request to trigger Cloudflare challenge
            response = scraper.get(
                self.target_url,
                proxies=proxies_dict,
                timeout=30
            )
            
            if response.status_code == 200:
                # Extract cookies and user agent
                cookies = dict(scraper.cookies)
                user_agent = scraper.headers.get('User-Agent', '')
                
                session = CloudflareSession(
                    cookies=cookies,
                    user_agent=user_agent,
                    obtained_at=time.time(),
                    proxy=proxy
                )
                
                logger.info(f"Successfully obtained Cloudflare session with {len(cookies)} cookies")
                return session
            else:
                logger.warning(f"Failed to obtain session: HTTP {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Error obtaining Cloudflare session: {e}")
            return None
    
    async def obtain_session(self, proxy: Optional[str] = None) -> Optional[CloudflareSession]:
        """Obtain Cloudflare session asynchronously."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self._executor,
            self._obtain_session_sync,
            proxy
        )
    
    async def _refresh_sessions(self):
        """Background task to refresh sessions periodically."""
        while self._running:
            try:
                # Obtain new sessions
                proxies_to_use = self.proxies[:self.max_sessions] if self.proxies else [None]
                
                tasks = [
                    self.obtain_session(proxy)
                    for proxy in proxies_to_use
                ]
                
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                new_sessions = []
                for result in results:
                    if isinstance(result, CloudflareSession):
                        new_sessions.append(result)
                    elif isinstance(result, Exception):
                        logger.error(f"Session refresh error: {result}")
                
                if new_sessions:
                    with self._lock:
                        self._sessions = new_sessions
                        logger.info(f"Refreshed {len(new_sessions)} Cloudflare sessions")
                else:
                    logger.warning("No valid sessions obtained during refresh")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in session refresh: {e}")
            
            # Wait for next refresh
            await asyncio.sleep(self.refresh_interval)
    
    async def start(self):
        """Start the Cloudflare bypass manager."""
        if self._running:
            return
        
        if not CLOUDSCRAPER_AVAILABLE:
            logger.error("Cannot start: cloudscraper25 not installed")
            return
        
        self._running = True
        
        # Obtain initial sessions
        logger.info("Obtaining initial Cloudflare bypass sessions...")
        proxies_to_use = self.proxies[:self.max_sessions] if self.proxies else [None]
        
        tasks = [
            self.obtain_session(proxy)
            for proxy in proxies_to_use
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in results:
            if isinstance(result, CloudflareSession):
                self._sessions.append(result)
        
        if not self._sessions:
            logger.warning("Failed to obtain any initial Cloudflare sessions")
        else:
            logger.info(f"Obtained {len(self._sessions)} initial sessions")
        
        # Start background refresh task
        self._refresh_task = asyncio.create_task(self._refresh_sessions())
    
    async def stop(self):
        """Stop the Cloudflare bypass manager."""
        self._running = False
        
        if self._refresh_task:
            self._refresh_task.cancel()
            try:
                await self._refresh_task
            except asyncio.CancelledError:
                pass
        
        self._executor.shutdown(wait=False)
        logger.info("Cloudflare bypass manager stopped")
    
    def get_session(self) -> tuple[Dict[str, str], str]:
        """
        Get cookies and user-agent for use with aiohttp.
        
        Returns:
            Tuple of (cookies_dict, user_agent_string)
        """
        with self._lock:
            if not self._sessions:
                return {}, ""
            
            # Round-robin through sessions
            self._session_index = (self._session_index + 1) % len(self._sessions)
            session = self._sessions[self._session_index]
            
            return session.cookies.copy(), session.user_agent
    
    def has_valid_session(self) -> bool:
        """Check if we have at least one valid session."""
        with self._lock:
            return any(not s.is_expired() for s in self._sessions)
    
    @property
    def session_count(self) -> int:
        """Return number of active sessions."""
        with self._lock:
            return len(self._sessions)


# Global instance for convenience
_bypass_instance: Optional[CloudflareBypass] = None


async def get_cloudflare_bypass(
    target_url: str = "http://veiculos.fipe.org.br/api/veiculos",
    proxies: Optional[List[str]] = None,
) -> CloudflareBypass:
    """
    Get or create the global Cloudflare bypass instance.
    
    This is a convenience function for simple usage patterns.
    """
    global _bypass_instance
    
    if _bypass_instance is None:
        _bypass_instance = CloudflareBypass(target_url=target_url, proxies=proxies)
        await _bypass_instance.start()
    
    return _bypass_instance


async def shutdown_cloudflare_bypass():
    """Shutdown the global Cloudflare bypass instance."""
    global _bypass_instance
    
    if _bypass_instance:
        await _bypass_instance.stop()
        _bypass_instance = None
