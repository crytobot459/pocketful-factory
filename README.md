# pocketful-factory

A software factory in three coding-agent seats. One of them decomposes a stage of a written
specification, one implements it, and one checks the result against that specification and
vetoes it if it is wrong. They work in one room, and once a stage is dispatched a human does not
touch it again.

They were pointed at the `pocketful` track of the BAND Dark Factory hackathon: a wallet and
payments service where money must never be created, destroyed, or spent twice — under retries,
concurrent writes, and rounding.

- What the band built, and what it cost: **[FACTORY.md](FACTORY.md)**
- The room it worked in: `room.json`, the full session
- The service: `stage-1/` through `stage-4/`, one complete buildable service per stage

## What is here

| Path | What it is |
|---|---|
| `FACTORY.md` | the factory: seats, design choices, what it cost, how it catches and recovers from bad work, how to stand it up elsewhere |
| `mandates/` | one file per seat, named after the seat, opening with the harness and model that seat runs |
| `room.json` | the room, downloaded in full: every message, tool call and verdict |
| `stage-N/` | one folder per stage: `Dockerfile`, `RUN.md`, source. Each builds on its own and passes every earlier suite |
| `holdouts/` | the reviewer's scenarios, plus `run_scenarios.py`, which runs them against a live service |
| `band-agents/` | the three thin adapters that connect each seat to the room |
| `demo.py` | narrates the whole thing from the evidence above, in English, in one command |
| `docs/harness-runs/` | the event harness's own report from the isolated run, kept rather than summarised |
| `docs/DECK.md`, `docs/DEMO_SCRIPT.md` | the deck, and a recording plan for the video |
| `docs/EVIDENCE.md` | where every number in these documents comes from, generated and checked |
| `docs/SUBMIT_CHECKLIST.md` | what to check before publishing, written against the ways this entry went wrong |
| `verify_claims.py` | re-derives every figure from the evidence and fails if a document disagrees |

## Results, from the event harness

```
python -m harness run --track pocketful --repo . --all --mode isolated
```

| Folder | Claims | share | Overshoot | Shipped checks run against it |
|---|---|---|---|---|
| `stage-1/` | stage 1 | 1.0 | none | 147 |
| `stage-2/` | stage 2 | 1.0 | none | 147 + 35 |
| `stage-3/` | stage 3 | 1.0 | none | 147 + 35 + 6 |
| `stage-4/` | stage 4 | 1.0 | none | 147 + 35 + 6 + 5 |

Highest contiguous stage: 4. No folder passes the next stage's whole suite, so none of them is
a later answer filed in the wrong place. The event ships only part of each stage's checks —
stage 1's 147 is a real sample of the grading suite, stage 3's 6 and stage 4's 5 are close to
a smoke test. What carries those two is the reviewer's own adversarial work in
[`holdouts/`](holdouts/), not the six and five. See FACTORY.md §2 for what the number is and is
not worth.

The run is kept rather than summarised: [`docs/harness-runs/`](docs/harness-runs/) has the
`summary.json`, four `report.json` files and every per-suite log.

**Every number in this file and in FACTORY.md is checked against the evidence by
[`verify_claims.py`](verify_claims.py), which CI runs.** It extracts each figure from
`room.json`, the harness report and the git history, then fails if a document says anything
else. [`docs/EVIDENCE.md`](docs/EVIDENCE.md) is the generated table of where each one comes
from. Run `python3 verify_claims.py` yourself: if it and this file ever disagree, it is right.

## Hear it, in one command

```bash
pip install edge-tts        # optional; the demo runs without it
python3 demo.py
```

That reads this repository's own evidence out loud, in English, and prints it at the same
time: the seats and their models, the room's message count and how it splits across them, the
stages and the revision each locked at, the verdicts, the token usage, and what the event's
harness said. Every figure it speaks is parsed out of `room.json`, the git history and
`docs/harness-runs/`, so the narration cannot drift away from what is in the repository.

`--no-speak` prints without speaking. `--save DIR` keeps the audio as numbered files, which is
what the video edit wants.

## Running a stage yourself

No account, no keys, no Docker needed for a quick look:

```bash
cd stage-4
pip install -r requirements.txt
PORT=8080 python3 -m src.app
curl -s http://127.0.0.1:8080/health        # {"status":"ok"}
```

Then open <http://127.0.0.1:8080/>. Sign in as `ada@example.com` with the password
`correct horse` — those three seeded accounts come from the specification's test fixtures.

To build it the way a judge does:

```bash
docker build -t pocketful-stage4 ./stage-4
docker run --rm -p 8080:8080 -e PORT=8080 pocketful-stage4
```

## Re-running the reviewer's scenarios

The notes in `holdouts/` are executable, so the verdicts do not have to be taken on trust:

```bash
python3 holdouts/run_scenarios.py --base-url http://127.0.0.1:8080 --stage 4
```

Each check prints what it expected against what it read, and the exit status is 0 only when
every one of them passed. CI runs the stage-1, stage-3 and stage-4 sets against every build.

## Standing the factory up

See `ROOM_DISPATCH.md`. In short: `opencode serve`, fill in `band-agents/.env` and
`band-agents/agent_config.yaml` from the templates next to them, run the three adapters, create
three seats whose names match the mandate filenames, and post the dispatch.

Keys are never committed. `harness check` scans gitignored files too, so move `.env` and
`agent_config.yaml` out of the tree for the length of the check.

## Licence

MIT. The specification the band built to belongs to the hackathon organisers; see FACTORY.md.