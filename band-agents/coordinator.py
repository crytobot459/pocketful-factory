"""Coordinator agent — decompose + route, never code. Model: muse-spark-1.3-contributor-free (fresh room, canonical slug coordinator). Fallback: space-bunny-free when 429 (accepted, mandate unchanged)."""
import asyncio
import logging
import os
from dotenv import load_dotenv
from band import Agent, Emit, configure_logging
from band.adapters import OpencodeAdapter, OpencodeAdapterConfig
from band.config import load_agent_config

logger = logging.getLogger(__name__)
REPO = str(__import__("pathlib").Path(__file__).resolve().parent.parent)
# A turn is cut off at this many seconds. 900 stopped the implementer part-way
# through the last stage: the work was fine, the deadline was not.
TURN_TIMEOUT_S = float(os.getenv("TURN_TIMEOUT_S", "1800"))


async def main():
    load_dotenv()
    configure_logging(root_level="INFO")
    agent_id, api_key = load_agent_config("coordinator")
    # Named after the seat as the room shows it, so the log and the mandate agree.
    mandate = open(REPO + "/mandates/factory-architect-df.md", encoding="utf-8").read()
    # Fallback accepted: coordinator stays on Spark unless 429, then bunny. Mandate unchanged.
    provider_id = os.getenv("OPENCODE_PROVIDER_COORDINATOR", "opencode")
    model_id = os.getenv("OPENCODE_MODEL_COORDINATOR", "muse-spark-1.3-contributor-free")
    if os.getenv("COORDINATOR_USE_FALLBACK", "0") == "1":
        model_id = os.getenv("OPENCODE_MODEL_COORDINATOR_FALLBACK", "space-bunny-free")
    adapter = OpencodeAdapter(
        config=OpencodeAdapterConfig(
            directory=REPO,
            custom_section=mandate,
            provider_id=provider_id,
            model_id=model_id,
            approval_mode="auto_accept",  # submitted run: no human gate mid-run; use manual only in dev
            question_mode="auto_reject",  # never block on human questions mid-run; agent-agent only
            turn_timeout_s=TURN_TIMEOUT_S,
            fallback_send_agent_text=False,  # model silence stays silent; kills ack-livelock
        ),
        emit={Emit.TOOL_CALLS, Emit.TASK_EVENTS, Emit.USAGE},
    )
    agent = Agent.create(adapter=adapter, agent_id=agent_id, api_key=api_key,
                         ws_url=os.getenv("BAND_WS_URL", "wss://app.band.ai/api/v1/socket/websocket"),
                         rest_url=os.getenv("BAND_REST_URL", "https://app.band.ai"))
    logger.info("Coordinator running. Ctrl+C to stop.")
    await agent.run()


if __name__ == "__main__":
    asyncio.run(main())
