# band-agents — chạy 3 seats OpenCode nối BAND room duy nhất

1. `cp .env.example .env` — điền `GEMINI_API_KEY/OPENAI_API_KEY` local (free-tier bạn cấp), không commit.
2. `cp agent_config.example.yaml agent_config.yaml` — điền 3 UUID/key từ `app.band.ai/agents`, không commit.
3. `opencode serve --hostname=127.0.0.1 --port=4096` (terminal riêng, giữ chạy).
4. `uv venv && uv add "band-sdk[opencode]" python-dotenv pyyaml` (lần đầu).
5. 3 terminal riêng:
```bash
uv run python coordinator.py
uv run python implementer.py
uv run python reviewer.py
```
6. Trên `app.band.ai`: tạo room mới `pocketful-factory`, add 3 remotes, paste dispatch ở `../ROOM_DISPATCH.md Stage-1` nguyên văn. Không dùng room cũ `b1e586c7/4ec606f4` để tránh cross-talk.
7. Sau run: Band console ⋮ > Open in Band > Download full session (scope=full) -> lưu thành `../room.json` (không commit nếu chứa secret, scrub trước khi public).
8. Check nộp (từ `/Users/admin/dark-factory-wearedevs`): tạm dời `band-agents/.env` ra `/tmp` rồi `python3 -m harness check <repo> --track pocketful` (check quét cả file gitignored). Xong restore `.env 600`. Kỳ vọng chỉ còn `room.json is missing` cho tới khi có run thật.

Model mapping (room mới 3 seats mới):
* coordinator: `muse-spark-1.3-contributor-free` (fallback `space-bunny-free` khi 429)
* implementer: `muse-spark-1.3-contributor-free` (fallback `nemotron-3-ultra-free` khi 429)
* reviewer: `GEMINI_MODEL_ID=gemini-3.8-flash` qua `GOOGLE_GENERATIVE_AI_API_KEY/GEMINI_API_KEY` (2.0/2.5 deprecated), fallback `OPENAI_MODEL_ID=gpt-4o-mini`

Submitted run dùng `approval_mode=auto_accept` để không treo chờ human. Dev có thể đổi `manual` local.
`emit` giữ `TOOL_CALLS+TASK_EVENTS+USAGE` — TASK_EVENTS load-bearing resume, USAGE đo cost.
