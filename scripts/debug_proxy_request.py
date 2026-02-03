"""
Debug script to compare what headers/data are sent via proxy vs direct connection.
Uses httpbin.org to echo back request details.

Usage:
    python scripts/debug_proxy_request.py
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncio
import aiohttp
from aiohttp_socks import ProxyConnector
import json

# httpbin.org echoes back request details
HTTPBIN_URL = "https://httpbin.org/post"

# Same headers we use for FIPE API
FIPE_HEADERS = {
    'Content-Type': 'application/x-www-form-urlencoded',
    'Referer': 'http://veiculos.fipe.org.br/',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
}


async def test_request(proxy: str = None, label: str = ""):
    """Make a request and return the echoed details."""
    print(f"\n{'='*60}")
    print(f"Testing: {label}")
    print(f"{'='*60}")

    try:
        is_socks = proxy and proxy.startswith('socks')

        if is_socks:
            connector = ProxyConnector.from_url(proxy)
            session = aiohttp.ClientSession(connector=connector)
        else:
            session = aiohttp.ClientSession()

        async with session:
            kwargs = {
                'headers': FIPE_HEADERS,
                'data': {'test': 'data'},
                'timeout': aiohttp.ClientTimeout(total=15)
            }

            if proxy and not is_socks:
                kwargs['proxy'] = proxy

            async with session.post(HTTPBIN_URL, **kwargs) as resp:
                print(f"Status: {resp.status}")

                if resp.status == 200:
                    result = await resp.json()

                    print(f"\nOrigin IP: {result.get('origin', 'unknown')}")

                    print(f"\nHeaders received by server:")
                    for key, value in sorted(result.get('headers', {}).items()):
                        print(f"  {key}: {value}")

                    print(f"\nForm data received:")
                    for key, value in result.get('form', {}).items():
                        print(f"  {key}: {value}")

                    return result
                else:
                    text = await resp.text()
                    print(f"Error response: {text[:500]}")
                    return None

    except Exception as e:
        print(f"Error: {type(e).__name__}: {e}")
        return None


async def test_fipe_direct_vs_proxy(proxy: str):
    """Test actual FIPE API endpoint to compare responses."""
    fipe_url = "http://veiculos.fipe.org.br/api/veiculos/ConsultarTabelaDeReferencia"

    print(f"\n{'='*60}")
    print("Testing actual FIPE API")
    print(f"{'='*60}")

    # Direct
    print("\n--- DIRECT ---")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(fipe_url, headers=FIPE_HEADERS, data={},
                                   timeout=aiohttp.ClientTimeout(total=10)) as resp:
                print(f"Status: {resp.status}")
                if resp.status == 200:
                    data = await resp.json()
                    print(f"Response: {len(data)} items")
                else:
                    print(f"Response: {await resp.text()[:200]}")
    except Exception as e:
        print(f"Error: {type(e).__name__}: {e}")

    # Via proxy
    print("\n--- VIA PROXY ---")
    try:
        is_socks = proxy.startswith('socks')

        if is_socks:
            connector = ProxyConnector.from_url(proxy)
            session = aiohttp.ClientSession(connector=connector)
        else:
            session = aiohttp.ClientSession()

        async with session:
            kwargs = {
                'headers': FIPE_HEADERS,
                'data': {},
                'timeout': aiohttp.ClientTimeout(total=15)
            }
            if not is_socks:
                kwargs['proxy'] = proxy

            async with session.post(fipe_url, **kwargs) as resp:
                print(f"Status: {resp.status}")
                text = await resp.text()
                print(f"Response: {text[:300]}")

                # Show response headers
                print(f"\nResponse headers:")
                for key, value in resp.headers.items():
                    print(f"  {key}: {value}")

    except Exception as e:
        print(f"Error: {type(e).__name__}: {e}")


async def main():
    # Load first proxy from file
    proxy = None
    try:
        with open('proxies.txt', 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    if not line.startswith(('http://', 'https://', 'socks')):
                        line = f'http://{line}'
                    proxy = line
                    break
    except FileNotFoundError:
        pass

    if not proxy:
        print("No proxy found in proxies.txt")
        print("Add at least one proxy to test")
        return

    print(f"Using proxy: {proxy[:70]}...")

    # Test with httpbin to see what's being sent
    print("\n" + "="*60)
    print("PART 1: Compare request details via httpbin.org")
    print("="*60)

    direct_result = await test_request(None, "DIRECT CONNECTION")
    proxy_result = await test_request(proxy, f"VIA PROXY")

    # Compare
    if direct_result and proxy_result:
        print(f"\n{'='*60}")
        print("COMPARISON")
        print(f"{'='*60}")

        direct_headers = direct_result.get('headers', {})
        proxy_headers = proxy_result.get('headers', {})

        all_keys = set(direct_headers.keys()) | set(proxy_headers.keys())

        print("\nHeader differences:")
        for key in sorted(all_keys):
            direct_val = direct_headers.get(key, '<missing>')
            proxy_val = proxy_headers.get(key, '<missing>')
            if direct_val != proxy_val:
                print(f"  {key}:")
                print(f"    Direct: {direct_val}")
                print(f"    Proxy:  {proxy_val}")

        print(f"\nIP addresses:")
        print(f"  Direct: {direct_result.get('origin', 'unknown')}")
        print(f"  Proxy:  {proxy_result.get('origin', 'unknown')}")

    # Test actual FIPE API
    print("\n" + "="*60)
    print("PART 2: Test actual FIPE API endpoint")
    print("="*60)

    await test_fipe_direct_vs_proxy(proxy)


if __name__ == "__main__":
    asyncio.run(main())
