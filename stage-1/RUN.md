# RUN.md — stage-1

Build and start, exactly as a judge would: from a clean container, nothing manual.

```bash
docker build -t pocketful-stage1 ./stage-1
docker run --rm -p 8080:8080 -e PORT=8080 pocketful-stage1
```

Verify:

```bash
curl -s http://127.0.0.1:8080/health
# -> {"status":"ok"}
```

Without Docker:

```bash
cd stage-1 && pip install -r requirements.txt && PORT=8080 python3 -m src.app
```

Then open <http://127.0.0.1:8080/> and sign in as `ada@example.com` with the password
`correct horse`. Those accounts are the ones the specification's fixtures seed.

The service binds `0.0.0.0` and reads `PORT`, default `8080`. Dependencies are installed at
build time; nothing reaches the network at run time.

Stage 2 is this folder carried forward and widened, and it must keep passing every stage-1
check.