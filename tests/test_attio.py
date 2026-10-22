import asyncio

import httpx

from vc_evals.attio import AttioClient


def note(i: int, title="Founder Call Brief — 2026-10-1x", day=10):
    return {
        "id": {"workspace_id": "w", "note_id": f"n{i}"},
        "parent_object": "deals",
        "parent_record_id": "d1",
        "title": title,
        "content_markdown": f"body {i}",
        "created_at": f"2026-10-{day:02d}T00:00:00Z",
    }


def client(handler, sleeps=None):
    async def fake_sleep(s):
        if sleeps is not None:
            sleeps.append(s)

    return AttioClient("k", transport=httpx.MockTransport(handler), sleep=fake_sleep)


def run(coro):
    return asyncio.run(coro)


def test_list_filters_titles_sorts_newest_first_and_limits():
    def handler(req):
        assert req.url.params["parent_object"] == "deals"
        assert req.url.params["parent_record_id"] == "d1"
        assert req.headers["Authorization"] == "Bearer k"
        return httpx.Response(
            200,
            json={"data": [note(1, day=1), note(2, title="Call notes", day=9), note(3, day=5)]},
        )

    briefs = run(client(handler).list_briefs("d1", limit=1))
    assert [b.note_id for b in briefs] == ["n3"]


def test_list_pages_with_offset_until_a_short_page():
    offsets = []

    def handler(req):
        offsets.append(int(req.url.params["offset"]))
        n = 50 if offsets[-1] == 0 else 3
        return httpx.Response(200, json={"data": [note(offsets[-1] + i) for i in range(n)]})

    briefs = run(client(handler).list_briefs("d1", limit=100))
    assert offsets == [0, 50] and len(briefs) == 53


def test_429_honors_retry_after_then_succeeds():
    calls, sleeps = [], []

    def handler(req):
        calls.append(1)
        if len(calls) == 1:
            return httpx.Response(429, headers={"Retry-After": "7"})
        return httpx.Response(200, json={"data": []})

    assert run(client(handler, sleeps).list_briefs("d1")) == []
    assert len(calls) == 2 and sleeps == [7.0]


def test_429_without_retry_after_backs_off_exponentially():
    calls, sleeps = [], []

    def handler(req):
        calls.append(1)
        if len(calls) <= 2:
            return httpx.Response(429)
        return httpx.Response(200, json={"data": []})

    run(client(handler, sleeps).list_briefs("d1"))
    assert sleeps == [1.0, 2.0]


def test_get_brief_returns_brief_or_none_for_other_notes():
    def handler(req):
        if req.url.path.endswith("/n1"):
            return httpx.Response(200, json={"data": note(1)})
        return httpx.Response(200, json={"data": note(2, title="Meeting notes")})

    c = client(handler)
    b = run(c.get_brief("n1"))
    assert (b.note_id, b.deal_id, b.body) == ("n1", "d1", "body 1")
    assert run(c.get_brief("n2")) is None
