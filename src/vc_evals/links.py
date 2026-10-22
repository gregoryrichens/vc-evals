"""The link check. The only part of `score` that uses the network. Each URL is reported as loaded or could not fetch."""

import httpx

LOADED = "loaded"
COULD_NOT_FETCH = "could not fetch"


async def check_links(urls: list[str], client: httpx.AsyncClient) -> dict[str, str]:
    """LOADED or COULD_NOT_FETCH for each URL. The result shows whether the page exists."""
    results = {}
    for url in dict.fromkeys(urls):
        try:
            resp = await client.get(url, follow_redirects=True, timeout=15)
            results[url] = LOADED if resp.status_code < 400 else COULD_NOT_FETCH
        except httpx.HTTPError:
            results[url] = COULD_NOT_FETCH
    return results
