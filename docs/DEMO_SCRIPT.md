# Demo script — the video shows the factory working

Target length 3 to 4 minutes. This is a screen recording of things that actually run, not a
narration over slides. Every command below has been run and produces the number quoted.

The narrated demo (`python3 demo.py`) reads the room, the git history and the harness report
out loud. Record that as the spine of the video and cut to the terminal while it runs.

---

## 0:00 — What this is

Terminal, nothing else on screen.

> Three coding agents in one room. One decomposes a stage of a specification, one implements it,
> one checks it and can veto. Once a stage is dispatched, I am not in the loop until it is locked.

## 0:20 — The room, before anything is built

BAND Desktop (jam). Open the room the band worked in and scroll it.

Point at three things and say them:

- the seat names: `factory-architect-df`, `factory-coder-df`, `factory-tester-df`
- a handoff, where the coordinator names a task and the revision to verify
- a verdict, which names a revision and carries numbers

> This is not a chat log. Every message either carries a revision, a count or a decision. The
> run before this one had 482 messages and the reviewer wrote five of them.

## 1:00 — A handoff, start to finish

Terminal. Run the narrated demo and let it speak while the output scrolls.

```bash
python3 demo.py
```

It prints and reads out: the seats and their models, the room's message count and how it splits
across them, the stages each locked at, the verdicts, the token usage, and what the event
harness said.

> The room is 121 messages. Fifty-two of them are the agents speaking, split 28, 13 and 11.
> Ten verdicts. Seven stages locked.

## 2:00 — The reviewer catching something

This is the part that makes the video. If you have no moment where review stopped something,
the run has not shown you a factory.

Cut to the room and to the git log together:

```bash
git log --oneline -- stage-4/src/app.py
```

> The reviewer checks the exact revision it was handed and writes its own scenarios — the
> ones the published checks never asked for. It found the refund cap being computed from the
> original amount rather than the corrected one, so a correction downward did not tighten
> what could be refunded; and a batch correction that could be applied to a settlement
> without all of its members. Two defects in stage 4, one revision, both found by the seat
> that is not allowed to fix them — and the fixes came back as a new commit, `b88cb7b`.
> Across the four stages it found six, and the list with the revision each was locked at is
> slide 4 of the deck.
>
> Say it plainly: in this run the reviewer never vetoed. Ten verdicts, all ACCEPT — the
> findings arrived attached to acceptances. The veto is still untested, and that is in the
> factory document rather than hidden from it.

## 2:30 — The service the factory built

Terminal, then browser.

```bash
cd stage-4 && pip install -r requirements.txt && PORT=8080 python3 -m src.app
curl -s http://127.0.0.1:8080/health
```

Browser on <http://127.0.0.1:8080/>. Seed the published fixture first with
`POST /_test/reset` — nothing is seeded at container start, see `stage-4/RUN.md` — then
sign in as `ada@example.com` / `correct horse`.

Show three things, quickly:

- the balance, and that it always equals the sum of every wallet
- a split preview for an amount that does not divide evenly, and that it agrees with what the
  server records to the minor unit
- a refusal, and that the balance did not move

> The reviewer found that one: a hidden error element survived a successful payment, so the page
> could not tell you apart from no error at all.

## 3:30 — Verified by the organiser's harness, not by us

Terminal.

```bash
python -m harness run --track pocketful --repo . --all --mode isolated
```

Scroll the summary.

> Four stage folders, built from clean containers. Each one passes every earlier suite as well
> as its own. Highest contiguous stage: four. No folder passes the next stage's whole suite,
> which would have meant an earlier folder was a later answer filed in the wrong place.

## 3:50 — What it cost, and what broke

Terminal, `git log --oneline`.

> Zero dollars. Free tiers throughout, about 28 hours of room window for three stages of real
> work.
>
> And it broke in ways worth hearing about. A seat checked out a revision to review it, which
> moved HEAD and stranded a commit; that happened twice and the mandate now forbids it. One turn
> hit its deadline mid-edit and had to be re-dispatched, which is the sort of thing this factory
> is supposed to not need. The room downloader silently returned half the room, so the log
> looked like it proved nothing when it was the script.

## 4:00 — Close

> The factory is three mandates, three adapters and one room. Point it at a different
> specification and the routing, the veto and the discipline carry over unchanged.

---

## Recording notes

- `bash work/video/record_demo.sh` sets the whole thing up: it serves stage-4 from the
  committed tree, seeds the published fixture through `POST /_test/reset`, opens BAND
  Desktop on the room `pocketful-factory-v2`, opens the product, runs the reviewer's
  scenarios and then `verify_claims.py`, and starts `screencapture`. `--serve-only` skips
  the windows, `--no-capture` skips the recorder. Every shot below is one of its steps, in
  that order, so the recording is reproducible rather than retyped.
- The room shot is BAND Desktop (`/Applications/Jam.app`), not a browser tab. The event
  disqualifies a video without the BAND Desktop room recording, and `app.band.ai` shows the
  same room but is not the thing the rule names.
- Record at 1920×1080 so the terminal text is legible when scaled down.
- `demo.py` needs no key. Speech is skipped silently if `edge-tts` is missing; install it with
  `pip install edge-tts` to have the narration.
- Cut on the numbers, not on the sentences. Every figure quoted above is in `docs/DECK.md` and in
  `FACTORY.md`, and both are traceable to `room.json` or the harness report.
- Do not run `python -m harness run` on camera. It takes minutes and the report is already
  committed under `docs/harness-runs/`; `python3 verify_claims.py` says the same thing in a
  second, and it also checks the documents.
