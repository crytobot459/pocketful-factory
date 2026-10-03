# FACTORY.md — pocketful-factory

A band of three coding-agent seats that plans work, implements it, and independently checks
its own result against a written specification, in one room, without a human in the loop once
a stage is dispatched.

What is submitted here: the factory, the room it worked in, and the code it produced.

---

## 1. The seats

Three seats, three roles, one room. The seat names are the ones the room records.

| Seat | Role | Harness | Model |
|---|---|---|---|
| `factory-architect-df` | decomposes a stage and routes it; never writes code | OpenCode | `opencode/muse-spark-1.3-contributor-free` |
| `factory-coder-df` | implements to spec, runs the checks, commits; never accepts its own work | OpenCode | `opencode/muse-spark-1.3-contributor-free` |
| `factory-tester-df` | verifies a named revision and vetoes; never edits code | OpenCode | `opencode/nemotron-3-ultra-free` |

The first two share a model. The reviewer does not, on purpose: a reviewer on the implementer's
model shares its blind spot, which is the one thing a reviewer must not do. Under free-tier
outage the reviewer may fall back further; `FACTORY.md` records which model actually ran in
every verdict it issues.

Each mandate opens with the harness and model its seat runs, and each is named after the seat
rather than after the role, so the roster in this table and the roster in `room.json` are the
same roster.

## 2. What the band produced

Four stages of the `pocketful` wallet specification. Each folder is a complete service that
builds from a clean container and passes every earlier suite as well as its own.

| Stage | Folder | Locked at | Shipped checks against it |
|---|---|---|---|
| 1 | `stage-1/` | `35e2fa1` | 147/147 |
| 2 | `stage-2/` | `bea1c8a` | 147 + 35 |
| 3 | `stage-3/` | `92d9a5f` | 147 + 35 + 6 |
| 4 | `stage-4/` | see `docs/harness-runs/` | — |

Verified by the event harness, not by us:

```
python -m harness run --track pocketful --repo . --all --mode isolated
  stage-1/: claims stage 1 on the shipped checks
  stage-2/: claims stage 2 on the shipped checks
  stage-3/: claims stage 3 on the shipped checks
  highest contiguous stage: 3
```

The full report is kept in `docs/harness-runs/`. Every folder scored `share 1.0` and no folder
passed the next stage's whole suite, so none of them is a later answer filed in the wrong place.

**What that number is worth, stated plainly.** The event ships only part of each stage's
checks. Stage 1's 147 and stage 2's 35 are a real sample of the grading suite. Stage 3's is
**6 checks**, and stage 4's shipped sample is smaller still. So "claims stage 3" means six
published checks plus whatever the reviewer's own adversarial notes found, not a stage 3 the
judges' full suite will confirm. Read the reviewer's counts below for what was actually
independent of the shipped checks.

## 3. Design choices, and what they cost

**One room for every stage, and stage folders carried forward.** A new room per stage would
have given four clean logs and four disconnected factories. One room means the log shows a
factory that kept going, and the copy-forward is what forces each stage to keep the earlier
contracts rather than rewriting them.

**A reviewer with veto, and the veto is the point.** The tester never writes service code. It
checks out the exact revision it was given, runs the shipped checks itself, and writes its own
adversarial scenarios in `holdouts/`, which the implementer is forbidden to read. What it
produced, beyond the shipped checks:

- stage 1 — H1..H10: lost-response retry moves money once; a burst of 10 identical writes
  yields 1 effect and 9 replays; a reused marker with a different body conflicts and moves
  nothing; a failed write does not claim its marker; a drain race keeps the total constant and
  never goes transiently negative; a group move commits fully or not at all; uneven division
  differs by at most one minor unit with the earlier member favoured; a hidden activity is
  visible to its parties and nobody else; a snapshot restores twice without duplication or loss.
- stage 2 — S2-H1..S2-H12: a refusal is shown where the person is looking and the balance does
  not move; no error element survives a successful action, so "no error" is distinguishable
  from "error dismissed"; two clicks move the money once; editing before submitting is a new
  action; the split preview equals what the server records to the minor unit; a stale page
  re-reads before acting; a lost response after commit is recoverable without guessing; holds
  change the total only by what was captured; every screen state has a testable element.
- stage 3 — S3-H1..S3-H11: a correction that fails for funds changes nothing; a correction that
  succeeds leaves no error; a stale `expected_revision` conflicts rather than overwriting;
  statements stay frozen across writes landing between pages; a snapshot token is rejected when
  combined with a range; another person's snapshot is not readable; a view pinned to an instant
  does not move when a correction lands afterwards; arithmetic in a statement reconciles against
  balances; conservation holds at the end of the run.

