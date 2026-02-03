# Proxy Auto-Disable Design

## Problem

When proxies get repeatedly blocked by Cloudflare (403 errors), the scraper wastes time retrying with dead proxies. We need to:
1. Automatically disable workers with blocked proxies
2. Remove blocked proxies from `proxies.txt`
3. Ensure in-flight requests aren't lost when a worker is disabled

## Design Decisions

### Failure Tracking
- `consecutive_failures` counter per worker, reset on 200 response
- Both 403 and 503 increment the counter and `requests_failed`
- Threshold via `PROXY_MAX_FAILURES` env var (default: 5)
- Worker sets `is_running = False` when threshold hit

### File Removal
- Callback `_on_worker_disabled(proxy)` removes proxy from file
- `_removed_proxies` set prevents duplicate removal attempts
- HTTP proxy format matching only
- Empty lines stripped on rewrite
- Race condition on concurrent writes accepted (unlikely, non-critical)

### Retry on Worker Disable
- When worker is disabled mid-request, requeue the work item
- Another active worker picks it up and retries
- If no active workers remain, return `None` (existing timeout handles it)

## Implementation Tasks

1. Fix: Add `requests_failed += 1` to 503 handling
2. Feature: Requeue work item when worker disabled (if other workers active)

## Testing

- Worker disables after N consecutive 403s
- Counter resets on successful request
- Proxy removed from file on disable
- Work item requeued when worker disabled
- No requeue when all workers disabled
