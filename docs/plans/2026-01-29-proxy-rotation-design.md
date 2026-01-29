# Proxy Rotation Design

## Overview

Add proxy rotation capability to the FIPE scraper to avoid rate limiting (429 errors) when scraping from a single IP address.

## Requirements

1. **Proxy Pool & Rotation**: Load proxies from `proxies.txt`, rotate on every request
2. **User-Agent Rotation**: Rotate through 50+ realistic User-Agent strings
3. **Error Handling**: Track failures per proxy, blacklist after 5 consecutive failures
4. **Fallback**: Fall back to direct connection when all proxies exhausted

## Architecture

### New Module: `proxy_manager.py`

```
┌─────────────────────────────────────────────────────────┐
│                     ProxyPool                           │
├─────────────────────────────────────────────────────────┤
│ State:                                                  │
│  - proxies: List[str]         # All loaded proxies      │
│  - failed_counts: Dict[str, int]  # Failure tracking    │
│  - blacklist: Set[str]        # Temporarily removed     │
│  - user_agents: List[str]     # 50+ User-Agent strings  │
│  - lock: asyncio.Lock         # Thread-safe rotation    │
├─────────────────────────────────────────────────────────┤
│ Methods:                                                │
│  - load_proxies(filepath)     # Parse proxies.txt       │
│  - get_next_proxy() -> str|None  # Rotate to next       │
│  - get_random_user_agent() -> str                       │
│  - mark_proxy_failed(proxy)   # Track failures          │
│  - mark_proxy_success(proxy)  # Reset failure count     │
│  - get_pool_stats() -> Dict   # For logging/monitoring  │
└─────────────────────────────────────────────────────────┘
```

### Integration Points

**`FIPEAPIScraper.__init__`:**
- Initialize `ProxyPool` instance
- Load proxies from configured file path

**`FIPEAPIScraper._make_request`:**
- Get next proxy via `get_next_proxy()` (returns `None` if all exhausted)
- Get random User-Agent via `get_random_user_agent()`
- Pass proxy to `session.post(..., proxy=proxy)`
- Call `mark_proxy_success(proxy)` on 200 response
- Call `mark_proxy_failed(proxy)` on 429/520/connection errors

### Proxy Format

- Input (`proxies.txt`): `ip:port` (one per line)
- Internal/aiohttp: `http://ip:port`
- No authentication required

### User-Agent List

50+ realistic User-Agents covering:
- Chrome (Windows, Mac, Linux) - versions 120-130
- Firefox (Windows, Mac, Linux) - versions 120-130
- Safari (Mac, iOS)
- Edge (Windows)
- Mobile browsers (Chrome Android, Safari iOS)

Selection: `random.choice()` on each request

### Configuration

New settings in `config.py`:

```python
PROXY_CONFIG = {
    'proxy_file': 'proxies.txt',
    'max_consecutive_failures': 5,
    'enable_proxy_rotation': True,
}
```

### Monitoring

`get_pool_stats()` returns:
```python
{
    'total_proxies': 469,
    'active_proxies': 423,
    'blacklisted_proxies': 46,
    'using_direct': False,
}
```

Log examples:
```
INFO  | Loaded 469 proxies from proxies.txt
DEBUG | Request via proxy 101.132.222.120:80
WARN  | Proxy 103.118.44.178:8080 blacklisted after 5 failures
WARN  | All proxies exhausted, falling back to direct connection
INFO  | Proxy pool stats: 423 active, 46 blacklisted
```

Stats logged every 100 requests at INFO level.

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Proxy authentication | None needed | All proxies are open/public |
| Failure threshold | 5 consecutive | Conservative - free proxies can be flaky |
| Fallback behavior | Direct connection | Keeps scraper running if proxies exhausted |
| User-Agent count | 50+ | Large variety for better anonymity |
| Rotation strategy | Every request | Maximum distribution to avoid rate limits |
| Module structure | Separate file | Matches existing architecture, easier to test |

## Implementation Tasks

1. Create `proxy_manager.py` with `ProxyPool` class
2. Add User-Agent list (50+ entries)
3. Add `PROXY_CONFIG` to `config.py`
4. Modify `FIPEAPIScraper.__init__` to initialize proxy pool
5. Modify `FIPEAPIScraper._make_request` to use proxy rotation
6. Add proxy stats logging
7. Test with small scrape
