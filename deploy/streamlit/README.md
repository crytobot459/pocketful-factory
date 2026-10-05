# Pocketful Factory — stage-4 demo

This is the Streamlit Community Cloud deployment of **stage-4**, the final build the
coding-agent factory produced for the `pocketful` track. The page starts the service
(`python3 -m src.app`) and drives it over HTTP; it does not reimplement the wallet, so what
you click is the code in `src/app.py`, byte for byte the code in `stage-4/` of
[crytobot459/pocketful-factory](https://github.com/crytobot459/pocketful-factory).

## Use it

1. **Seed the accounts** — a fresh container holds no users. This is the
   `POST /_test/reset` call that `stage-4/RUN.md` tells a judge to make; nothing is seeded
   at start-up, because the specification says state is seeded through that endpoint.
2. **Sign in as Ada** — `ada@example.com`, password `correct horse`.
3. Work down the page. It walks the three claims the video makes: a payment larger than the
   balance is refused and the balance does not move; the same payment fired twice moves the
   money once; and stage 4's refunds are idempotent and only the receiver may issue one.

Every number on the page is read back from the server. The "unchanged" and "one entry"
messages appear only after two reads of `/me`, or a count of `/activity`, agree.

## One service, every visitor

The page is not a private sandbox. `st.cache_resource` starts **one** service per process,
so a deployed URL is a single wallet that everyone shares: one set of balances, one
idempotency store. Two things follow, and the page handles both rather than pretending
otherwise.

* Seeding resets it for whoever comes next. If you arrive at a balance that is not
  `EUR 100.00`, press **Seed the fixture** — and read that as "someone got here first", not
  as a broken demo.
* Every idempotency key carries the browser session's id, shown on the page. Without it two
  visitors inside the same minute would share one key, and the second would be handed the
  first one's replay: `200` instead of `201`, and no money moved, on a service that was
  behaving perfectly.

## If you would rather use HTTP

`streamlit_app.py` picks a free loopback port (8080 upwards) and prints it under **What is
running here**. `GET /health` on it returns `{"status":"ok"}`; `src/app.py` reads `PORT` if
you set it.

The free tier sleeps, so the first request after a pause takes 30–60 seconds to wake. That
is the platform, not this app.

## What this is not

It is not a hosted demo of the *whole* entry: the repository is the submission, and it also
carries `stage-1/` through `stage-3/`, the BAND room export (`room.json`), the three seat
mandates and `FACTORY.md`.
