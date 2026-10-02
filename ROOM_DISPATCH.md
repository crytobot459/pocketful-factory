# ROOM_DISPATCH — room `pocketful-factory-v2`, seats `factory-*-df`

Room: `affa9999-88af-4bef-b731-55957ba9af33`. Stage 1 ran here on 2026-10-02 and is locked at
`35e2fa1`. The 482-message room before it was abandoned and is not part of this submission; the
reviewer sent five messages in 482 there.

## Standing the room up

1. `opencode serve --hostname=127.0.0.1 --port=4096`
2. In `band-agents/`: `cp .env.example .env` and fill in the model keys, then
   `cp agent_config.example.yaml agent_config.yaml` with the three seat credentials.
   `REVIEWER_USE_FALLBACK=1` runs the reviewer on an OpenCode free model rather than the
   primary tier; see FACTORY.md for why that is accepted.
3. Three terminals in `band-agents/`: `uv run python coordinator.py`, `implementer.py`,
   `reviewer.py`. Wait for three `connected` lines.
4. Post the dispatch below. Nothing else is typed into the room by a human: once a stage is
   dispatched, the seats run it and the next input is a verdict.

## Dispatch — stage 2

```text
@factory-architect-df Stage 1 is locked at revision 35e2fa1. Build stage 2 now.

Work in /Users/admin/harness/lablab-harness/build/pocketful-factory/stage-2, to the
specification at /Users/admin/dark-factory-wearedevs/pocketful/spec/stage-2.md. That folder is
stage 1 carried forward with three fixes already applied and committed at 4004384; keep them,
they are what the stage-2 checks were failing on. Stage 2 must still pass every stage-1 check.

@factory-coder-df implements to the specification, runs the stage-1 and stage-2 shipped checks,
commits, and hands each revision to @factory-tester-df with the revision SHA, the exact
commands and the results. @factory-tester-df checks out that exact revision, reads
holdouts/stage-2.md (reviewer only, never paste it into the room), runs independent plus
adversarial verification, and replies ACCEPT to @factory-architect-df or REJECT to
@factory-coder-df with the revision and logs. No human clarification mid-run. The coordinator
locks the stage only after the reviewer accepts.

Run locally: cd stage-2 && PORT=8080 python3 -m src.app, then curl
http://127.0.0.1:8080/health. The checks themselves are part of the specification's
conformance run and are also runnable from the harness package at
/Users/admin/dark-factory-wearedevs.
```

## Dispatch — stage 3 and stage 4

Same shape, after the previous stage is locked. Stage 3 and stage 4 are copy-forward: start
from the locked folder of the stage before it, and keep every earlier check passing.

## Before it can be submitted

```bash
# `check` scans gitignored files too, so move the secrets out for the length of the run
mv band-agents/.env band-agents/agent_config.yaml /tmp/
python3 -m harness check . --track pocketful      # from the harness package directory
mv /tmp/.env /tmp/agent_config.yaml band-agents/
```

Then download the room again, from the Band console: the room's menu, Open in Band, then
Download full session. Save it at the repository root as `room.json`, overwriting the older
copy. Read it before committing it: `check` looks for credential shapes, but the download
redacts nothing and it cannot know every private value.