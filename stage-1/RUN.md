# RUN.md — stage-1

Build + start duy nhất judge follow y hệt (clean container, không manual):

```bash
docker build -t pocketful-stage1 ./stage-1
docker run --rm -p 8080:8080 -e PORT=8080 pocketful-stage1
```

Verify:

```bash
curl -s http://127.0.0.1:8080/health
# -> {"status":"ok"}
```

Local không Docker:

```bash
cd stage-1 && pip install -r requirements.txt && PORT=8080 python3 -m src.app
```

Service bind `0.0.0.0`, đọc `PORT` default `8080`. Deps cài lúc build, runtime không internet.
Stage-2+ copy-forward thư mục này rồi mở rộng, giữ pass suites cũ.
