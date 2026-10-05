---
title: Pocketful Factory
emoji: 💸
colorFrom: indigo
colorTo: green
sdk: docker
app_port: 7860
pinned: false
---

# Pocketful Factory — stage-4 demo

This Space runs **stage-4**, the final build the coding-agent factory produced for the
`pocketful` track, and puts a Streamlit page in front of it. The page starts the service
(`python3 -m src.app`) and drives it over HTTP; it does not reimplement the wallet, so what
you click is the code in `src/app.py`, byte for byte the code in `stage-4/` of
[crytobot459/pocketful-factory](https://github.com/crytobot459/pocketful-factory).

## Use it

1. **Seed the accounts** — a fresh container holds no users. This is the
   `POST /_test/reset` call that `stage-4/RUN.md` tells a judge to make; nothing is seeded
   at start-up, because the specification says state is seeded through that endpoint.
2. **Sign in as Ada** — `ada@example.com`, password `correct horse`.
3. The tabs below walk the three claims the video makes: a payment larger than the balance
   is refused and the balance does not move; the same payment fired twice moves the money
   once; and stage 4's refunds are idempotent.

Every number on the page is read back from the server. The "unchanged" and "one entry"
messages appear only after two reads of `/me`, or a count of `/activity`, agree.

## If you would rather use HTTP

The service is on `$PORT` (7860). `GET /health` returns `{"status":"ok"}`.

## What this is not

It is not a hosted demo of the *whole* entry: the repository is the submission, and it also
carries `stage-1/` through `stage-3/`, the BAND room export (`room.json`), the three seat
mandates and `FACTORY.md`.
