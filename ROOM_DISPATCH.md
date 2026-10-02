# ROOM_DISPATCH — fresh room (đã chạy 2026-10-02, stage-1 LOCKED)

> THỰC TẾ 2026-10-02 (agent làm hết trên máy): seats là 3 seats cũ (`factory-architect/coder/tester-df`, không tạo seats mới vì cần browser tay) nhưng room HOÀN TOÀN MỚI `affa9999-88af-4bef-b731-55957ba9af33` (`pocketful-factory-v2`), tạo + add seats + post dispatch 100% bằng API (`band-agents/new_room.py`). Room cũ 482-msg đã archive, không nộp. Fallback OpenCode reviewer accepted (`REVIEWER_USE_FALLBACK=1` -> nemotron). Stage-1 LOCKED tại `35e2fa1` (Batch A 11/11 + Batch B 12/12).

> QUYẾT ĐỊNH 2026-10-02 (user chốt): bỏ room cũ 482-msg (ack-livelock 99% ping-pong, reviewer 1%), tạo room + 3 seats MỚI TINH với slug canonical `coordinator/implementer/reviewer`. Fallback OpenCode cho reviewer được chấp nhận để run không block khi 429. Ưu tiên hoàn thiện stage-1 trước (REJECT-loop + metrics + video loop), stage-2 sau.

## Tạo room (bấm tay trên app.band.ai)

1. Trên https://app.band.ai/agents: tạo 3 agents MỚI TINH (không tái dùng seat room cũ): `coordinator`, `implementer`, `reviewer`. Slug phải khớp đúng tên file `mandates/<slug>.md` (Gate 2 check routing theo slug).
2. `cp band-agents/.env.example band-agents/.env` (điền GEMINI/OPENAI keys; để `REVIEWER_USE_FALLBACK=1` nếu Gemini hết quota — fallback OpenCode đã được chấp nhận) + `cp band-agents/agent_config.example.yaml band-agents/agent_config.yaml` (điền 3 UUID/key mới). Model: coordinator + implementer = `muse-spark-1.3-contributor-free`, reviewer = `gemini-3.8-flash` (fallback `nemotron-3-ultra-free`).
3. Tạo chat room mới tên `pocketful-factory-v2`, add 3 remotes mới.
4. `opencode serve --hostname=127.0.0.1 --port=4096`, rồi 3 terminal: `uv run python coordinator.py / implementer.py / reviewer.py`. Đợi 3 `connected`.
5. Paste dispatch dưới đây NGUYÊN VĂN (đã nhúng silence rule chống ack-spam).
6. Room cũ đã archive thành `room.archive-*.json` (gitignored, không nộp). `room.json` nộp là Download full session của room MỚI này (scope=full).

> KHÔNG gửi tin vào room cũ để tránh cross-talk.

## Dispatch — Stage-1 (paste nguyên văn, đã nhúng silence rule)

```text
@coordinator Build stage-1 of the Pocketful wallet service from the official spec at /Users/admin/dark-factory-wearedevs/pocketful/spec/stage-1.md, working in ./stage-1 of this repo (/Users/admin/harness/lablab-harness/build/pocketful-factory/stage-1).

@implementer implements to the SPEC, runs the shipped checks locally, commits, and hands each revision to @reviewer with revision SHA + exact commands + results. @reviewer checks out the exact revision, runs independent plus adversarial verification (concurrent same-key writes, lost-response retry, invariant sum checks, export/import atomicity), and replies ACCEPT to @coordinator or REJECT to @implementer with revision + logs. No human clarification mid-run. Coordinator locks the stage only after reviewer ACCEPT.

SILENCE RULE (all seats): after reporting a revision or assigning a task, stay silent until a verdict or new revision arrives. Never send Holding/Ack/Noted/Waiting. One revision = one report with numbers. Replying to empty pings voids teamwork score.

Verify locally: cd stage-1 && PORT=8080 python3 -m src.app + curl http://127.0.0.1:8080/health. Official: python -m harness check /Users/admin/harness/lablab-harness/build/pocketful-factory --track pocketful.
```

## Sau ACCEPT stage-1

Paste tiếp cho stage-2 (copy-forward, giữ pass suites cũ):

```text
@coordinator Stage-1 ACCEPTED at revision <SHA>. Now build stage-2 by copy-forwarding ./stage-1 to ./stage-2 and extending per /Users/admin/dark-factory-wearedevs/pocketful/spec/stage-2.md. Stage-2 must still pass all stage-1 suites. Same handoff rules: @implementer -> @reviewer -> ACCEPT/REJECT.
```

## Lấy evidence

Band console ⋮ > Open in Band > Download full session (scope=full) -> lưu đè `room.json` ở repo root. Scrub secret trước khi public (Gate 4 quét credentials cả `room.json`).
