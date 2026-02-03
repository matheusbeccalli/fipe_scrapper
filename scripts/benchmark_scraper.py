"""
Benchmark script to compare scraper performance between versions.

Measures real-world throughput by making actual API requests.
- Current version: Uses ProxyWorkerPool with proxies
- Old version: Uses semaphore with direct connections

Usage:
    python scripts/benchmark_scraper.py
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncio
import time
from typing import Dict, List

# Detect which version we're running
try:
    from proxy_manager import ProxyWorkerPool
    HAS_WORKER_POOL = True
except ImportError:
    HAS_WORKER_POOL = False

import config
from fipe_api_scraper import FIPEAPIScraper


async def run_benchmark(num_months: int = 5, num_brands_per_month: int = 10):
    """
    Run benchmark by fetching real data from FIPE API.

    Args:
        num_months: Number of months to fetch brands for
        num_brands_per_month: Number of brands to fetch models for (per month)
    """
    print("=" * 70)
    print("FIPE SCRAPER PERFORMANCE BENCHMARK")
    print("=" * 70)

    # Detect version
    if HAS_WORKER_POOL:
        print(f"Version: CURRENT (Worker Pool Architecture)")
        print(f"Proxy file: {config.PROXY_CONFIG.get('proxy_file', 'N/A')}")
    else:
        print(f"Version: OLD (Semaphore-based)")

    print(f"\nWorkload: {num_months} months × {num_brands_per_month} brands = ~{num_months * num_brands_per_month * 2} requests")
    print("-" * 70)

    # Initialize scraper
    if HAS_WORKER_POOL:
        # Current version: no args, concurrency managed by worker pool
        scraper = FIPEAPIScraper()
    else:
        # Old version: uses max_concurrent_requests arg
        scraper = FIPEAPIScraper(max_concurrent_requests=10)

    results: Dict[str, float] = {}

    # Phase 1: Fetch reference months
    print("\n[Phase 1] Fetching reference months...")
    start = time.perf_counter()

    async with __import__('aiohttp').ClientSession() as session:
        # Start worker pool if available
        if HAS_WORKER_POOL and hasattr(scraper, 'worker_pool') and scraper.worker_pool:
            await scraper.worker_pool.start()

        try:
            months = await scraper.get_reference_months(session)
            results['phase1_time'] = time.perf_counter() - start
            results['months_fetched'] = len(months) if months else 0
            print(f"  ✓ Fetched {results['months_fetched']} months in {results['phase1_time']:.2f}s")

            if not months:
                print("  ✗ Failed to fetch months, aborting benchmark")
                return

            # Phase 2: Fetch brands for N months (concurrent)
            print(f"\n[Phase 2] Fetching brands for {num_months} months...")
            start = time.perf_counter()

            test_months = months[:num_months]
            brand_tasks = [scraper.get_brands(session, m['Codigo']) for m in test_months]
            brand_results = await asyncio.gather(*brand_tasks)

            results['phase2_time'] = time.perf_counter() - start
            results['brand_requests'] = num_months
            total_brands = sum(len(b) if b else 0 for b in brand_results)
            results['brands_fetched'] = total_brands
            print(f"  ✓ Fetched {total_brands} brands in {results['phase2_time']:.2f}s")
            print(f"    Throughput: {num_months / results['phase2_time']:.1f} requests/sec")

            # Phase 3: Fetch models for N brands per month (more concurrent requests)
            print(f"\n[Phase 3] Fetching models for {num_brands_per_month} brands × {num_months} months...")
            start = time.perf_counter()

            model_tasks = []
            for i, month in enumerate(test_months):
                brands = brand_results[i]
                if brands:
                    for brand in brands[:num_brands_per_month]:
                        model_tasks.append(
                            scraper.get_models(session, month['Codigo'], brand['Value'])
                        )

            model_results = await asyncio.gather(*model_tasks)

            results['phase3_time'] = time.perf_counter() - start
            results['model_requests'] = len(model_tasks)
            total_models = sum(len(m.get('Modelos', [])) if m else 0 for m in model_results)
            results['models_fetched'] = total_models
            print(f"  ✓ Fetched {total_models} models in {results['phase3_time']:.2f}s")
            print(f"    Throughput: {len(model_tasks) / results['phase3_time']:.1f} requests/sec")

        finally:
            # Stop worker pool if available
            if HAS_WORKER_POOL and hasattr(scraper, 'worker_pool') and scraper.worker_pool:
                await scraper.worker_pool.stop()

    # Summary
    total_requests = 1 + results['brand_requests'] + results['model_requests']
    total_time = results['phase1_time'] + results['phase2_time'] + results['phase3_time']

    print("\n" + "=" * 70)
    print("BENCHMARK RESULTS")
    print("=" * 70)
    print(f"Version:           {'CURRENT (Worker Pool)' if HAS_WORKER_POOL else 'OLD (Semaphore)'}")
    print(f"Total requests:    {total_requests}")
    print(f"Total time:        {total_time:.2f}s")
    print(f"Overall throughput:{total_requests / total_time:.1f} requests/sec")
    print("-" * 70)
    print(f"Phase 1 (months):  {results['phase1_time']:.2f}s")
    print(f"Phase 2 (brands):  {results['phase2_time']:.2f}s ({results['brand_requests'] / results['phase2_time']:.1f} req/s)")
    print(f"Phase 3 (models):  {results['phase3_time']:.2f}s ({results['model_requests'] / results['phase3_time']:.1f} req/s)")
    print("=" * 70)

    # Scraper stats
    print("\nScraper Statistics:")
    print(f"  Total requests:    {scraper.stats['total_requests']}")
    print(f"  Successful:        {scraper.stats['successful_requests']}")
    print(f"  Failed:            {scraper.stats['failed_requests']}")
    print(f"  Rate limit hits:   {scraper.stats['rate_limit_hits']}")
    print(f"  Retries:           {scraper.stats['retries']}")

    if HAS_WORKER_POOL and hasattr(scraper, 'worker_pool') and scraper.worker_pool:
        stats = scraper.worker_pool.get_stats()
        print(f"\nWorker Pool Statistics:")
        print(f"  Workers:           {stats['workers']}")
        print(f"  Completed:         {stats['requests_completed']}")
        print(f"  Failed:            {stats['requests_failed']}")


def main():
    # Parse optional arguments
    num_months = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    num_brands = int(sys.argv[2]) if len(sys.argv) > 2 else 10

    print(f"\nStarting benchmark with {num_months} months, {num_brands} brands per month\n")
    asyncio.run(run_benchmark(num_months, num_brands))


if __name__ == "__main__":
    main()
