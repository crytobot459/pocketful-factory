# RUN.md — stage-4 (stage-3 carried forward, plus refunds and batch corrections)

Build and start, exactly as a judge would: from a clean container, nothing manual.

```bash
docker build -t pocketful-stage4 ./stage-4
docker run --rm -p 8080:8080 -e PORT=8080 pocketful-stage4
```

Verify:

```bash
curl -s http://127.0.0.1:8080/health
# -> {"status":"ok"}
```

Without Docker:

```bash
cd stage-4 && pip install -r requirements.txt && PORT=8080 python3 -m src.app
```

Then open <http://127.0.0.1:8080/> and sign in as `ada@example.com` with the password
`correct horse`.

The service binds `0.0.0.0` and reads `PORT`, default `8080`. Dependencies are installed at
build time; nothing reaches the network at run time.

The browser routes serve HTML when the request carries `Accept: text/html`, and JSON otherwise.

Added in this stage: `POST /payments/{id}/refunds`, an idempotent write the receiver alone may
make; `POST /correction-batches`, an operator's idempotent write that is aware of settlements and
applies all of its members or none; and `GET /payments/{id}/refunds`.

Every stage-1, stage-2 and stage-3 check still passes against this folder.