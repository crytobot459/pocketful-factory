# RUN.md — stage-3 (stage-2 carried forward, plus statements and corrections)

Build and start, exactly as a judge would: from a clean container, nothing manual.

```bash
docker build -t pocketful-stage3 ./stage-3
docker run --rm -p 8080:8080 -e PORT=8080 pocketful-stage3
```

Verify:

```bash
curl -s http://127.0.0.1:8080/health
# -> {"status":"ok"}
```

Without Docker:

```bash
cd stage-3 && pip install -r requirements.txt && PORT=8080 python3 -m src.app
```

Then open <http://127.0.0.1:8080/> and sign in as `ada@example.com` with the password
`correct horse`.

The service binds `0.0.0.0` and reads `PORT`, default `8080`. Dependencies are installed at
build time; nothing reaches the network at run time.

The browser routes serve HTML when the request carries `Accept: text/html`, and JSON otherwise.

Added in this stage: `GET /statement`, which returns a snapshot token so that paging stays
stable while writes land; `GET /me?as_of=...&known_at=...` for a balance as it stood at an
instant; `POST /payments/{id}/corrections`, an idempotent write; and
`GET /payments/{id}/revisions`.

Every stage-1 and stage-2 check still passes against this folder.