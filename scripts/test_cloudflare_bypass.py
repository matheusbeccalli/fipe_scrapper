#!/usr/bin/env python3
"""
Test script for Cloudflare bypass functionality.

Tests:
1. Direct connection (no bypass) - to see if Cloudflare is blocking
2. Connection with cloudscraper25 bypass
3. Connection through proxy with bypass cookies

Usage:
    python scripts/test_cloudflare_bypass.py
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncio
import time
import aiohttp
from aiohttp_socks import ProxyConnector

# Check dependencies
try:
    import cloudscraper25 as cloudscraper
    CLOUDSCRAPER_AVAILABLE = True
except ImportError:
    CLOUDSCRAPER_AVAILABLE = False
    print("WARNING: cloudscraper25 not installed. Run: pip install cloudscraper25")

import config
from proxy_manager import ProxyPool

API_BASE_URL = "http://veiculos.fipe.org.br/api/veiculos"
TEST_ENDPOINT = "/ConsultarTabelaDeReferencia"
TEST_URL = f"{API_BASE_URL}{TEST_ENDPOINT}"

HEADERS = {
    'Content-Type': 'application/x-www-form-urlencoded',
    'Referer': 'http://veiculos.fipe.org.br/',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
}


def print_header(title: str):
    print(f"\n{'=' * 60}")
    print(title)
    print('=' * 60)


async def test_direct_connection():
    """Test 1: Direct connection without any bypass."""
    print_header("TEST 1: Direct Connection (No Bypass)")
    
    async with aiohttp.ClientSession() as session:
        try:
            start = time.time()
            async with session.post(
                TEST_URL, 
                headers=HEADERS, 
                data={},
                timeout=aiohttp.ClientTimeout(total=15)
            ) as response:
                elapsed = time.time() - start
                
                if response.status == 200:
                    data = await response.json()
                    print(f"  ✓ SUCCESS: HTTP {response.status} in {elapsed*1000:.0f}ms")
                    print(f"    Response: {len(data)} reference months found")
                    return True, None
                elif response.status == 403:
                    print(f"  ✗ BLOCKED: HTTP 403 - Cloudflare is blocking (in {elapsed*1000:.0f}ms)")
                    return False, "Cloudflare 403"
                elif response.status == 503:
                    text = await response.text()
                    if "cloudflare" in text.lower() or "challenge" in text.lower():
                        print(f"  ✗ CHALLENGE: HTTP 503 - Cloudflare challenge page")
                        return False, "Cloudflare challenge"
                    print(f"  ✗ ERROR: HTTP 503 - Service unavailable")
                    return False, "503 Service Unavailable"
                else:
                    print(f"  ? UNKNOWN: HTTP {response.status} in {elapsed*1000:.0f}ms")
                    return False, f"HTTP {response.status}"
                    
        except Exception as e:
            print(f"  ✗ ERROR: {type(e).__name__}: {e}")
            return False, str(e)


def test_cloudscraper_direct():
    """Test 2: cloudscraper25 direct (synchronous)."""
    print_header("TEST 2: Cloudscraper25 Direct (No Proxy)")
    
    if not CLOUDSCRAPER_AVAILABLE:
        print("  ✗ SKIPPED: cloudscraper25 not installed")
        return False, None, None
    
    try:
        scraper = cloudscraper.create_scraper(
            browser={
                'browser': 'chrome',
                'platform': 'windows',
                'mobile': False
            }
        )
        
        print("  Creating scraper session...")
        start = time.time()
        
        response = scraper.post(TEST_URL, data={}, timeout=30)
        elapsed = time.time() - start
        
        if response.status_code == 200:
            data = response.json()
            cookies = dict(scraper.cookies)
            user_agent = scraper.headers.get('User-Agent', '')
            
            print(f"  ✓ SUCCESS: HTTP {response.status_code} in {elapsed*1000:.0f}ms")
            print(f"    Response: {len(data)} reference months found")
            print(f"    Cookies obtained: {len(cookies)}")
            for name, value in cookies.items():
                print(f"      - {name}: {value[:40]}...")
            
            return True, cookies, user_agent
        else:
            print(f"  ✗ FAILED: HTTP {response.status_code}")
            return False, None, None
            
    except Exception as e:
        print(f"  ✗ ERROR: {type(e).__name__}: {e}")
        return False, None, None


async def test_aiohttp_with_cookies(cookies: dict, user_agent: str):
    """Test 3: aiohttp with Cloudflare bypass cookies."""
    print_header("TEST 3: aiohttp with Bypass Cookies")
    
    if not cookies:
        print("  ✗ SKIPPED: No cookies available")
        return False
    
    # Build cookie header
    cookie_header = "; ".join(f"{k}={v}" for k, v in cookies.items())
    headers = HEADERS.copy()
    headers['Cookie'] = cookie_header
    headers['User-Agent'] = user_agent
    
    async with aiohttp.ClientSession() as session:
        try:
            start = time.time()
            async with session.post(
                TEST_URL,
                headers=headers,
                data={},
                timeout=aiohttp.ClientTimeout(total=15)
            ) as response:
                elapsed = time.time() - start
                
                if response.status == 200:
                    data = await response.json()
                    print(f"  ✓ SUCCESS: HTTP {response.status} in {elapsed*1000:.0f}ms")
                    print(f"    Response: {len(data)} reference months found")
                    return True
                else:
                    print(f"  ✗ FAILED: HTTP {response.status}")
                    return False
                    
        except Exception as e:
            print(f"  ✗ ERROR: {type(e).__name__}: {e}")
            return False


async def test_proxy_with_cookies(proxy: str, cookies: dict, user_agent: str):
    """Test 4: Proxy + Cloudflare bypass cookies."""
    print_header(f"TEST 4: Proxy with Bypass Cookies")
    print(f"  Proxy: {proxy[:60]}...")
    
    if not cookies:
        print("  ✗ SKIPPED: No cookies available")
        return False
    
    cookie_header = "; ".join(f"{k}={v}" for k, v in cookies.items())
    headers = HEADERS.copy()
    headers['Cookie'] = cookie_header
    headers['User-Agent'] = user_agent
    
    is_socks = proxy.startswith(('socks4://', 'socks5://'))
    
    try:
        start = time.time()
        
        if is_socks:
            connector = ProxyConnector.from_url(proxy)
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.post(
                    TEST_URL,
                    headers=headers,
                    data={},
                    timeout=aiohttp.ClientTimeout(total=20)
                ) as response:
                    elapsed = time.time() - start
                    
                    if response.status == 200:
                        data = await response.json()
                        print(f"  ✓ SUCCESS: HTTP {response.status} in {elapsed*1000:.0f}ms")
                        print(f"    Response: {len(data)} reference months found")
                        return True
                    else:
                        print(f"  ✗ FAILED: HTTP {response.status}")
                        return False
        else:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    TEST_URL,
                    headers=headers,
                    data={},
                    proxy=proxy,
                    timeout=aiohttp.ClientTimeout(total=20)
                ) as response:
                    elapsed = time.time() - start
                    
                    if response.status == 200:
                        data = await response.json()
                        print(f"  ✓ SUCCESS: HTTP {response.status} in {elapsed*1000:.0f}ms")
                        print(f"    Response: {len(data)} reference months found")
                        return True
                    else:
                        print(f"  ✗ FAILED: HTTP {response.status}")
                        return False
                        
    except Exception as e:
        print(f"  ✗ ERROR: {type(e).__name__}: {e}")
        return False


def test_cloudscraper_with_proxy(proxy: str):
    """Test 5: cloudscraper25 through a proxy."""
    print_header(f"TEST 5: Cloudscraper25 with Proxy")
    print(f"  Proxy: {proxy[:60]}...")
    
    if not CLOUDSCRAPER_AVAILABLE:
        print("  ✗ SKIPPED: cloudscraper25 not installed")
        return False, None, None
    
    try:
        scraper = cloudscraper.create_scraper(
            browser={
                'browser': 'chrome',
                'platform': 'windows',
                'mobile': False
            }
        )
        
        proxies = {
            "http": proxy,
            "https": proxy
        }
        
        print("  Creating scraper session through proxy...")
        start = time.time()
        
        response = scraper.post(TEST_URL, data={}, proxies=proxies, timeout=30)
        elapsed = time.time() - start
        
        if response.status_code == 200:
            data = response.json()
            cookies = dict(scraper.cookies)
            user_agent = scraper.headers.get('User-Agent', '')
            
            print(f"  ✓ SUCCESS: HTTP {response.status_code} in {elapsed*1000:.0f}ms")
            print(f"    Response: {len(data)} reference months found")
            print(f"    Cookies obtained: {len(cookies)}")
            
            return True, cookies, user_agent
        else:
            print(f"  ✗ FAILED: HTTP {response.status_code}")
            return False, None, None
            
    except Exception as e:
        print(f"  ✗ ERROR: {type(e).__name__}: {e}")
        return False, None, None


async def main():
    print("=" * 60)
    print("CLOUDFLARE BYPASS TEST SUITE")
    print("=" * 60)
    print(f"Target: {TEST_URL}")
    print(f"cloudscraper25 available: {CLOUDSCRAPER_AVAILABLE}")
    
    results = {}
    
    # Test 1: Direct connection
    success, error = await test_direct_connection()
    results['direct'] = success
    
    # Test 2: cloudscraper direct
    success, cookies, user_agent = test_cloudscraper_direct()
    results['cloudscraper_direct'] = success
    
    # Test 3: aiohttp with cookies
    if cookies:
        success = await test_aiohttp_with_cookies(cookies, user_agent)
        results['aiohttp_with_cookies'] = success
    else:
        results['aiohttp_with_cookies'] = None
    
    # Load a proxy for testing
    proxy = None
    proxy_pool = ProxyPool(max_consecutive_failures=5)
    proxy_count = proxy_pool.load_proxies(config.PROXY_CONFIG.get('proxy_file', 'proxies.txt'))
    
    if proxy_count > 0:
        proxy = proxy_pool.proxies[0]
        
        # Test 4: Proxy with bypass cookies
        if cookies:
            success = await test_proxy_with_cookies(proxy, cookies, user_agent)
            results['proxy_with_cookies'] = success
        else:
            results['proxy_with_cookies'] = None
        
        # Test 5: cloudscraper through proxy
        success, proxy_cookies, proxy_ua = test_cloudscraper_with_proxy(proxy)
        results['cloudscraper_proxy'] = success
    else:
        print("\n  No proxies available for proxy tests")
        results['proxy_with_cookies'] = None
        results['cloudscraper_proxy'] = None
    
    # Summary
    print_header("SUMMARY")
    
    status_map = {
        True: "✓ PASS",
        False: "✗ FAIL",
        None: "- SKIP"
    }
    
    print(f"  Direct connection:        {status_map[results.get('direct')]}")
    print(f"  Cloudscraper direct:      {status_map[results.get('cloudscraper_direct')]}")
    print(f"  aiohttp + cookies:        {status_map[results.get('aiohttp_with_cookies')]}")
    print(f"  Proxy + cookies:          {status_map[results.get('proxy_with_cookies')]}")
    print(f"  Cloudscraper + proxy:     {status_map[results.get('cloudscraper_proxy')]}")
    
    # Recommendations
    print_header("RECOMMENDATIONS")
    
    if results.get('direct'):
        print("  Cloudflare is NOT currently blocking direct connections.")
        print("  The bypass may not be needed right now.")
    elif results.get('cloudscraper_direct') and results.get('aiohttp_with_cookies'):
        print("  ✓ Cloudflare bypass is WORKING!")
        print("  Cookies obtained from cloudscraper can be used with aiohttp.")
    elif results.get('cloudscraper_direct'):
        print("  Cloudscraper works but cookie reuse failed.")
        print("  Consider using cloudscraper directly for each request.")
    else:
        print("  ✗ Cloudflare bypass is NOT working.")
        print("  Consider using FlareSolverr or browser automation.")
    
    print()


if __name__ == "__main__":
    asyncio.run(main())
