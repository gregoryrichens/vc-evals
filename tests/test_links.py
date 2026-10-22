import asyncio

import httpx

from vc_evals.links import COULD_NOT_FETCH, LOADED, check_links


def test_loaded_404_and_connection_error():
    def handler(req):
        if req.url.host == "down.example":
            raise httpx.ConnectError("no route")
        return httpx.Response(404 if req.url.path == "/gone" else 200)

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
            urls = ["https://a.example/ok", "https://a.example/gone", "https://down.example/x"]
            return await check_links(urls + urls[:1], c)  # a duplicate is fetched once

    assert asyncio.run(run()) == {
        "https://a.example/ok": LOADED,
        "https://a.example/gone": COULD_NOT_FETCH,
        "https://down.example/x": COULD_NOT_FETCH,
    }
