# RUN.md — stage-3 (copy-forward of stage-2 + statements/corrections + browser UI)

Build + start duy nhất judge follow y hệt (clean container, không manual):

```bash
docker build -t pocketful-stage3 ./stage-3
docker run --rm -p 8080:8080 -e PORT=8080 pocketful-stage3
```

Verify:

```bash
curl -s http://127.0.0.1:8080/health
# -> {"status":"ok"}
```

Local không Docker:

```bash
cd stage-3 && pip install -r requirements.txt && PORT=8080 python3 -m src.app
```

Service bind `0.0.0.0`, đọc `PORT` default `8080`. Deps cài lúc build, runtime không internet.
UI routes `/ /requests /split /signup /login /authorizations` serve HTML khi
`Accept: text/html`, JSON trong các trường hợp còn lại. Mọi stage-1/2 suites vẫn pass.
Thêm `GET /statement` (JSON, snapshot token cho paging ổn định),
`GET /me?as_of=...&known_at=...`, `POST /payments/{id}/corrections` (idempotent
write), `GET /payments/{id}/revisions`.
