"""Post a dispatch message into the room, mentioning the two seats it addresses.

The sending seat cannot mention itself, so a dispatch always names the other two
and the text itself opens by addressing the coordinator.

Usage: .venv/bin/python post_dispatch.py <file-with-the-text>
"""
import asyncio
import os
import sys

import yaml
from dotenv import load_dotenv

from band.client.rest import AsyncRestClient
from band.cli.trigger import DEFAULT_REQUEST_OPTIONS

try:
    from band_rest.agent_api_messages.types.chat_message_request import ChatMessageRequest
    from band_rest.agent_api_messages.types.chat_message_request_mentions_item import (
        ChatMessageRequestMentionsItem as Mention,
    )
except ImportError:  # fallback paths across SDK versions
    from band.cli.trigger import ChatMessageRequest, ChatMessageRequestMentionsItem as Mention

ROOM = os.getenv("ROOM_ID", "affa9999-88af-4bef-b731-55957ba9af33")


async def main() -> None:
    load_dotenv()
    text = open(sys.argv[1], encoding="utf-8").read().strip()
    cfg = yaml.safe_load(open("agent_config.yaml"))
    client = AsyncRestClient(
        api_key=cfg["coordinator"]["api_key"],
        base_url=os.getenv("BAND_REST_URL", "https://app.band.ai").rstrip("/"),
    )
    try:
        body = ChatMessageRequest(
            content=text,
            mentions=[Mention(id=cfg[role]["agent_id"], handle=cfg[role]["seat"])
                      for role in ("implementer", "reviewer")],
        )
        r = await client.agent_api_messages.create_agent_chat_message(
            ROOM, message=body, request_options=DEFAULT_REQUEST_OPTIONS,
        )
        print("posted:", getattr(r.data, "id", r.data))
    finally:
        # This SDK version has no close(); the transport is released with the loop.
        pass


if __name__ == "__main__":
    asyncio.run(main())