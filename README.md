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
| `holdouts/` | the reviewer's private scenarios, one file per stage. The implementer is forbidden to read them |
| `band-agents/` | the three thin adapters that connect each seat to the room |
| `docs/harness-runs/` | the event harness's own report from the isolated run, kept rather than summarised |
| `docs/templates/` | submission, deck and script skeletons. Outlines, not this factory's story |

## Results, from the event harness

```
python -m harness run --track pocketful --repo . --all --mode isolated
```

| Folder | Claims | share | Overshoot |
|---|---|---|---|
| `stage-1/` | stage 1 | 1.0 | none |
| `stage-2/` | stage 2 | 1.0 | none |
| `stage-3/` | stage 3 | 1.0 | none |

Highest contiguous stage: 3. The event ships only part of each stage's checks, so this is
directional — see FACTORY.md §2 for what the number is and is not worth.

## Running a stage yourself

No account, no keys, no Docker needed for a quick look:

```bash
cd stage-3
pip install -r requirements.txt
PORT=8080 python3 -m src.app
curl -s http://127.0.0.1:8080/health        # {"status":"ok"}
```

Then open <http://127.0.0.1:8080/>. Sign in as `ada@example.com` with the password
`correct horse` — those three seeded accounts come from the specification's test fixtures.

To build it the way a judge does:

```bash
docker build -t pocketful-stage3 ./stage-3
docker run --rm -p 8080:8080 -e PORT=8080 pocketful-stage3
```

## Standing the factory up

See `ROOM_DISPATCH.md`. In short: `opencode serve`, fill in `band-agents/.env` and
`band-agents/agent_config.yaml` from the templates next to them, run the three adapters, create
three seats whose names match the mandate filenames, and post the dispatch.

Keys are never committed. `harness check` scans gitignored files too, so move `.env` and
`agent_config.yaml` out of the tree for the length of the check.

## Licence

MIT. The specification the band built to belongs to the hackathon organisers; see FACTORY.md.