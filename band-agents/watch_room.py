"""Watch fresh room: print message count + new text messages (truncated, no secrets)."""
import asyncio
import os
import sys

import yaml
from dotenv import load_dotenv

from band.client.rest import AsyncRestClient
from band.cli.trigger import DEFAULT_REQUEST_OPTIONS

ROOM = os.getenv("ROOM_ID", "affa9999-88af-4bef-b731-55957ba9af33")


async def main() -> None:
    load_dotenv()
    cfg = yaml.safe_load(open("agent_config.yaml"))
    client = AsyncRestClient(
        api_key=cfg["coordinator"]["api_key"],
        base_url=os.getenv("BAND_REST_URL", "https://app.band.ai").rstrip("/"),
    )
    try:
        resp = await client.agent_api_messages.list_agent_messages(
            ROOM, status="all", sort_order="asc", limit=100,
            request_options=DEFAULT_REQUEST_OPTIONS,
        )
        msgs = list(resp.data or [])
        print(f"COUNT={len(msgs)}")
        since = int(os.getenv("SINCE", "0"))
        for i, m in enumerate(msgs):
            if i < since:
                continue
            sender = getattr(m, "sender_name", None) or getattr(m, "sender_id", "?")
            content = (getattr(m, "content", "") or "")[:300].replace("\n", " | ")
            print(f"[{i}] {sender}: {content}")
    finally:
        try:
            await client.close()
        except Exception:
            pass


if __name__ == "__main__":
    asyncio.run(main())
