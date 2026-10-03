"""Reviewer agent — independent verifier with veto.

Primary: Gemini free. Fallback chain (2026-10-01: GPT key has no credits,
Gemini free-tier daily cap hit): REVIEWER_USE_FALLBACK=1 -> OpenCode free
model (default nemotron-3-ultra-free, different model from implementer).
Same mandate policy; independence is best-effort under free-tier outages.
"""
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
    agent_id, api_key = load_agent_config("reviewer")
    # Named after the seat as the room shows it, so the log and the mandate agree.
    mandate = open(REPO + "/mandates/factory-tester-df.md", encoding="utf-8").read()
    # Primary: Gemini free (gemini-3.8-flash proven 2026-10-01; 2.0/2.5 deprecated for new keys).
    # OpenCode server needs GOOGLE_GENERATIVE_AI_API_KEY exported (see .env) when it starts.
    use_fallback = os.getenv("REVIEWER_USE_FALLBACK", "0")
    if use_fallback == "gpt":
        provider_id, model_id = "openai", os.getenv("OPENAI_MODEL_ID", "gpt-4o-mini")
    elif use_fallback == "1":
        provider_id = os.getenv("OPENCODE_PROVIDER_REVIEWER", "opencode")
        model_id = os.getenv("OPENCODE_MODEL_REVIEWER", "nemotron-3-ultra-free")
    else:
        provider_id, model_id = "google", os.getenv("GEMINI_MODEL_ID", "gemini-3.8-flash")
    adapter = OpencodeAdapter(
        config=OpencodeAdapterConfig(
            directory=REPO,
            custom_section=mandate,
            provider_id=provider_id,
            model_id=model_id,
            approval_mode="auto_accept",
            # Submitted run: reviewer must never block on human questions mid-run.
            question_mode="auto_reject",
            # Full verify (shipped suites + adversarial) exceeds the 300s default.
            turn_timeout_s=TURN_TIMEOUT_S,
            # Model silence stays silent (no filler posts); kills ack-livelock.
            fallback_send_agent_text=False,
        ),
        emit={Emit.TOOL_CALLS, Emit.TASK_EVENTS, Emit.USAGE},
    )
    agent = Agent.create(adapter=adapter, agent_id=agent_id, api_key=api_key,
                         ws_url=os.getenv("BAND_WS_URL", "wss://app.band.ai/api/v1/socket/websocket"),
                         rest_url=os.getenv("BAND_REST_URL", "https://app.band.ai"))
    logger.info(f"Reviewer running ({provider_id}/{model_id}). Ctrl+C to stop.")
    await agent.run()


if __name__ == "__main__":
    asyncio.run(main())
