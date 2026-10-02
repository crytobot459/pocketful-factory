# pocketful-factory — Dark Factory (Pocketful track, BAND)

![factory](https://img.shields.io/badge/factory-BAND-blue) ![ci](https://img.shields.io/badge/ci-pytest-blue) ![license](https://img.shields.io/badge/license-MIT-green)

> Factory 3 seats OpenCode xây wallet/payments đúng invariant dưới retry + concurrency + failure. 1 room xuyên suốt, copy-forward stage-1 -> stage-4, evidence = room log + git history + isolated harness.

* Track: `pocketful` (Venmo-like). Spec chính thức: `/Users/admin/dark-factory-wearedevs/pocketful/spec/stage-*.md`
* Factory: `FACTORY.md` + `mandates/` (generic, không chứa endpoint/field/error)
* Submission structure chuẩn official: `README, FACTORY, mandates/, room.json, stage-N/Dockerfile+RUN.md`
* Harness kiểm tra: `python -m harness check` (gates 1,2,4 offline) + `run --mode isolated` (gate 3)

## Chạy stage-1 local (không cần BAND key)

```bash
cd stage-1 && pip install -r requirements.txt && PORT=8080 python3 -m src.app
# test khác terminal:
curl -s http://127.0.0.1:8080/health
# check official (từ /Users/admin/dark-factory-wearedevs, tạm dời band-agents/.env ra /tmp vì check quét cả file gitignored):
# python3 -m harness check /Users/admin/harness/lablab-harness/build/pocketful-factory --track pocketful
```

## Chạy factory BAND (cần key, không commit key)

```bash
cd band-agents
cp .env.example .env  # điền GEMINI_API_KEY, OPENAI_API_KEY, BAND keys vào .env local
cp agent_config.example.yaml agent_config.yaml  # điền 3 seat UUID/key từ app.band.ai
opencode serve --hostname=127.0.0.1 --port=4096
# 3 terminal riêng:
uv run python coordinator.py
uv run python implementer.py
uv run python reviewer.py
# Trên app.band.ai: tạo room mới `pocketful-factory`, add 3 remotes, paste dispatch ở ROOM_DISPATCH.md § Dispatch Stage-1 nguyên văn
```

## Cần key gì

* BAND seat UUID/key x3 MỚI TINH (https://app.band.ai/agents → tạo 3 agents mới, không tái dùng room cũ) — bắt buộc cho factory thật
* `GEMINI_API_KEY` (free, https://aistudio.google.com/apikey) cho reviewer
* `OPENAI_API_KEY` (free-tier bạn cấp) làm fallback reviewer
* Coordinator/Implementer dùng `opencode/muse-spark-1.3-contributor-free` (room mới; fallback coordinator `space-bunny-free`, implementer `nemotron-3-ultra-free` khi 429)
* Không commit key. Xem `.gitignore` + `band-agents/.env.example`.

## Cấu trúc

* `FACTORY.md` — thiết kế factory, routing, veto, cost/time, recover (judge đọc cho Factory 50%)
* `mandates/` — 3 files generic theo seat slug
* `stage-1/` — Dockerfile + RUN.md + src (factory build, copy-forward lên stage-2...)
* `band-agents/` — 3 agents OpenCode nối BAND rooms thật
* `room.json` — Download full session từ Band console (scope=full), đổi tên đúng `room.json`, KHÔNG commit key
