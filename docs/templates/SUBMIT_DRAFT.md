# SUBMIT DRAFT — copy-paste lên lablab.ai (đủ format, không bị trừ điểm)

## Title
Dark Factory — Mini Factory pocketful: spec ví → checked ledger code (BAND)

## Short desc (≤255 ký tự, hiện tại 178)
Spec ví 1 trang → factory plan-code-evaluate → ledger chứng minh conservation, 5/5 holdout, train/test tách biệt. BAND pocketful track.

## Long desc (≥100 từ — problem + solution + user)
Solo developer và team fintech indie 1-5 người ship tính năng tiền bạc sợ nhất ba thứ: tiền tự sinh ra, tiền mất không dấu vết, cùng một khoản bị tiêu hai lần. Một dòng sai trong hàm chuyển tiền là mất tiền thật, nhưng thuê auditor đọc từng diff tốn ~2h/task.

Dark Factory là software factory kiểm chứng ví tiền: viết SPEC 1 trang, factory tự plan-code, rồi một evaluator độc lập chấm 5 bài holdout conservation mà coder không bao giờ được đọc (train/test separation). Kết quả reproduce bằng `python3 src/main.py`: 5/5 passed, leak không, ~609 tokens/task.

User khởi điểm: Solana bounty hunter + fintech indie. Revenue: factory-as-service $19/seat/tháng, tiết kiệm ~2h review mỗi task. Track nhắm: pocketful (BAND). Live demo Streamlit + video quay LOOP thật trong BAND Desktop room 4ec606f4 (architect/coder/tester + human APPROVE).

## Tags
technology: band, python, streamlit | category: pocketful, devtools, fintech

## Cover 16:9
Chụp màn hình Streamlit báo 5/5 + dòng BAND room → crop 1280x720 PNG/JPG.

## Links điền khi submit
- Repo PUBLIC: (push xong điền — hiện chưa có remote)
- Demo: https://dark-factory.streamlit.app/
- Video: (quay xong điền YouTube unlisted + tick Not for Kids)
- Slides PDF: export từ DECK_OUTLINE.md (10 slides)
