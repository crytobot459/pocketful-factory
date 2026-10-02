# BRIEF — WeAreDevelopers x BAND present: Dark Factory (hackathon edition)
- Link: https://lablab.ai/ai-hackathons/wearedevelopers-hackathon
- Giải: $6000
- EV: $77.14/ngày | Score A+93
- Lịch: 2026-09-26 → 2026-10-05 (HẠN NỘP: 13:59 VN 06/10 (06:59 UTC) — Online Build 26/9-5/10, kickoff 23:00 VN 26/9)
- Format: online only | Stack: band | Status: enrolled/Register
- Repo thật: (chưa gắn — Bob bắt buộc repo thật + BOB_REPORT)
- Demo URL: (chưa có — Technology mất điểm nếu local-only)

## 🎯 Track nhắm (snipe ít đối thủ): tablekeeper track (đối thủ stratifyX làm OpenTable clone — đông) hoặc pocketful track (aichaliveret nhắm pocketful + Bob — ít info hơn, có thể ít đối thủ). Factory spec→CRUD của ta hợp cả 2 — chốt sau kickoff 26/9

## Tracks / chủ đề
- Main [suy từ slug]: Dark Factory with BAND — factory planner→coder→evaluator (mở trang event đọc Tracks)
- [ ] Mở https://lablab.ai/ai-hackathons/wearedevelopers-hackathon đọc mục Tracks/Prizes chính xác (HTML tĩnh không có, phải đọc tay 5 phút)

## Tiêu chí chấm
- Mặc định lablab 4 chiều (trang tĩnh không có criteria chi tiết — đọc mục Judging/Evaluation tay):
- Presentation / Business Value / Technology / Originality (xem khung 4 chiều bên dưới)
- Rubric nguyên văn (event override): "BAND factory load-bearing + evaluator pass-rate/override-rate/token-task + holdout separation + video quay LOOP + generic 4 chiều Presentation/Business/Technology/Originality"

## Checklist đọc tay 5 phút (HTML tĩnh không có tracks đầy đủ)
- [ ] Mở https://lablab.ai/ai-hackathons/wearedevelopers-hackathon mục Tracks/Prizes -> điền `track_target` vào config/events.yaml
- [ ] Copy rubric Judging/Evaluation -> điền `judging_rubric_quote` vào config
- [ ] Xác nhận deadline giờ chuẩn (DB chỉ lưu ngày) -> `deadline_vn`

## 3 hướng ý tưởng (chọn 1 — rồi load skill chốt)
1. Factory đo được: planner→coder→evaluator trong BAND Desktop, báo evaluator pass-rate + override-rate + token/task. Video quay cái LOOP, không quay UI app.
2. Spec-to-CRUD: 1 spec văn bản ra 1 app CRUD qua factory, holdout scenarios coder không được đọc — đúng train/test separation.
3. AGENTS.md showcase: repo mẫu mà agent nào vào cũng build được ngay, đo số bước tay còn lại (càng gần 0 càng thắng).

## Tiêu chí chấm (judge nhìn 4 chiều này)
1. Presentation — video 4-5 phút rõ ràng (problem 30s, live demo, business case).
2. Business Value — user cụ thể + TAM + 1 revenue model + vì sao cần AI.
3. Technology — demo URL public mở được, repo commit rải đều, AI load-bearing.
4. Originality — góc mới chỉ làm được với model thế hệ này.

## Test ý tưởng (phải qua cả 4 mới build)
- [ ] Core loop chạy được trong 24h đầu?
- [ ] User là niche cụ thể (không phải 'everyone')?
- [ ] Demo ≤3 màn hình, judge hiểu trong 30s?
- [ ] Sponsor API không gỡ được (gỡ ra là demo chết)?

> Chốt concept: load skill `lablab-idea-forge` trong opencode với BRIEF này.

## Việc tiếp theo (hôm nay)
1. `python3 agent/scaffold.py wearedevelopers-hackathon` — sinh skeleton + demo script
2. Enroll trên lablab.ai (bấm tay), join Discord event
3. `python3 -c "from agent.store import set_status; set_status('wearedevelopers-hackathon','building')"`
4. Code MVP 1 tính năng đo được → quay demo 2 phút
5. `python3 agent/submit.py wearedevelopers-hackathon --check` trước khi Submit tay

_Luật an toàn: agent chỉ code + public quét. Enroll/Submit bấm tay trên browser._
