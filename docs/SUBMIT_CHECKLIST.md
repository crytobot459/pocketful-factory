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
- [ ] The video contains the **BAND room** recording. This is a hard disqualifier, not a scoring
      item: the event states a video without it disqualifies the team. Two things about ours are
      worth knowing before you decide whether to re-shoot anything:
  - The room shot is `app.band.ai/sessions/affa9999-...` in a browser, not the Band Desktop
    binary. The band was driven by the BAND CLI and the agent API from three terminals, which
    the event explicitly allows ("a seat can be any runtime BAND supports, including one you
    build on the BAND SDK and run on your own machine"), and the room it recorded is the room
    `room.json` exports — same id, same 121 messages, same verdicts.
  - It cannot be in Band Desktop's sidebar, and that is a property of the room rather than a
    missing export: `jam room participants` lists `factory-architect-df` as owner, so the
    human-account room list leaves it out and `jam room rename` answers 403.
  - So the shot has to *say* that, rather than leave a judge to work out why the app in the
    video is a browser. The narration names it, and shot three prints the same room back with
    BAND's own CLI. If you would rather not rely on that, the alternative is installing Band
    Desktop and finding a room it will list — which for this room there is not.
- [ ] The video shows the reviewer finding something the shipped checks never asked for — and it
      says plainly what form that took. In this run it reported six findings attached to
      acceptances and never vetoed, so the honest shot is a verdict carrying numbers, plus the
      sentence that the veto is untested. A video claiming a veto that the log does not contain
      is worse than one that admits the gap.
- [ ] The presentation covers the factory design, what it cost, a bad result it caught, and the
      stage it reached.

## The demo URL

- [ ] `crytobot459/pocketful-demo` is public and its default branch is `main`, with
      `streamlit_app.py` at the **root**. The deploy form asks for a repository, a branch and
      a main file path, and all three are validated against each other: pointing it at
      `crytobot459/pocketful-factory` gives "this branch does not exist" and "this file does
      not exist", because that repository has no `streamlit_app.py` and its branch is `main`.
- [ ] `bash deploy/build_demo_repo.sh --check-only` is green **before** anything is pushed. It
      drives the page itself, not the functions behind it, and it covers a first visitor and a
      second one on the same service.
- [ ] Open the deployed URL and click Seed, Sign in as Ada, Fire it twice. Then reload and do
      it again. A URL that only works once is not a demo URL, and this is a public one: the
      free tier sleeps, the first request after a pause takes 30-60 seconds, and the service is
      one wallet shared by every visitor, so seeding is what puts it back to `EUR 100.00`.
- [ ] Say the sleep in the form. A judge who opens a 40-second blank page concludes the demo is
      broken, and nothing in the submission is worth more at that moment than the first click.

## The form, field by field

The form is `https://lablab.ai/ai-hackathons/wearedevelopers-hackathon` reached from the team
page, and it is three steps: basic information, media, then the submission itself.

**It does ask for a demo URL.** An earlier draft of this file said it did not, and that was
wrong — it was written from memory of the event page rather than from the form, and it would
have sent the submission in with a required field empty. The wallet is a FastAPI service, not
a Streamlit app, so the demo is `crytobot459/pocketful-demo`: `streamlit_app.py` at the root
starts `stage-4/src/app.py` as a subprocess and drives it over HTTP. `deploy/` holds the source
of that page and `deploy/build_demo_repo.sh` assembles, checks and pushes it. The service
under the page is byte-identical to the stage in this repository, and the build refuses to
push if it is not.

| Field | Value |
|---|---|
| Submission title | `Pocketful Factory: three agents, one room` (41 of 50) |
| Short description | 249 of 255, below |
| Long description | 1862 of 2000, below |
| Categories | `Coding` |
| Event Tracks | `pocketful` |
| Technologies Used | `Band Intergrations`, `Band Agentic Mesh`, `Band Control Plane` |
| Cover image | `docs/cover.png` (1920x1080) |
| Video presentation | the video file, uploaded separately from the slides |
| Slide presentation | `docs/DECK.pdf`, 11 slides at 1280x720 CSS px (a 960x540 pt page — same 16:9) |
| Repository | `https://github.com/crytobot459/pocketful-factory` (public, 42 commits, CI green) |
| Demo Application Platform | `Streamlit` |
| Demo Application URL | the deployed `https://<app>.streamlit.app` |

The form measures **50 characters** on the title and **2000** on the long description, so both
of the drafts that read better are wrong for this form and are not the ones below.

The form's technologies list is fixed and the entries above are the whole of it: an earlier
draft here listed `python`, `ai-agents`, `multi-agent`, `docker` and `agent-harness`, none of
which the form offers. Everything it does offer names BAND, which is the point.

**Long description** (paste exactly, 1862 characters):

> We did not build a wallet app. We built the thing that builds one, and pointed it at a wallet.
>
> Three coding-agent seats share one BAND room. One decomposes a stage of the written specification and routes it, one implements to that specification, runs the checks and commits, and one reviews that exact revision and replies ACCEPT or REJECT. The reviewer never edits service code, so it cannot make a failing check pass by changing the thing being checked, and it writes its own adversarial scenarios in a folder the implementer is forbidden to read.
>
> The band reached stage 4. Each stage-N/ folder is a complete service that builds from a clean container, answers /health with no outbound network, and still passes every earlier stage's suite: 147 checks at stage 1, +35 at stage 2, +6 at stage 3, +5 at stage 4, plus the reviewer's own scenarios. The event's own harness scored every folder share 1.0, highest contiguous stage 4.
>
> Once a stage was dispatched no human touched it again. That is a property of the room, not of this paragraph: all 121 messages in room.json carry an agent sender and not one is from a human. The reviewer found six defects the published checks never named, and every fix came back through the room as its own commit.
>
> What we will not claim: the reviewer never actually vetoed anything. Every verdict in the room is an ACCEPT, six carrying findings. The veto the factory is built around is untested in this run, and FACTORY.md says so rather than leaving it for a judge to find.
>
> The factory is three mandates, three adapters and one room. The mandates name no endpoint, no field and no error code, so they could be pointed at a different specification tomorrow. verify_claims.py checks all 36 figures in the documents against room.json, the git history and the committed harness report, and CI fails the build when one disagrees.

**Short description** (paste exactly, 249 characters):

> Three coding-agent seats in one BAND room build a wallet to spec: one decomposes a stage, one implements it, one checks that exact revision and can veto it. Four buildable stages, the room export, every number checked against its evidence. Cost: $0.

Then: submit, and keep the receipt — a screenshot of the confirmation and the submission URL.

- [ ] Submit the repository URL, the presentation and the video, then keep the receipt.
