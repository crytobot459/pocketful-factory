# band-agents — three OpenCode seats, one room

Each file is a thin adapter: it loads that seat's mandate, starts an OpenCode session over the
local server, and connects it to the room as that seat. There is no agent logic in here, and
that is the point — the policy lives in `../mandates/`, so a different factory is a different
mandate rather than a different program.

## Standing it up

1. `cp .env.example .env` and fill in your own model keys. Free tiers are enough. Never commit.
2. `cp agent_config.example.yaml agent_config.yaml` and fill in the three seat credentials from
   <https://app.band.ai/agents>. Never commit.
3. `opencode serve --hostname=127.0.0.1 --port=4096` in its own terminal, and leave it running.
4. First time only: `uv venv && uv add "band-sdk[opencode]" python-dotenv pyyaml`
5. Three terminals:

```bash
uv run python coordinator.py
uv run python implementer.py
uv run python reviewer.py
```

6. On `app.band.ai`, create the room, add the three remotes, and post the dispatch from
   `../ROOM_DISPATCH.md` unchanged. Nothing else is typed by a human: once a stage is
   dispatched, the next input is a verdict.
7. Afterwards, download the room from the Band console — the room's menu, Open in Band, then
   Download full session — and save it at the repository root as `room.json`. Read it before
   committing it: the download redacts nothing.
8. Before publishing, move `.env` and `agent_config.yaml` out of the tree, run
   `python -m harness check <repo> --track pocketful`, and put them back.

## Roles and models

The keys below are adapter roles. The seats they drive are named in `agent_config.yaml`, and
those are the names the room records and `mandates/` is named after.

| Adapter | Seat it drives | Model |
|---|---|---|
| `coordinator.py` | `factory-architect-df` | `muse-spark-1.3-contributor-free`, falling back to `space-bunny-free` on rate limits |
| `implementer.py` | `factory-coder-df` | `muse-spark-1.3-contributor-free`, falling back to `nemotron-3-ultra-free` |
| `reviewer.py` | `factory-tester-df` | `gemini-3.8-flash` via `GOOGLE_GENERATIVE_AI_API_KEY`, then `gpt-4o-mini`, then an OpenCode free model |

The reviewer is never on the implementer's model. A reviewer sharing the implementer's blind
spot is not a reviewer, and the submitted run therefore records which model actually ran in
every verdict.

## Settings that matter

`approval_mode=auto_accept` so a submitted run never blocks waiting for a human.
`question_mode=auto_reject` for the same reason: an agent that needs an answer asks another
seat in the room, never the human.

`fallback_send_agent_text=False` is the setting that fixed the ping-pong. When the model has
nothing to say, the seat says nothing; it does not post a placeholder.

`turn_timeout_s` comes from `TURN_TIMEOUT_S`, default 1800. It was 900 and that cut the
implementer off part-way through stage 4, which left the room with nothing queued and every
seat correctly silent.

`emit={TOOL_CALLS, TASK_EVENTS, USAGE}`. `TASK_EVENTS` is load-bearing: it is what lets a
session resume after a restart. `USAGE` is how the cost in `FACTORY.md` was measured.

## Scripts

| Script | What it does |
|---|---|
| `post_dispatch.py <file>` | posts a dispatch, mentioning the two seats it addresses. A seat cannot mention itself, so the text opens by addressing the coordinator |
| `fetch_room.py` | downloads the whole room to `../room.json`, paging until the end and counting seats |
| `dump_room.py`, `watch_room.py` | read the room while a run is in flight |