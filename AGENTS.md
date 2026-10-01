# AGENTS.md — pocketful-factory operating contract

## Build / Run
* Stage service: `cd stage-1 && pip install -r requirements.txt && PORT=8080 python3 -m src.app`
* Health: `curl -s http://127.0.0.1:8080/health` -> `{"status":"ok"}`
* BAND agents: `cd band-agents && uv run python coordinator.py` (x3 files riêng), cần `opencode serve --hostname=127.0.0.1 --port=4096` chạy trước
* Official harness (ngoài repo này): `python -m harness check <repo> --track pocketful` + `run --track pocketful --repo <repo> --stage 1 --mode isolated`

## Conventions (bắt buộc để không bị loại)
* Mandates generic: chỉ nói factory làm việc thế nào (owns/handoff/reject/report). CẤM endpoint path, field name, error code, test-id. Check bằng official `vocabulary.py`.
* Implementer chỉ đọc SPEC/repo/RUN + shipped checks để wire-up. CẤM search hidden tests, inspect judge harness, grep expected answers.
* Reviewer checkout đúng revision SHA, tự chạy + sinh adversarial riêng, ACCEPT/REJECT, KHÔNG tự fix code.
* Coordinator không code. Mọi handoff self-contained + `@handle` 2 chiều trong room text (tool-call echo không tính cho Gate 2).
* Không commit: `.env, agent_config.yaml, room.json chứa secret, key`. Secrets chỉ env local.
* Stage sau copy-forward stage trước, giữ pass suites cũ. Không symlink/submodule, không `.git` lồng.
* 1 room xuyên suốt các stages. Room phụ debug (nếu có) không phải room nộp.

## Architecture
* `mandates/` -> BAND room routing -> `stage-N/` service -> official harness isolated
* `band-agents/*.py` là薄 adapter: `OpencodeAdapter(directory=REPO, custom_section=mandate, provider/model từ env)` + `emit={TOOL_CALLS,TASK_EVENTS,USAGE}`
* Evidence = BAND event log (tool_call/tool_result/task/usage) + git history (commits per revision + fix-after-reject) + harness report
