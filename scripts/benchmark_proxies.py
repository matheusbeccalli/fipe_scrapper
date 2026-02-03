"""
Benchmark script to compare proxy vs direct connection performance.
Tests latency and success rate for each proxy in parallel.
Automatically removes failed proxies from the proxy file.

Usage:
    python scripts/benchmark_proxies.py
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncio
import time
import aiohttp
from aiohttp_socks import ProxyConnector
from proxy_manager import ProxyPool
import config

API_URL = "http://veiculos.fipe.org.br/api/veiculos/ConsultarTabelaDeReferencia"
PROXY_FILE_HEADER = """# FIPE Scraper Proxy List
# Supported formats (one proxy per line):
#   ip:port                              - HTTP proxy (no auth)
#   username:password@ip:port            - HTTP proxy with auth
#   http://ip:port                       - HTTP proxy (explicit)
#   http://username:password@ip:port     - HTTP proxy with auth (explicit)
#   socks5://ip:port                     - SOCKS5 proxy
#   socks5://username:password@ip:port   - SOCKS5 proxy with auth
# Lines without protocol prefix default to http://
#
"""
HEADERS = {
    'Content-Type': 'application/x-www-form-urlencoded',
    'Referer': 'http://veiculos.fipe.org.br/',
}
NUM_TESTS = 3  # Number of requests per proxy
MAX_CONCURRENT = 50  # Number of proxies to test in parallel


async def test_direct_connection():
    """Test direct connection (no proxy)."""
    times = []

    async with aiohttp.ClientSession() as session:
        for _ in range(NUM_TESTS):
            start = time.time()
            try:
                async with session.post(API_URL, headers=HEADERS, data={}, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        await resp.json()
                        times.append(time.time() - start)
            except Exception:
                pass
            await asyncio.sleep(0.5)

    return times


async def test_proxy(proxy: str, semaphore: asyncio.Semaphore, progress: dict):
    """Test a single proxy with semaphore for concurrency control."""
    async with semaphore:
        times = []
        errors = []

        try:
            is_socks = proxy.startswith('socks')

            for _ in range(NUM_TESTS):
                start = time.time()
                try:
                    if is_socks:
                        connector = ProxyConnector.from_url(proxy)
                        async with aiohttp.ClientSession(connector=connector) as session:
                            async with session.post(API_URL, headers=HEADERS, data={}, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                                if resp.status == 200:
                                    await resp.json()
                                    times.append(time.time() - start)
                                else:
                                    errors.append(f"HTTP {resp.status}")
                    else:
                        async with aiohttp.ClientSession() as session:
                            async with session.post(API_URL, headers=HEADERS, data={}, proxy=proxy, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                                if resp.status == 200:
                                    await resp.json()
                                    times.append(time.time() - start)
                                else:
                                    errors.append(f"HTTP {resp.status}")
                except Exception as e:
                    errors.append(f"{type(e).__name__}: {str(e)[:80]}")
                await asyncio.sleep(0.1)
        except Exception as e:
            errors.append(f"Setup error: {type(e).__name__}: {str(e)[:80]}")

        # Update progress
        progress['completed'] += 1
        status = "✓" if times else "✗"
        print(f"\r  Progress: {progress['completed']}/{progress['total']} proxies tested [{status}]", end="", flush=True)

        return proxy, times, errors


async def main():
    print("=" * 60)
    print("FIPE API Proxy Benchmark (Parallel)")
    print("=" * 60)
    print(f"Testing {NUM_TESTS} requests per proxy, {MAX_CONCURRENT} concurrent\n")

    # Test direct connection
    print("Testing DIRECT connection...")
    direct_times = await test_direct_connection()

    if direct_times:
        direct_avg = sum(direct_times) / len(direct_times)
        print(f"  ✓ Direct: avg {direct_avg*1000:.0f}ms, {len(direct_times)}/{NUM_TESTS} success")
    else:
        direct_avg = float('inf')
        print(f"  ✗ Direct: all requests failed")

    print()

    # Load proxies
    proxy_pool = ProxyPool(max_consecutive_failures=config.PROXY_CONFIG['max_consecutive_failures'])
    proxy_pool.load_proxies(config.PROXY_CONFIG['proxy_file'])
    if not proxy_pool.proxies:
        print("No proxies found in proxy file!")
        return

    total_proxies = len(proxy_pool.proxies)
    print(f"Testing {total_proxies} proxies in parallel...\n")

    # Create semaphore and progress tracker
    semaphore = asyncio.Semaphore(MAX_CONCURRENT)
    progress = {'completed': 0, 'total': total_proxies}

    # Test all proxies in parallel
    start_time = time.time()
    tasks = [test_proxy(proxy, semaphore, progress) for proxy in proxy_pool.proxies]
    raw_results = await asyncio.gather(*tasks)
    elapsed = time.time() - start_time

    print(f"\n\n  Completed in {elapsed:.1f}s\n")

    # Process results
    results = []
    for proxy, times, errors in raw_results:
        if times:
            avg = sum(times) / len(times)
            success_rate = len(times) / NUM_TESTS * 100
            results.append((proxy, avg, success_rate, errors))
        else:
            results.append((proxy, float('inf'), 0, errors))

    # Summary
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)

    working_proxies = [(p, t, s, e) for p, t, s, e in results if t != float('inf')]
    failed_proxies = [(p, t, s, e) for p, t, s, e in results if t == float('inf')]

    if direct_avg != float('inf'):
        print(f"\nDirect connection: {direct_avg*1000:.0f}ms average")
    else:
        print(f"\nDirect connection: FAILED")
    print(f"Working proxies: {len(working_proxies)}/{len(results)}")
    print(f"Failed proxies: {len(failed_proxies)}/{len(results)}")

    if working_proxies:
        # Sort by latency
        working_proxies.sort(key=lambda x: x[1])

        print(f"\nFastest proxies:")
        for proxy, avg, success, _ in working_proxies[:5]:
            if direct_avg != float('inf'):
                speed = "FASTER" if avg < direct_avg else "SLOWER"
                print(f"  {avg*1000:.0f}ms ({success:.0f}% success) - {proxy[:50]}... [{speed}]")
            else:
                print(f"  {avg*1000:.0f}ms ({success:.0f}% success) - {proxy[:50]}...")

        overall_avg = sum(t for _, t, _, _ in working_proxies) / len(working_proxies)

        print(f"\nOverall proxy average: {overall_avg*1000:.0f}ms")

        if direct_avg != float('inf'):
            faster_than_direct = sum(1 for _, t, _, _ in working_proxies if t < direct_avg)
            print(f"Proxies faster than direct: {faster_than_direct}/{len(working_proxies)}")

            if overall_avg > direct_avg * 1.5:
                print("\n⚠️  WARNING: Proxies are significantly slower than direct connection!")
                print("   Consider using only the fastest proxies or disabling proxy rotation.")

    # Show error summary for failed proxies
    if failed_proxies:
        print(f"\n{'=' * 60}")
        print("FAILED PROXY ERRORS (first 10)")
        print("=" * 60)

        # Count error types
        error_counts = {}
        for _, _, _, errors in failed_proxies:
            for err in errors:
                # Get error type (first part before colon)
                err_type = err.split(':')[0] if ':' in err else err
                error_counts[err_type] = error_counts.get(err_type, 0) + 1

        print("\nError type summary:")
        for err_type, count in sorted(error_counts.items(), key=lambda x: -x[1]):
            print(f"  {err_type}: {count} occurrences")

        print("\nSample errors (first 10 proxies):")
        for proxy, _, _, errors in failed_proxies[:10]:
            proxy_short = proxy[:60] + "..." if len(proxy) > 60 else proxy
            if errors:
                print(f"  {proxy_short}")
                print(f"    → {errors[0]}")
            else:
                print(f"  {proxy_short}: No error captured")

    # Remove failed proxies from file
    if failed_proxies:
        print(f"\n{'=' * 60}")
        print(f"CLEANUP: {len(failed_proxies)} failed proxies will be removed")
        print("=" * 60)

        proxy_file = config.PROXY_CONFIG['proxy_file']
        working_proxy_urls = [p for p, _, _, _ in working_proxies]

        # Write working proxies back to file
        with open(proxy_file, 'w') as f:
            f.write(PROXY_FILE_HEADER)
            for proxy in working_proxy_urls:
                f.write(f"{proxy}\n")

        print(f"✓ Removed {len(failed_proxies)} failed proxies from {proxy_file}")
        print(f"✓ {len(working_proxy_urls)} working proxies remain")
    else:
        print(f"\n✓ All {len(results)} proxies are working!")


if __name__ == "__main__":
    asyncio.run(main())
