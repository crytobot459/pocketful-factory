# RUN.md — stage-2 (stage-1 carried forward, plus holds and the browser UI)

Build and start, exactly as a judge would: from a clean container, nothing manual.

```bash
docker build -t pocketful-stage2 ./stage-2
docker run --rm -p 8080:8080 -e PORT=8080 pocketful-stage2
```

Verify:

```bash
curl -s http://127.0.0.1:8080/health
# -> {"status":"ok"}
```

Without Docker:

```bash
cd stage-2 && pip install -r requirements.txt && PORT=8080 python3 -m src.app
```

Then open <http://127.0.0.1:8080/> and sign in as `ada@example.com` with the password
`correct horse`.

The service binds `0.0.0.0` and reads `PORT`, default `8080`. Dependencies are installed at
build time; nothing reaches the network at run time.

The browser routes `/`, `/requests`, `/split`, `/signup`, `/login` and `/authorizations`
serve HTML when the request carries `Accept: text/html`, and JSON otherwise. `/requests` and
`/authorizations` are shared between the page and the API.

Every stage-1 check still passes against this folder: balance equals total when nothing is
held, and `insufficient_funds` is judged against available funds rather than the total.