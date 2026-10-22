"""Read-only Attio client that lists and reads brief notes.

Endpoints (verified against https://docs.attio.com on 2026-10-14):
  GET /v2/notes/{note_id}
  GET /v2/notes?parent_object=&parent_record_id=&limit=&offset=   (limit max 50, offset paging)
This client picks out brief notes by title.
Verify the deals object slug ("deals") against your workspace.
"""

import asyncio
import os
from datetime import datetime
from pathlib import Path

import httpx
from pydantic import BaseModel

BASE_URL = "https://api.attio.com/v2"
DEALS_OBJECT = "deals"
TITLE_PREFIX = "Founder Call Brief"
PAGE_SIZE = 50
MAX_PAGES = 20  # caps paging at 1,000 notes per deal
MAX_RETRIES = 5


class Brief(BaseModel):
    note_id: str
    deal_id: str
    created_at: datetime
    title: str
    body: str


def _to_brief(note: dict) -> Brief | None:
    title = note.get("title") or ""
    if not title.startswith(TITLE_PREFIX):
        return None
    return Brief(
        note_id=note["id"]["note_id"],
        deal_id=note["parent_record_id"],
        created_at=note["created_at"],
        title=title,
        body=note.get("content_markdown") or "",
    )


def load_api_key(env_path: Path = Path(".env")) -> str:
    key = os.environ.get("ATTIO_API_KEY")
    if not key and env_path.exists():
        for line in env_path.read_text().splitlines():
            name, _, value = line.partition("=")
            if name.strip() == "ATTIO_API_KEY":
                key = value.strip().strip("'\"")
    if not key:
        raise RuntimeError("ATTIO_API_KEY is not set. Put it in .env or the environment.")
    return key


class AttioClient:
    def __init__(
        self,
        api_key: str,
        transport: httpx.AsyncBaseTransport | None = None,
        sleep=asyncio.sleep,
    ):
        self._http = httpx.AsyncClient(
            base_url=BASE_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            transport=transport,
            timeout=30,
        )
        self._sleep = sleep

    async def aclose(self) -> None:
        await self._http.aclose()

    async def _get(self, path: str, params: dict | None = None) -> httpx.Response:
        for attempt in range(MAX_RETRIES + 1):
            resp = await self._http.get(path, params=params)
            if resp.status_code != 429 or attempt == MAX_RETRIES:
                resp.raise_for_status()
                return resp
            retry_after = resp.headers.get("Retry-After")
            try:
                delay = float(retry_after) if retry_after else 2.0**attempt
            except ValueError:
                delay = 2.0**attempt
            await self._sleep(delay)
        raise AssertionError("unreachable")

    async def get_brief(self, note_id: str) -> Brief | None:
        """The note as a Brief, or None if its title is not a brief title."""
        resp = await self._get(f"/notes/{note_id}")
        return _to_brief(resp.json()["data"])

    async def list_briefs(self, deal_id: str, limit: int = 20) -> list[Brief]:
        """One deal's briefs, newest first, at most `limit`."""
        briefs: list[Brief] = []
        for page in range(MAX_PAGES):
            resp = await self._get(
                "/notes",
                {
                    "parent_object": DEALS_OBJECT,
                    "parent_record_id": deal_id,
                    "limit": PAGE_SIZE,
                    "offset": page * PAGE_SIZE,
                },
            )
            notes = resp.json()["data"]
            briefs += [b for n in notes if (b := _to_brief(n))]
            if len(notes) < PAGE_SIZE:
                break
        briefs.sort(key=lambda b: b.created_at, reverse=True)
        return briefs[:limit]
