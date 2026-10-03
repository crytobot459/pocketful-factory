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

| Stage | Folder | Locked at | Shipped checks run against it |
|---|---|---|---|
| 1 | `stage-1/` | `35e2fa1` | 147 / 147 |
| 2 | `stage-2/` | `bea1c8a` | 147 + 35 |
| 3 | `stage-3/` | `92d9a5f` | 147 + 35 + 6 |
| 4 | `stage-4/` | `b88cb7b` | 147 + 35 + 6 + 5 |

Verified by the event harness, not by us:

```
python -m harness run --track pocketful --repo . --all --mode isolated
  stage-1/: claims stage 1 on the shipped checks   share 1.0
  stage-2/: claims stage 2 on the shipped checks   share 1.0
  stage-3/: claims stage 3 on the shipped checks   share 1.0
  stage-4/: claims stage 4 on the shipped checks   share 1.0
  highest contiguous stage: 4
```

Every folder scored `share 1.0` and no folder passed the next stage's whole suite, so none of
them is a later answer filed in the wrong place. The full report is in `docs/harness-runs/`.

**What that number is worth, stated plainly.** The event ships only part of each stage's
checks. Stage 1's 147 and stage 2's 35 are a real sample of the grading suite. Stage 3 ships 6
checks and stage 4 ships 5, so for those two the harness result is close to a smoke test. What
carries them is the reviewer's own adversarial work below, not the five and six.

## 3. Design choices, and what they cost

**One room for every stage, and stage folders carried forward.** A new room per stage would
have given four clean logs and four disconnected factories. One room means the log shows a
factory that kept going, and the copy-forward is what forces each stage to keep the earlier
contracts rather than rewriting them.

**The reviewer has teeth, and the teeth are the scenarios.** The tester never writes service
code. It cannot make a failing check pass by editing the thing being checked.

It writes its own adversarial scenarios, in its own folder, which the implementer is forbidden
to read. What it found that the published checks never asked for:

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
  statements stay frozen across writes landing between pages; a lost response after a correction
  replays rather than moving money twice; two parties see two different statements; the
  arithmetic in a statement reconciles; conservation holds at the end of the run.
- stage 4 — S4-H1..S4-H10: the refund cap follows the *corrected* amount, not the original, so a
  correction downward makes an over-refund fail; refunding a refund is refused; a correction
  cannot be applied to a refund; a correction cannot take a payment below what has already been
  refunded; only the receiver may refund; a batch correction touching one member of a settlement
  changes nothing at all; a batch is checked for money across all its members together.

**Two honest weaknesses in that list.** The stage-3 and stage-4 scenarios were graded inside the
reviewer's session and written to `holdouts/stage-3.md` and `stage-4.md` afterwards, transcribed
from the verdicts; the first two stages were written before verifying. Those two files say so at
the top. And there is **no rejection in this room**: eight verdicts, all ACCEPT. The reviewer
did change the work — the stage-2 error-element and split-preview defects and all three stage-4
gaps were found by it and fixed by the implementer — but it found them by reporting acceptance
with findings attached rather than by vetoing. A future run should veto at least once so the
room shows the veto actually stopping something.

**Every one of those scenarios is now executable.** `holdouts/run_scenarios.py` runs them
against a live service, named after the note each came from, and prints expected against actual:

```bash
python3 holdouts/run_scenarios.py --base-url http://127.0.0.1:8080 --stage 4
```

CI runs it against all three stages. Writing them down was the first half of making them
countable; being able to re-run them without the reviewer in the room is the second half.

**They were also checked against every revision in this repository's history, and that found
nothing to reject.** The claim in the room is that `ed2a419` failed the snapshot-restored-twice
check and `35e2fa1` fixed it. Re-running that scenario against both produces identical results,
so the difference between them is not observable through the API: it is Python object aliasing
inside the process, which no request can reach. Every stage folder also passes every shipped
check, and the reviewer's own stage-3 and stage-4 scenarios pass against the current build. So
there is no honest rejection to be had from this run, and inventing one would be worth nothing —
which is also what the event says about manufactured conflict.

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
| The split preview did not match what the server recorded | reviewer, stage 2 | preview text reduced to the amount alone, in the element the checks address |
| The refund cap used the original amount, so a correction downward did not tighten it | reviewer, stage 4 | cap recomputed against the latest corrected amount |
| A batch correction could be applied to a settlement without all of its members | reviewer, stage 4 | completeness check, plus affordability summed across members |
| A reviewer checking out a revision moved HEAD off the branch tip and stranded a later commit | human, watching the reflog | branch fast-forwarded from the reflog; no history rewritten, because the stranded commit was a descendant of the tip |
| That same checkout made a verdict land against the wrong revision | reviewer, then architect | the architect refused to lock `b88cb7b` on a verdict for `92d9a5f` and sent it back. The reviewer's mandate now forbids a bare `git checkout <sha>` |
| The implementer's turn was cut off at 900 seconds part-way through stage 4 | human | turn timeout raised and taken from the environment; the stage-4 dispatch was posted again unchanged |
| Two implementations of the same endpoints existed at once in a carried-forward folder | architect, at the start of stage 3 | refused to hand off blind, isolated the duplicate, had the implementer reconcile to one and re-run |
| Two seats edited one file at once during stage 4 | coder reported it, architect partitioned | ownership of `app.py` assigned to one seat, the other held |
| The room download returned 50 of 113 messages and counted zero seats | human, comparing the log against what the seats were doing | the downloader pages properly and compares the sender type case-insensitively |

The first six are the factory working: a seat found a defect the published checks did not name,
reported it with numbers, and the fix came back through the room as a new revision. The rest are
what it costs to run three agents on one machine, and they are the kind of thing a written
factory document should save another team from rediscovering.

## 5. Cost and time

- Model spend: **$0**. Free tiers throughout.
- Room window covered by `room.json`: 2026-10-02T02:54Z to 2026-10-03T04:20Z, about 25 hours.
- 113 messages: 49 seat messages (27 architect, 13 coder, 9 tester), the rest tool calls, tool
  results and usage events. Eight verdicts, all ACCEPT; seven stage locks.
- Tokens the room recorded: 191,555 in / 16,068 out, all attributed to the architect seat. The
  coder and tester seats report usage through their own adapters and their counts are not in the
  room log, so these are a floor, not a total.
- Wall-clock overhead that was not work: seat restarts, draining the backlog of an abandoned
  earlier room, and two verifications that ran past the turn deadline and had to be restarted.
- One human message went into the middle of stage 4, re-posting that stage's dispatch unchanged
  after the implementer's turn was cut off. That is the sort of thing the collaboration is meant
  not to need, and it is recorded here rather than left for someone to notice in the log.

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