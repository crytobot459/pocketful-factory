# Deck — pocketful-factory

10 slides. One idea per slide. Every number on a slide is one the band actually reported in the
room or the event harness produced.

---

## 1. The problem

A wallet's users do three things: send money, ask for it, split a bill. Underneath, one rule
has to hold no matter what: **the money in the system never changes.**

Not "mostly". Never. Not under a retry, not under twenty simultaneous transfers from one
account, not when a split does not divide evenly, not when a request to save and export your
state comes back twice.

Getting this right by reading diffs is the expensive part. A senior reviewer takes about two
hours per change to a money-moving path, and they are reviewing *correctness under
concurrency*, which is exactly the thing a diff does not show.

## 2. What we built

A factory, not a service. Three coding agents that build the service:

- one **decomposes** a stage of the specification and routes it
- one **implements** to the specification, runs the checks, commits
- one **verifies** that exact commit and **vetoes** it if it is wrong

They share one room. Once a stage is dispatched, no human is in the loop until the stage is
locked.

## 3. Why a factory and not a better code review

Code review catches what a human thought to look at. The factory's reviewer was told what to
look for: same key fired ten times at once, a response lost after the server already committed,
a snapshot restored twice, a page whose state went stale under it.

Those are not things a reviewer remembers at 5pm on a Friday. They are a list.

## 4. The reviewer has real teeth

The reviewer never writes service code. It cannot make a failing check pass by editing the
thing being checked.

It writes its own scenarios, in its own file, which the implementer is forbidden to read. What
it found that the published checks never asked for:

| | Scenario | What the shipped checks would have said |
|---|---|---|
| stage 1 | a snapshot restored twice duplicates records | fine |
| stage 2 | a hidden error element survives a successful payment | fine |
| stage 2 | the split preview disagrees with the server by one minor unit | fine |
| stage 3 | a statement changes under you while you page through it | fine |

Each became a rejection with numbers, and the fix came back through the room as a new commit.

## 5. What it produced

Four stages of the wallet specification. Each folder is a complete service that builds from a
clean container and passes every earlier stage's checks as well as its own.

| Stage | Shipped checks run against it |
|---|---|
| 1 — the API | 147 / 147 |
| 2 — the browser product | 147 + 35 |
| 3 — history and corrections | 147 + 35 + 6 |
| 4 — refunds and batch corrections | see the repository |

## 6. Verified by the event's own harness

Not by us. The organiser's harness, isolated mode, building each folder from scratch:

```
stage-1/  claims stage 1     share 1.0
stage-2/  claims stage 2     share 1.0
stage-3/  claims stage 3     share 1.0
highest contiguous stage: 3
```

Nothing is claimed on our word. The report is committed at `docs/harness-runs/`.

**And the honest caveat:** the event ships part of each stage's checks. Stage 3 is six published
checks. That number is directional, and we say so in the factory document rather than let a
judge work it out.

## 7. What it cost

**$0.** Every seat ran on a free tier.

Room window: about 25 hours wall-clock across two calendar days, of which the useful work was
roughly four. The rest was infrastructure: restarting seats, draining a backlog from an
abandoned earlier room, and one long verification that had to be split in two.

## 8. It failed in instructive ways

A factory that never fails is a diagram.

- One seat was checking out a revision to review it and moved `HEAD` off the branch tip,
  stranding a later commit. Recovered from the reflog; the dispatch for the next stage now
  forbids a bare `git checkout`.
- The room downloader silently returned half the room and counted zero seats. It looked like
  the room proved nothing. It was the script.
- Two seats edited the same file at once in the last stage. The architect refused to hand off
  blind, partitioned ownership, and had it reconciled.

All three are written up in `FACTORY.md`, because that is what saves the next team the day.

## 9. Who it is for

Teams who ship money-moving code and cannot afford a two-hour review per change — and who do
not trust a black box to do it.

The factory is not vendor-specific. Three mandates, three adapters, one room. Point it at a
different specification and the routing, the veto, and the discipline transfer unchanged.

## 10. What we would do next

- The last stage's checks were the thinnest of the four. More holdouts, written before the
  implementation rather than after, would catch more.
- A seat-per-worktree setup. Two seats editing one directory is a coordination problem this
  factory currently solves with a ruling instead of a lock.
- A reviewer that writes its scenario *first* and hands it to the implementer as the task,
  instead of discovering the gap afterwards. That is the real version of test-first, and it
  needs a seat that can hold a spec without writing code.