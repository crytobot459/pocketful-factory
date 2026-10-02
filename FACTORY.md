# FACTORY.md — pocketful-factory

## 1. Seats (3 seats thật, 4 vai logic)

| Seat (slug) | Harness | Model | Vai |
|---|---|---|---|
| `coordinator` | OpenCode | `opencode/muse-spark-1.3-contributor-free` (fresh room canonical; fallback `space-bunny-free` khi 429, accepted) | Decompose + route, không code |
| `implementer` | OpenCode | `opencode/muse-spark-1.3-contributor-free` (fresh room; fallback `nemotron-3-ultra-free` khi 429, accepted) | Code + test + commit |
| `reviewer` | OpenCode | Gemini free `google/gemini-3.8-flash` (2.0/2.5 deprecated với key mới, đã verify 2026-10-01), fallback GPT-free `openai/gpt-4o-mini`, fallback cuối OpenCode `nemotron-3-ultra-free` (accepted 2026-10-02 để run không block) | Independent + adversarial verify, không fix code |

Tên file mandate khớp slug: `mandates/coordinator.md` etc. Dòng đầu mỗi mandate bắt buộc `Harness: ...` + `Model: ...`. Fresh room chỉ dùng 3 slug canonical này. 3 file `mandates/factory-*-df.md` là LEGACY của room cũ archive, không route tới nữa.

Tại sao chia vậy: coordinator + implementer cùng Muse Spark 1.3 Free (mạnh, free quota chung, routing + code atomic/idempotency khó), reviewer khác họ model Gemini (tránh cùng blind-spot, veto độc lập). Fallback khi 429 (accepted): coordinator→bunny, implementer→nemotron, reviewer→gpt-mini→nemotron (ghi rõ model thực chạy trong verdict).

## 2. Design choices + trade-off

* **Fresh room v2, bỏ room cũ.** Room cũ 482 msg (coordinator-coder ping-pong 99%, reviewer 1%, ~455 msg <200 chars lặp Holding/Ack) đã archive, không nộp. Room mới `pocketful-factory-v2` + 3 seats canonical mới tinh cho history sạch.
* **Silence rule là load-bearing cho Teamwork 25%.** Sau khi báo revision / giao task thì im lặng tới verdict / revision mới. Cấm Holding/Ack/Noted/Waiting. 1 revision = 1 report có số. Reply vào ping rỗng trừ điểm teamwork. Đã nhúng vào cả 3 mandates + dispatch.
* **1 room xuyên suốt, không room-per-stage.** Stage sau = copy-forward stage trước + mở rộng, vẫn pass suites cũ (chain rule). 1 `room.json` full-session cho history đẹp.
* **`@mention` là router.** `@implementer` mới nhận việc, `@reviewer` mới review. Không broadcast. Coordinator handoff self-contained: paste full task + spec path + repo path + checks.
* **Sequential handoff:** coordinator -> implementer -> reviewer -> (ACCEPT -> coordinator lock / REJECT -> implementer). Không song song 2 người cùng sửa 1 file.
* **Reviewer = veto authority, không phải fixer.** Checkout đúng revision SHA, tự chạy shipped + sinh adversarial riêng (concurrent same-key, lost-response retry, kill mid-transaction, sum==seeded). REJECT kèm revision + logs + invariant vi phạm.
* **Human ngoài run.** Submitted run `auto_accept`, không treo chờ human. Human chỉ accept ngoài boundary (nhận/shíp). Dev mới dùng `manual`.

## 3. Room flow (paste vào BAND room)

```text
@coordinator Build stage-1 from pocketful/spec/stage-1.md in ./stage-1.
Repo: <absolute path>/pocketful-factory/stage-1. Checks: harness shipped stage-1.
Rules: implementer reads SPEC/repo/RUN only, runs checks, commits, hands to @reviewer with revision+commands+results. Reviewer checks out revision, runs independent + adversarial, ACCEPT or REJECT to @implementer. No human clarification mid-run.
```

Handoff mẫu implementer -> reviewer:
```text
@reviewer @coordinator Revision abc123 stage-1 ready. Commands: PORT=8080 python3 -m src.app; pytest. Results: ... Files: stage-1/src/...
```

Reviewer REJECT mẫu:
```text
@implementer REJECT abc123 reason: concurrent idempotency unsafe (20x same key -> 20 payments, expect 1x201+19x200). Logs: ... Repro: ...
```

## 4. Bắt + recover bad work

