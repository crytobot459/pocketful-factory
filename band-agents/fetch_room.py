"""Fetch full session of the fresh room via context API and save console-shape room.json.

Console shape: {room_id, room_name, scope=full, messages:[{id,senderId,senderName,
senderType,messageType,content,inserted_at}]}. Secrets are never written:
runner must scrub before public (same rule as console download).
Usage: .venv/bin/python fetch_room.py  (ROOM_ID env overrides default)
"""
import asyncio
import json
import os

import yaml
from dotenv import load_dotenv

from band.client.rest import AsyncRestClient
from band.cli.trigger import DEFAULT_REQUEST_OPTIONS

ROOM = os.getenv("ROOM_ID", "affa9999-88af-4bef-b731-55957ba9af33")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "room.json")


def page_meta(response) -> dict:
    """`metadata` arrives as a flat query string, not as an object."""
    meta = response.metadata
    if isinstance(meta, dict):
        return meta
    out = {}
    for part in str(meta or "").split():
        if "=" in part:
            key, _, value = part.partition("=")
            out[key] = value
    return out


async def fetch_all(client) -> list:
    """Every message in the room, in order.

    The endpoint pages, and it will not tell you the room is longer than one
    page unless you ask in the way that reports it: `limit` stops at 100 and
    hands back a cursor, while `page`/`page_size` also reports `total_count`
    and `total_pages`. A room long enough to need a second page therefore looks
    complete to anything that reads one page, which is how this saved a room
    that was missing its own final revisions.

    Deduplicate by id as well, since a message can appear on the boundary.
    """
    seen: dict[str, object] = {}
    page = 1
    while True:
        response = await client.agent_api_context.get_agent_chat_context(
            ROOM, page=page, page_size=100, request_options=DEFAULT_REQUEST_OPTIONS,
        )
        batch = response.data or []
        for m in batch:
            seen[getattr(m, "id", "") or str(len(seen))] = m
        if not batch or page_meta(response).get("has_more") != "True":
            break
        page += 1
        if page > 50:          # a room cannot plausibly be longer; stop rather than spin
            break
    return sorted(seen.values(), key=lambda m: str(getattr(m, "inserted_at", "")))


async def main() -> None:
    load_dotenv()
    cfg = yaml.safe_load(open("agent_config.yaml"))
    client = AsyncRestClient(
        api_key=cfg["coordinator"]["api_key"],
        base_url=os.getenv("BAND_REST_URL", "https://app.band.ai").rstrip("/"),
    )
    try:
        msgs = []
        for m in await fetch_all(client):
            ts = getattr(m, "inserted_at", "")
            msgs.append({
                "id": getattr(m, "id", ""),
                "senderId": getattr(m, "sender_id", ""),
                "senderName": getattr(m, "sender_name", ""),
                "senderType": getattr(m, "sender_type", ""),
                "messageType": getattr(m, "message_type", ""),
                "content": getattr(m, "content", "") or "",
                "inserted_at": ts.isoformat() if hasattr(ts, "isoformat") else str(ts),
            })
        room = {
            "room_id": ROOM,
            "room_name": "pocketful-factory-v2",
            "scope": "full",
            "messages": msgs,
        }
        with open(OUT, "w") as f:
            json.dump(room, f, ensure_ascii=False, indent=1)
        agents = {x["senderId"] for x in msgs if str(x["senderType"]).lower() == "agent"}
        texts = [x for x in msgs
                 if str(x["senderType"]).lower() == "agent" and x["messageType"] == "text"]
        print(f"saved {OUT} messages={len(msgs)} agent_seats={len(agents)} "
              f"agent_texts={len(texts)}")
    finally:
        # This SDK version has no close(); the transport is released with the loop.
        pass


if __name__ == "__main__":
    asyncio.run(main())
