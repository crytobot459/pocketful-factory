# RUN.md — stage-4 (copy-forward of stage-3 + refunds/batch corrections)

Build + start duy nhất judge follow y hệt (clean container, không manual):

```bash
docker build -t pocketful-stage4 ./stage-4
docker run --rm -p 8080:8080 -e PORT=8080 pocketful-stage4
```

Verify:

```bash
curl -s http://127.0.0.1:8080/health
# -> {"status":"ok"}
```

Local không Docker:

```bash
cd stage-4 && pip install -r requirements.txt && PORT=8080 python3 -m src.app
```

Service bind `0.0.0.0`, đọc `PORT` default `8080`. Deps cài lúc build, runtime không internet.
UI routes `/ /requests /split /signup /login /authorizations` serve HTML khi
`Accept: text/html`, JSON trong các trường hợp còn lại. Mọi stage-1/2/3 suites vẫn pass.
Thêm `POST /payments/{id}/refunds` (idempotent write, receiver only),
`POST /correction-batches` (operator, idempotent, settlement-aware),
`GET /payments/{id}/refunds` (list refunds of a payment).