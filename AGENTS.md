# AGENTS.md — operating contract for this repository

## Build and run

* A stage service: `cd stage-1 && pip install -r requirements.txt && PORT=8080 python3 -m src.app`
* Health: `curl -s http://127.0.0.1:8080/health` → `{"status":"ok"}`
* The band: `opencode serve --hostname=127.0.0.1 --port=4096` first, then one terminal each for
  `band-agents/coordinator.py`, `implementer.py` and `reviewer.py`
* The narrated demo: `python3 demo.py` — reads the room, the git history and the harness report
  out loud. No key needed; speech is skipped if `edge-tts` is not installed.
* The event harness, which lives outside this repository:
  `python -m harness check <repo> --track pocketful` and
  `python -m harness run --track pocketful --repo <repo> --all --mode isolated`

## Conventions

Breaking any of these is what disqualifies an entry, not what costs points.

* **Mandates stay generic.** A mandate says how the factory works: what a seat owns, how it
  hands off, when it rejects. No endpoint path, no field name, no error code, no check id. The
  event's `vocabulary.py` enforces this.
* **The implementer reads the specification, the repository, the RUN docs and the shipped
  checks**, and nothing else. No searching for hidden checks, no reading the judge's harness, no
  grepping for expected answers, and never `holdouts/`, which belongs to the reviewer alone.
* **The reviewer reads the exact revision it was named.** It runs the checks itself, invents
  adversarial scenarios from `holdouts/stage-N.md`, and replies ACCEPT or REJECT. It never edits
  service code, and it never runs a bare `git checkout <sha>` — see `mandates/factory-tester-df.md`.
* **The coordinator never writes code.** Every handoff is self-contained and names both
  directions with `@handle` in the message text, because a mention echoed in a tool call does not
  count for gate 2.
* **Silence is the default.** After reporting a revision or assigning a task, say nothing until a
  verdict or a new revision arrives. `Standing by`, `Noted`, `Acknowledged`, `Holding` and
  `Waiting` are forbidden outright. One revision gets one report, carrying numbers. The abandoned
  room in this project died of exactly that: 482 messages, 99% of them pings.
* **One room for every stage**, named by the seats it contains: `factory-architect-df`,
  `factory-coder-df`, `factory-tester-df`. `mandates/` is named after those three and nothing
  else.
* **Never commit a key.** `.env`, `agent_config.yaml`, and any `room.json` carrying a credential
  stay out. `harness check` scans gitignored files too, so move the two secret files to `/tmp`
  for the length of the check and put them back afterwards.
* **Each stage folder is carried forward from the one before it** and keeps every earlier check
  passing. No symlinks, no submodules, no nested `.git`.
* **Do not rewrite history.** No amend, no rebase, no squash. A seat that checks out a revision
  to review it will move HEAD and strand later commits; recover by fast-forwarding from the
  reflog, which is not a rewrite.

## Architecture

`mandates/` → room routing → `stage-N/` service → the event harness in isolated mode.

`band-agents/*.py` are thin adapters: an `OpencodeAdapter` over the repository, the seat's
mandate as its custom section, and provider and model from the environment. They emit tool calls,
task events and usage.

Evidence is three things that have to agree: the room log, the git history with one commit per
revision, and the harness report under `docs/harness-runs/`.