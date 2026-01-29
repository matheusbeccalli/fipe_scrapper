# Proxy Rotation Design

## Overview

Add proxy rotation capability to the FIPE scraper to avoid rate limiting (429 errors) when scraping from a single IP address.

## Requirements

1. **Proxy Pool & Rotation**: Load proxies from `proxies.txt`, rotate on every request
2. **Multi-Protocol Support**: Support HTTP, SOCKS4, and SOCKS5 proxies
3. **User-Agent Rotation**: Rotate through 50+ realistic User-Agent strings
4. **Error Handling**: Track failures per proxy, blacklist after 5 consecutive failures
5. **Fallback**: Fall back to direct connection when all proxies exhausted

## Dependencies

New package required:
```bash
pip install aiohttp-socks
```

This enables SOCKS4/SOCKS5 support for aiohttp.

## Architecture

### New Module: `proxy_manager.py`

```
┌─────────────────────────────────────────────────────────┐
│                     ProxyPool                           │
├─────────────────────────────────────────────────────────┤
│ State:                                                  │
│  - proxies: List[str]         # All loaded proxy URLs   │
│  - failed_counts: Dict[str, int]  # Failure tracking    │
│  - blacklist: Set[str]        # Temporarily removed     │
│  - user_agents: List[str]     # 50+ User-Agent strings  │
│  - lock: asyncio.Lock         # Thread-safe rotation    │
│  - current_index: int         # Round-robin position    │
├─────────────────────────────────────────────────────────┤
│ Methods:                                                │
│  - load_proxies(filepath)     # Parse proxies.txt       │
│  - get_next_proxy() -> str|None  # Rotate to next       │
│  - get_random_user_agent() -> str                       │
│  - mark_proxy_failed(proxy)   # Track failures          │
│  - mark_proxy_success(proxy)  # Reset failure count     │
│  - get_pool_stats() -> Dict   # For logging/monitoring  │
│  - is_socks_proxy(proxy) -> bool  # Check proxy type    │
└─────────────────────────────────────────────────────────┘
```

### Integration Points

**`FIPEAPIScraper.__init__`:**
- Initialize `ProxyPool` instance
- Load proxies from configured file path

**`FIPEAPIScraper._make_request`:**
- Get next proxy via `get_next_proxy()` (returns `None` if all exhausted)
- Get random User-Agent via `get_random_user_agent()`
- Create appropriate connector based on proxy type:
  - HTTP proxies: use native `session.post(..., proxy=proxy_url)`
  - SOCKS proxies: use `ProxyConnector.from_url(proxy_url)` from aiohttp-socks
- Call `mark_proxy_success(proxy)` on 200 response
- Call `mark_proxy_failed(proxy)` on 429/520/connection errors

**Connector handling for SOCKS:**
```python
from aiohttp_socks import ProxyConnector

if proxy_url.startswith(('socks4://', 'socks5://')):
    connector = ProxyConnector.from_url(proxy_url)
    async with aiohttp.ClientSession(connector=connector) as session:
        # make request
else:
    # HTTP proxy - use existing session with proxy= parameter
    async with session.post(url, proxy=proxy_url, ...) as response:
        # handle response
```

### Proxy Format

**Input format (`proxies.txt`):** Protocol-prefixed URLs, one per line:
```
http://101.132.222.120:80
http://101.201.225.47:80
socks4://103.118.44.178:1080
socks5://145.220.178.0:1080
```

**Backwards compatibility:** Lines without protocol prefix (e.g., `ip:port`) default to `http://`

**Supported protocols:**
- `http://` - HTTP proxies (native aiohttp support)
- `socks4://` - SOCKS4 proxies (via aiohttp-socks)
- `socks5://` - SOCKS5 proxies (via aiohttp-socks)

**No authentication required** (but format supports `protocol://user:pass@ip:port` if needed later)

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
| Proxy protocols | HTTP, SOCKS4, SOCKS5 | Maximum flexibility with available proxies |
| Proxy file format | Single file with protocol prefix | Standard URL format, self-documenting, easy to manage |
| Proxy authentication | None needed | All proxies are open/public |
| Failure threshold | 5 consecutive | Conservative - free proxies can be flaky |
| Fallback behavior | Direct connection | Keeps scraper running if proxies exhausted |
| User-Agent count | 50+ | Large variety for better anonymity |
| Rotation strategy | Every request | Maximum distribution to avoid rate limits |
| Module structure | Separate file | Matches existing architecture, easier to test |

## Implementation Tasks

1. Add `aiohttp-socks` to `requirements.txt`
2. Create `proxy_manager.py` with `ProxyPool` class
3. Add User-Agent list (50+ entries)
4. Add `PROXY_CONFIG` to `config.py`
5. Modify `FIPEAPIScraper.__init__` to initialize proxy pool
6. Modify `FIPEAPIScraper._make_request` to use proxy rotation (with SOCKS connector support)
7. Add proxy stats logging
8. Update `proxies.txt` format to include protocol prefixes
9. Test with small scrape