| Lỗi | Ai bắt | Recover |
|---|---|---|
| Shipped xanh nhưng concurrent sai | reviewer adversarial | REJECT -> implementer fix lock/idempotency -> revision mới |
| Implementer kẹt >2 REJECT | coordinator | chia nhỏ task, yêu cầu minimal repro + invariant list |
| Reviewer nghi spec ambiguous | reviewer hỏi coordinator trong room (agent-agent), không hỏi human mid-run; ghi vào FACTORY appendix |
| Mất kết nối / restart | BAND `TASK_EVENTS` resume OpenCode session per room; `session_id` trong task-event metadata |
| 429 free-tier | switch model fallback (bunny<->spark<->nemotron<->gemini<->gpt), giữ nguyên mandate logic |

## 5. Cost / time (fresh room run 2026-10-02 — stage-1 hoàn thiện)

* Room: `affa9999-88af-4bef-b731-55957ba9af33` (`pocketful-factory-v2`), 49 entries (22 agent texts + 27 tool/task/usage events), 3 seats, 0 ack-spam sau khi tắt adapter fallback.
* Wall: dispatch 02:54 UTC -> Stage-1 LOCK 04:28 UTC ≈ 94 min (gồm ~40 min overhead hạ tầng: restart seats, backlog drain room cũ, 1 turn reviewer chạm 900s timeout phải chia Batch A/B).
* Verdicts stage-1: 3 ACCEPT có số — `e0597cb` full (shipped 30+ + independent 9 H1-H9 + adversarial 3), `ed2a419` Batch A 11/11 shipped, `35e2fa1` Batch B 12/12 holdouts H1-H10. 0 REJECT text; 1 fix revision trong loop (`35e2fa1` H9 import hardening: validate-all + deepcopy + atomic swap).
* Room-text tokens (dòng `Token usage` trong room): coordinator 56.4k in / 9.4k out. Token đầy đủ nằm ở BAND USAGE events + opencode usage (xem room.json events).
* Models thực chạy: coordinator Spark 1.3, implementer Spark 1.3, reviewer nemotron-3-ultra-free (fallback accepted, `REVIEWER_USE_FALLBACK=1`).
* `Stage-1 fresh: ~94min wall, verdicts 3 ACCEPT / 0 REJECT, 1 fix revision. Models thực chạy: coord spark, impl spark, rev nemotron. Spend: $0 (free-tier).`
* Chạy lại được: `python -m harness run --track pocketful --repo . --stage 1 --mode isolated` (cần docker; máy dev không có docker nên verify local `PORT=18082 python3 -m src.app` + `/health -> {status:ok}` PASS 2026-10-02).

## 6. Reuse cho team khác

1. Copy `FACTORY.md + mandates/` sang problem mới.
2. Thay spec path + repo path trong dispatch, giữ nguyên routing/veto policy.
3. Chỉnh `band-agents/*.py: REPO + provider/model env`, không sửa mandate logic.
4. Verify: `harness check` xanh gates 1,2,4 + `run --mode isolated`.

## Appendix: invariants Pocketful Stage-1 (reviewer checklist)

* 5 write paths idempotent scope per-user, replay identical `200`, khác body `409`, concurrent cùng key 1 tác dụng.
* `sum(balance)==seeded total` luôn, không âm transient, split nguyên minor-unit chênh lệch tối đa 1 về người đầu.
* Export/import atomic, sai track/version `422` không đổi state, retry key cũ vẫn valid sau import.
* Container `PORT/0.0.0.0//health->{status:ok}` <60s, unknown field bỏ qua, no outbound runtime.

## 7. Fresh-room decision log (2026-10-02)

* Bỏ room cũ: 482 msg, reviewer 5 msg (1 ACCEPT + 4 ack/wait), 0 REJECT thật, ack-loop Holding/Ack ~226 msg <60 chars. Không chứng minh được veto + teamwork.
* Tạo room mới `pocketful-factory-v2`: 3 seats canonical mới, dispatch đã nhúng silence rule, mandates đã có fallback accepted.
* Fallback OpenCode cho reviewer được chấp nhận: primary Gemini, `REVIEWER_USE_FALLBACK=1` -> nemotron (khác implementer Spark). Ghi model thực chạy trong verdict.
* Ưu tiên hoàn thiện stage-1 trước: ép 1 REJECT-loop có chủ ý + điền metrics + quay E2E loop cho video. Stage-2 copy-forward sau khi stage-1 ACCEPT.
* Reviewer-only holdouts ở `holdouts/stage-1.md` (implementer cấm đọc). Reviewer grade theo đó + adversarial riêng.
