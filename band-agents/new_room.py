"""Create fresh room pocketful-factory-v2: new chatroom + 3 seats + dispatch.

Uses coordinator agent key (agent auth). Never prints secrets.
Usage: uv run python new_room.py
"""
import asyncio
import logging
import os
import sys

import yaml
from dotenv import load_dotenv

from band.client.rest import AsyncRestClient
from band.cli.trigger import DEFAULT_REQUEST_OPTIONS

try:
    from band_rest.agent_api_chats.types.chat_room_request import ChatRoomRequest
    from band_rest.agent_api_participants.types.participant_request import (
        ParticipantRequest,
    )
    from band_rest.agent_api_messages.types.chat_message_request import (
        ChatMessageRequest,
    )
    from band_rest.agent_api_messages.types.chat_message_request_mentions_item import (
        ChatMessageRequestMentionsItem,
    )
except ImportError:  # fallback paths across SDK versions
    from band.cli.trigger import (
        ChatRoomRequest,
        ParticipantRequest,
        ChatMessageRequest,
        ChatMessageRequestMentionsItem,
    )

logger = logging.getLogger(__name__)
HERE = str(__import__("pathlib").Path(__file__).resolve().parent)

DISPATCH = """@coordinator Build stage-1 of the Pocketful wallet service from the official spec at /Users/admin/dark-factory-wearedevs/pocketful/spec/stage-1.md, working in ./stage-1 of this repo (/Users/admin/harness/lablab-harness/build/pocketful-factory/stage-1).

@implementer implements to the SPEC, runs the shipped checks locally, commits, and hands each revision to @reviewer with revision SHA + exact commands + results. @reviewer checks out the exact revision, reads holdouts/stage-1.md (reviewer only, never share it), runs independent plus adversarial verification, and replies ACCEPT to @coordinator or REJECT to @implementer with revision + logs. No human clarification mid-run. Coordinator locks the stage only after reviewer ACCEPT.

SILENCE RULE (all seats): after reporting a revision or assigning a task, stay silent until a verdict or new revision arrives. Never send Holding/Ack/Noted/Waiting. One revision = one report with numbers.

Verify locally: cd stage-1 && PORT=8080 python3 -m src.app + curl http://127.0.0.1:8080/health. Official: python -m harness check /Users/admin/harness/lablab-harness/build/pocketful-factory --track pocketful."""


async def main() -> str:
    load_dotenv()
    logging.basicConfig(level=logging.INFO)
    cfg = yaml.safe_load(open(os.path.join(HERE, "agent_config.yaml")))
    ids = {k: cfg[k]["agent_id"] for k in ("coordinator", "implementer", "reviewer")}
    key = cfg["coordinator"]["api_key"]
    rest_url = os.getenv("BAND_REST_URL", "https://app.band.ai").rstrip("/")

    client = AsyncRestClient(api_key=key, base_url=rest_url)
    try:
        # Resolve handles for our 3 seats via peer list.
        handles: dict[str, str] = {}
        names: dict[str, str] = {}
        page = 1
        while True:
            resp = await client.agent_api_peers.list_agent_peers(
                page=page, page_size=100,
                request_options=DEFAULT_REQUEST_OPTIONS,
            )
            if not resp.data:
                break
            for peer in resp.data:
                if peer.id in ids.values():
                    slug = next(k for k, v in ids.items() if v == peer.id)
                    handles[slug] = getattr(peer, "handle", None) or slug
                    names[slug] = peer.name
            total = (getattr(resp.metadata, "total_pages", None) or 1) if resp.metadata else 1
            if page >= total:
                break
            page += 1
        missing = [k for k in ids if k not in handles]
        if missing == ["coordinator"]:
            # Own agent is never its own peer; resolve self via identity endpoint.
            me = await client.agent_api_identity.get_agent_me(
                request_options=DEFAULT_REQUEST_OPTIONS,
            )
            me_data = getattr(me, "data", me)
            handles["coordinator"] = getattr(me_data, "handle", None) or "coordinator"
            names["coordinator"] = getattr(me_data, "name", None) or "coordinator"
            missing = []
        if missing:
            raise RuntimeError(f"peer lookup missed seats: {missing} (same owner required)")
        logger.info("peers: %s", {k: names[k] for k in ids})

        # Create room (or reuse one from a previous partial run).
        room_id = os.getenv("ROOM_ID", "")
        if not room_id:
            chat_resp = await client.agent_api_chats.create_agent_chat(
                chat=ChatRoomRequest(), request_options=DEFAULT_REQUEST_OPTIONS,
            )
            room_id = chat_resp.data.id
        print(f"ROOM_ID={room_id}", flush=True)

        # Add all 3 seats (creator re-add is tolerated).
        for slug in ("coordinator", "implementer", "reviewer"):
            try:
                await client.agent_api_participants.add_agent_chat_participant(
                    chat_id=room_id,
                    participant=ParticipantRequest(participant_id=ids[slug]),
                    request_options=DEFAULT_REQUEST_OPTIONS,
                )
                logger.info("added %s", slug)
            except Exception as e:  # e.g. creator already member
                logger.warning("add %s: %s", slug, type(e).__name__)

        # Dispatch with mentions for implementer + reviewer only
        # (platform rejects self-mention by the sending seat).
        mentions = [
            ChatMessageRequestMentionsItem(id=ids[s], handle=handles[s])
            for s in ("implementer", "reviewer")
        ]
        await client.agent_api_messages.create_agent_chat_message(
            chat_id=room_id,
            message=ChatMessageRequest(content=DISPATCH, mentions=mentions),
            request_options=DEFAULT_REQUEST_OPTIONS,
        )
        logger.info("dispatch posted")
        return room_id
    finally:
        try:
            from band.client.rest import aclose_rest_client  # type: ignore
            await aclose_rest_client(client)
        except Exception:
            pass


if __name__ == "__main__":
    room = asyncio.run(main())
    print(f"FRESH_ROOM={room}")
    sys.exit(0)
