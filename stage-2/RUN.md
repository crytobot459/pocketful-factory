# RUN.md — stage-2 (copy-forward of stage-1 + holds/authorizations + browser UI)

Build + start duy nhất judge follow y hệt (clean container, không manual):

```bash
docker build -t pocketful-stage2 ./stage-2
docker run --rm -p 8080:8080 -e PORT=8080 pocketful-stage2
```

Verify:

```bash
curl -s http://127.0.0.1:8080/health
# -> {"status":"ok"}
```

Local không Docker:

```bash
cd stage-2 && pip install -r requirements.txt && PORT=8080 python3 -m src.app
```

Service bind `0.0.0.0`, đọc `PORT` default `8080`. Deps cài lúc build, runtime không internet.
UI routes `/ /requests /split /signup /login /authorizations` serve HTML khi
`Accept: text/html`, JSON trong các trường hợp còn lại (chia sẻ path `/requests`,
`/authorizations` với API). Mọi stage-1 suites vẫn pass (balance=total khi không
có hold; insufficient_funds xét trên available).
