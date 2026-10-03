# Before you submit

A checklist, in the order the failures actually happen. Each step names the thing it catches.

## The repository

- [ ] `python -m harness check <clone> --track pocketful` prints **ok**. Run it against a **fresh
      clone**, never the directory you worked in: a file you forgot to commit and a stage folder
      that is its own git repository are both invisible from your working tree and both arrive
      empty for a judge.
- [ ] Move `.env` and `agent_config.yaml` out of the tree first. `check` scans gitignored files,
      so it will report a credential that was never going to be published.
- [ ] `python -m harness run --track pocketful --repo <clone> --all --mode isolated` — every
      stage folder builds and claims its stage. This is gate 3 and nothing else checks it.
- [ ] Follow each `stage-N/RUN.md` by hand in a clean environment, then open the UI. No offline
      check covers whether the service actually starts.
- [ ] `git log --oneline` shows one commit per revision the room discusses, no amends, no
      rebases, no squashes.
- [ ] Scan for credentials once more by eye. The scanner looks for shapes; it cannot know every
      private value. If you find one, rotate it — deleting the line does not unpublish what was
      already pushed.

## The room

- [ ] `room.json` **reaches the end of the room**: it carries the message that locks stage 4.
      Not "the scope field says full" -- the exporter writes that string itself, so checking
      it only proves the exporter is self-consistent. This export once stopped two hours
      early, five seconds after the architect flagged a verdict issued against the wrong
      revision, and the acceptance and the lock that ended the run were both missing from
      the file. `verify_claims.py` fails on an export that does not reach the end, so this
      is checked rather than remembered.
- [ ] Two of your own seats exchanged `@handle` messages in both directions. The judge reads this
      out of the file; confirm it is really there rather than assuming it.
- [ ] No seat posted a filler message. `Standing by`, `Noted`, `Acknowledged`, `Quiet`,
      `Holding`, `Waiting` — one of those in the log costs more than a quiet room would have.
- [ ] The work is **distributed**. One seat carrying the great majority of it reads the same
      however many messages it sent; here the split is 28/13/11, so the architect is at 54%.
- [ ] Every revision the room mentions has a commit. Code with no discussion behind it is code
      the band did not write.
- [ ] `room.json` is the **last** download, taken after the last thing the band did. Re-export
      with `band-agents/fetch_room.py`, not by hand.

## The documents

- [ ] `README.md` and `FACTORY.md` are written, not placeholders.
- [ ] Every number in `FACTORY.md` can be traced to the room log, the git history or the harness
      report. Check them; a document that overstates is worse than one that admits a gap.
- [ ] `python3 verify_claims.py` passes, and it passes **after** you break it on purpose. Put
      the stage count back, invent a rejection, and check that it fails. A checker that has
      never been shown a lie is not known to work.
- [ ] Every mandate could be pointed at a different problem. Any endpoint path, field name,
      error code or check id disqualifies the entry.

## The presentation

- [ ] The video shows **the factory working**: the room, a handoff between seats, and the result
      it produced. A slideshow about the factory is not the factory.
- [ ] The video contains the **BAND Desktop room** recording. This is a hard disqualifier, not a
      scoring item: the event states a video without it disqualifies the team. It has to be the
      app, not `app.band.ai` in a browser, and it has to be long enough to read.
- [ ] The video shows the reviewer finding something the shipped checks never asked for — and it
      says plainly what form that took. In this run it reported six findings attached to
      acceptances and never vetoed, so the honest shot is a verdict carrying numbers, plus the
      sentence that the veto is untested. A video claiming a veto that the log does not contain
      is worse than one that admits the gap.
- [ ] The presentation covers the factory design, what it cost, a bad result it caught, and the
      stage it reached.
- [ ] Submit the repository URL, the presentation and the video, then keep the receipt.
