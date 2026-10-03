# Harness run — 2026-10-03, final

The event's own harness, run against this submission, kept rather than summarised.

```
python3 harness run --track pocketful --repo <this repository> --all --mode isolated
```

## What this directory is

`2026-10-03-final/` is the run. It holds:

| File | What it is |
|---|---|
| `summary.json` | what the run decided, across all four folders |
| `stage-N/report.json` | one folder's result: every suite that ran against it, and the share it passed |
| `stage-N/stage-M.log` | the full pytest output of one suite against one folder, unedited |

## What the result is

| Folder | Claims | share | Overshoot | Highest contiguous |
|---|---|---|---|---|
| `stage-1/` | stage 1 | 1.0 | none | 1 |
| `stage-2/` | stage 2 | 1.0 | none | 2 |
| `stage-3/` | stage 3 | 1.0 | none | 3 |
| `stage-4/` | stage 4 | 1.0 | none | 4 |

`overshoot` is the part worth reading twice. The harness also runs each folder against the
**next** stage's suite, because a folder that passes it is a later answer filed in the wrong
place and claims nothing. Every folder here reports `null`, so none of them is that.

The number is not the whole story, and FACTORY.md §2 says so: the event ships only part of
each stage's checks. Stage 1's 147 and stage 2's 35 are a real sample of the grading suite;
stage 3 ships 6 and stage 4 ships 5, so for those two this result is close to a smoke test.
What carries them is the reviewer's own adversarial scenarios in
[`holdouts/`](../../holdouts/), which CI re-runs against every build.

## How the tree it ran against was produced

This is the part that decides whether the run means anything. A directory you worked in
contains files a clone does not: uncommitted edits, a `.env`, a `server.log`, a nested `.git`
inside a stage folder that git would record as a link. Everything below builds in that
directory and arrives empty for a judge.

So the run was made against an export of the committed tree only:

```bash
git archive --format=tar HEAD:build/pocketful-factory | tar -x -C <dir>
python3 harness run --track pocketful --repo <dir> --all --mode isolated
```

90 files, exactly the committed set, with no `.env`, no `agent_config.yaml`, no virtualenv
and no logs. `harness check` reports **0 problems** on that same directory, which is the
offline half of gates 1, 2 and 4.

`report.json` records `revision: ""`, and that is honest rather than a gap: the export is not
a git checkout, so there is no commit hash to read. The commit it corresponds to is the one
whose tree produced it, and the run's `started_at` is on it. The earlier evidence this
directory replaces was taken from the working directory instead, which is why it could not
answer the question this one can.