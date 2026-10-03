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

## Seed the accounts, then sign in

A fresh service holds no users: the specification seeds state through
`POST /_test/reset`, and nothing is seeded at container start. Seed the published
fixture, then sign in as `ada@example.com` with the password `correct horse`:

```bash
curl -s -X POST http://127.0.0.1:8080/_test/reset -H 'Content-Type: application/json' -d '{
  "currency": "EUR",
  "minor_units": 2,
  "users": [
    { "id": "u_ada", "email": "ada@example.com", "password": "correct horse",
      "display_name": "Ada", "handle": "ada", "balance": 10000 },
    { "id": "u_bob", "email": "bob@example.com", "password": "correct horse",
      "display_name": "Bob", "handle": "bob", "balance": 2500 }
  ],
  "payments": [
    { "id": "p_1", "from_user_id": "u_ada", "to_user_id": "u_bob",
      "amount": 500, "note": "coffee", "visibility": "public" }
  ],
  "requests": [
    { "id": "rq_1", "requester_id": "u_bob", "payer_id": "u_ada",
      "amount": 1200, "note": "taxi", "status": "pending" }
  ]
}'
# -> 204, and no body
```

After that, <http://127.0.0.1:8080/> shows Ada with a balance of 100.00 EUR, one paid
"coffee" in the feed and one pending "taxi" request. `POST /auth/signup` also works if
you would rather make your own account.

The service binds `0.0.0.0` and reads `PORT`, default `8080`. Dependencies are installed at
build time; nothing reaches the network at run time.

The browser routes `/`, `/requests`, `/split`, `/signup`, `/login` and `/authorizations`
serve HTML when the request carries `Accept: text/html`, and JSON otherwise. `/requests` and
`/authorizations` are shared between the page and the API.

Every stage-1 check still passes against this folder: balance equals total when nothing is
held, and `insufficient_funds` is judged against available funds rather than the total.