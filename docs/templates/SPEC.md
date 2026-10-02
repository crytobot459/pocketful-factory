# SPEC — mini_ledger (versioned, coder chỉ đọc file này + AGENTS.md)

## Goal
Sinh module `mini_ledger` ví mẫu trong bộ nhớ: nạp/rút/chuyển/tồn — đủ để
chứng minh TIỀN KHÔNG TỰ SINH, KHÔNG MẤT, KHÔNG TIÊU 2 LẦN (pocketful track).

## Interfaces (bắt buộc, tên hàm + chữ ký)
- `deposit(acct: str, amount: float) -> dict` — nạp, trả `{acct, balance}`. amount ≤ 0 raise ValueError.
- `withdraw(acct: str, amount: float) -> dict` — rút, thiếu tiền raise ValueError.
- `transfer(src: str, dst: str, amount: float) -> dict` — chuyển, thiếu tiền raise ValueError.
- `balance(acct: str) -> float` — số dư (tài khoản mới = 0).
- `total() -> float` — tổng mọi tài khoản (bảo toàn: chỉ đổi khi deposit/withdraw).
- `clear() -> None` — reset giữa các test evaluator.

## Constraints
- Stdlib only, không mạng, không file ngoài bộ nhớ.
- Không đọc `holdout.json` trong code sinh ra (evaluator kiểm tra bằng grep).

## Non-goals
- Không persistence, không auth, không UI web. Chỉ module + hàm đúng spec.
