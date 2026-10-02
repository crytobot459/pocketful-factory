# CONCEPT_SCORED — wearedevelopers-hackathon (stack band)
Weights: Presentation 20 + Business Value 20 + Technology 40 + Originality 20 = 100

| # | Ý tưởng | Pres | Biz | Tech | Orig | Tổng/10 | ≥7 |
|---|---|---|---|---|---|---|---|
| 1 | Factory đo được: planner→coder→evaluator trong BAND Desktop, báo evaluator pass-rate + ove… | 8 | 4 | 10 | 6 | **7.6** | 2/4 |
| 2 | Spec-to-CRUD: 1 spec văn bản ra 1 app CRUD qua factory, holdout scenarios coder không được… | 4 | 4 | 8 | 7 | **6.2** | 2/4 |
| 3 | AGENTS.md showcase: repo mẫu mà agent nào vào cũng build được ngay, đo số bước tay còn lại… | 6 | 4 | 3 | 4 | **4.0** | 0/4 |

## Winner: ý tưởng 1 — 7.6/10, ăn 2/4 chiều (cần ≥3 chiều ≥7)
> Factory đo được: planner→coder→evaluator trong BAND Desktop, báo evaluator pass-rate + override-rate + token/task. Video quay cái LOOP, không quay UI app.

### Vì sao thắng (matched keywords)
- Presentation 8/10: base 4 (demo được trong 24h); +2 quay/screencast rõ; +2 có số đo/trước-sau
- Business Value 4/10: base 4 (1 job thật)
- Technology 10/10: base 3; +5 sponsor hits: band,factory,planner,evaluator; +2 bằng chứng chạy được
- Originality 6/10: base 4; +2 pattern ít đối thủ

### Ablation test (gỡ sponsor ra phải chết)
- [ ] Gỡ sponsor SDK/key ra → demo có chết không? (không chết = trừ Tech/Orig)
- [ ] Core loop 24h? Niche? ≤3 màn hình?

> Chốt tay: copy winner vào `build/wearedevelopers-hackathon/CONCEPT.md`, rồi `python3 agent/scaffold.py wearedevelopers-hackathon --hf`
> Khoảng trống: `work/gaps/wearedevelopers-hackathon.md` | Rubric: `config/rubrics/wearedevelopers-hackathon.yaml`