**Explicit message discipline, because the first attempt at this failed.** The run this factory
submitted before had 482 messages in it, of which the reviewer wrote five, and roughly half were
sentences announcing that the sender was waiting. Every mandate now names the sentences that
are forbidden outright — "Standing by", "Noted", "Acknowledged", "Quiet", "Holding",
"Waiting" — and states that silence, not a placeholder, is the correct output. The run in
`room.json` has 41 seat messages and every one of them carries a revision, a count or a
verdict.

**Free tiers only.** Cost to run the whole thing: $0. The seats run on OpenCode's free models
and a Gemini key, all of which rate-limit. Fallback is declared per seat in
`band-agents/.env.example` and the mandate logic does not change when a seat falls back.

## 4. Catching and recovering from bad work

| What went wrong | Who found it | What it took to recover |
|---|---|---|
| Snapshot restore applied twice duplicated records | reviewer, stage 1 H9 | implementer rewrote the restore path: validate everything, deep-copy, swap atomically |
| The browser left a hidden error element in the DOM after success | reviewer, stage 2 | element created on demand and removed when cleared, so "no error" is a real state |
| A list reload wiped the error the failed action had just set | reviewer, stage 2 | the reload stopped touching the error; only the action decides |
| The split preview did not match what the server recorded | reviewer, stage 2 | preview text reduced to the amount alone, in the element the tests address |
| Two implementations of the same endpoints existed at once in a carried-forward folder | architect, at the start of stage 3 | architect refused to hand off blind, isolated the duplicate, had the implementer reconcile to one and re-run |
| The reviewer checking out a revision moved HEAD off the branch tip and stranded a later commit | human, watching the reflog | branch fast-forwarded from the reflog; no history rewritten, because the stranded commit was a descendant of the tip. The stage-4 dispatch now forbids a bare `git checkout <sha>` for exactly this reason |
| The room download returned 50 of 95 messages and counted zero seats | human, comparing the log against what the seats were doing | the downloader pages with a cursor, and compares the sender type case-insensitively |

The first four are the factory working: a seat found a defect the published checks did not
name, rejected or flagged it with numbers, and the fix came back through the room as a new
revision. The last two are what it costs to run three agents on one machine, and they are the
kind of thing a written factory document should save another team from rediscovering.

## 5. Cost and time

- Model spend: **$0**. Free tiers throughout.
- Room window covered by `room.json`: 2026-10-02T02:54Z to 2026-10-03T03:27Z.
- Tokens the room recorded: 191,555 in / 16,068 out, all attributed to the architect seat. The
  coder and tester seats report usage through their own adapters and their counts are not in the
  room log, so these are a floor, not a total.
- Wall-clock overhead that was not work: roughly 40 minutes on the stage-1 run went to seat
  restarts and to draining the backlog of the abandoned room.

## 6. Standing this up on a different problem

The factory is the room plus three mandates plus the adapters. Nothing in it names this track.

1. Copy `FACTORY.md` and `mandates/` into a new repository.
2. Write one holdout file per stage for the reviewer. Plain English scenarios, never pasted into
   the room.
3. Point the three adapters at the new repository and the new specification paths. The model and
   provider come from the environment; see `band-agents/.env.example`.
4. Create three seats whose names match the mandate filenames, fill in `agent_config.yaml`,
   and dispatch. The dispatch text in `ROOM_DISPATCH.md` is the shape to copy.
5. Check with the event harness before publishing, and run it against a fresh clone rather than
   the directory you worked in.

The routing rules, the veto, the message discipline and the copy-forward discipline are the
parts that transfer. The stage folder layout is not — that is the event's shape.

## Appendix: the invariants this problem is about

Kept here because they are what the reviewer's adversarial notes are actually probing, and
because a reviewer reading them cold should know what "correct" means here.

- Five stage-1 write paths take an idempotency key. Replaying the same key with the same body
  replays the response; replaying it with a different body conflicts and moves nothing; a write
  that fails validation never claims its key.
- Balances always sum to the seeded total, never transiently negative. Money moves between
  wallets only.
- Splits divide to the minor unit with the earlier-listed member taking the odd unit.
- A hold reserves without moving anything; only a capture moves money.
- A snapshot restores atomically and idempotently, and a key issued before a restore still
  works after it.
- A statement is frozen at the instant it was taken; later writes do not change what it said.