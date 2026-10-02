"""Dump fresh-room conversation: sender + full text (local only, never commit)."""
import asyncio
import os
import sys

import yaml
from dotenv import load_dotenv

from band.client.rest import AsyncRestClient
from band.cli.trigger import DEFAULT_REQUEST_OPTIONS

ROOM = os.getenv("ROOM_ID", "affa9999-88af-4bef-b731-55957ba9af33")
LIMIT = int(os.getenv("LIMIT", "0"))  # 0 = all


async def main() -> None:
    load_dotenv()
    cfg = yaml.safe_load(open("agent_config.yaml"))
    names = {
        cfg["coordinator"]["agent_id"]: "coordinator",
        cfg["implementer"]["agent_id"]: "implementer",
        cfg["reviewer"]["agent_id"]: "reviewer",
    }
    client = AsyncRestClient(
        api_key=cfg["coordinator"]["api_key"],
        base_url=os.getenv("BAND_REST_URL", "https://app.band.ai").rstrip("/"),
    )
    try:
        r = await client.agent_api_context.get_agent_chat_context(
            ROOM, request_options=DEFAULT_REQUEST_OPTIONS,
        )
        msgs = list(r.data or [])
        if LIMIT:
            msgs = msgs[-LIMIT:]
        print(f"ROOM={ROOM} COUNT={len(msgs)}")
        for i, m in enumerate(msgs):
            sid = getattr(m, "sender_id", "?")
            who = names.get(sid, sid[:8])
            print(f"===== [{i}] {who} {getattr(m, 'inserted_at', '')} =====")
            print(getattr(m, "content", ""))
    finally:
        try:
            await client.close()
        except Exception:
            pass


if __name__ == "__main__":
    asyncio.run(main())
