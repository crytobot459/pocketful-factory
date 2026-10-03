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

- [ ] `room.json` is a **full session** download, not a filtered one, saved unchanged.
- [ ] Two of your own seats exchanged `@handle` messages in both directions. The judge reads this
      out of the file; confirm it is really there rather than assuming it.
- [ ] No seat posted a filler message. `Standing by`, `Noted`, `Acknowledged`, `Quiet`,
      `Holding`, `Waiting` — one of those in the log costs more than a quiet room would have.
- [ ] The work is **distributed**. One seat carrying 90% of it reads the same however many
      messages it sent.
- [ ] Every revision the room mentions has a commit. Code with no discussion behind it is code
      the band did not write.

## The documents

- [ ] `README.md` and `FACTORY.md` are written, not placeholders.
- [ ] Every number in `FACTORY.md` can be traced to the room log, the git history or the harness
      report. Check them; a document that overstates is worse than one that admits a gap.
- [ ] Every mandate could be pointed at a different problem. Any endpoint path, field name,
      error code or check id disqualifies the entry.
- [ ] `room.json` is the last download, so it holds the whole collaboration.

## The presentation

- [ ] The video shows **the factory working**: the room, a handoff between seats, and the result
      it produced. A slideshow about the factory is not the factory.
- [ ] The video contains a moment where the reviewer found something wrong. Correct work
      accepted first time loses nothing, but a run where nothing was ever caught shows a veto
      that was never exercised.
- [ ] The presentation covers the factory design, what it cost, a bad result it caught, and the
      stage it reached.
- [ ] Submit the repository URL, the presentation and the video, then keep the receipt.