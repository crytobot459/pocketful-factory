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


async def main() -> None:
    load_dotenv()
    cfg = yaml.safe_load(open("agent_config.yaml"))
    client = AsyncRestClient(
        api_key=cfg["coordinator"]["api_key"],
        base_url=os.getenv("BAND_REST_URL", "https://app.band.ai").rstrip("/"),
    )
    try:
        # The context endpoint caps a page at 100 and returns the oldest page by
        # default, so a room longer than that silently truncates at the front of
        # the run. Walk the pages with a cursor until one comes back short.
        raw, cursor = [], None
        while True:
            page = await client.agent_api_context.get_agent_chat_context(
                ROOM, limit=100, cursor=cursor, request_options=DEFAULT_REQUEST_OPTIONS,
            )
            batch = page.data or []
            raw.extend(batch)
            if len(batch) < 100:
                break
            nxt = getattr(page, "next_cursor", None) or getattr(page, "cursor", None)
            if not nxt or nxt == cursor:
                break
            cursor = nxt
        msgs = []
        for m in raw:
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
