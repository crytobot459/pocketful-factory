"""Implementer agent — code + test + commit. Model: muse-spark-1.3-contributor-free (fresh room, canonical slug implementer). Fallback: nemotron-3-ultra-free when 429 (accepted)."""
import asyncio
import logging
import os
from dotenv import load_dotenv
from band import Agent, Emit, configure_logging
from band.adapters import OpencodeAdapter, OpencodeAdapterConfig
from band.config import load_agent_config

logger = logging.getLogger(__name__)
REPO = str(__import__("pathlib").Path(__file__).resolve().parent.parent)


async def main():
    load_dotenv()
    configure_logging(root_level="INFO")
    agent_id, api_key = load_agent_config("implementer")
    # Named after the seat as the room shows it, so the log and the mandate agree.
    mandate = open(REPO + "/mandates/factory-coder-df.md", encoding="utf-8").read()
    provider_id = os.getenv("OPENCODE_PROVIDER_IMPLEMENTER", "opencode")
    model_id = os.getenv("OPENCODE_MODEL_IMPLEMENTER", "muse-spark-1.3-contributor-free")
    if os.getenv("IMPLEMENTER_USE_FALLBACK", "0") == "1":
        model_id = os.getenv("OPENCODE_MODEL_IMPLEMENTER_FALLBACK", "nemotron-3-ultra-free")
    adapter = OpencodeAdapter(
        config=OpencodeAdapterConfig(
            directory=REPO,
            custom_section=mandate + "\nRepo: ./stage-1. Build to pocketful/spec/stage-1.md, not to tests.",
            provider_id=provider_id,
            model_id=model_id,
            approval_mode="auto_accept",
            question_mode="auto_reject",
            turn_timeout_s=900.0,
            fallback_send_agent_text=False,  # model silence stays silent; kills ack-livelock
        ),
        emit={Emit.TOOL_CALLS, Emit.TASK_EVENTS, Emit.USAGE},
    )
    agent = Agent.create(adapter=adapter, agent_id=agent_id, api_key=api_key,
                         ws_url=os.getenv("BAND_WS_URL", "wss://app.band.ai/api/v1/socket/websocket"),
                         rest_url=os.getenv("BAND_REST_URL", "https://app.band.ai"))
    logger.info("Implementer running. Ctrl+C to stop.")
    await agent.run()


if __name__ == "__main__":
    asyncio.run(main())
