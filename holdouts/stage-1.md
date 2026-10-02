# Holdouts stage-1 — REVIEWER ONLY (implementer cấm đọc)

> Train/test separation: file này chỉ reviewer được mở. Implementer build theo spec, không build theo các ghi chú này. Mọi scenario dưới đây viết bằng plain English, reviewer tự dịch thành repro cụ thể khi verify. Không paste nguyên văn file này vào room chung khi implementer còn đọc được — reviewer chỉ công bố verdict ACCEPT/REJECT kèm invariant vi phạm + expected vs actual.

## H1 — Lost-response retry moves money once
Send a write with a fresh client marker, simulate a timeout after the server committed, then retry with the same marker and identical body. Expect the second reply to match the first verbatim with no second money move. Any double move is REJECT.

## H2 — Burst of identical submissions
Fire a burst (10 or more) of identical writes at once sharing one client marker from one user. Expect exactly one to take effect as new, the rest to replay identically. More than one effect is REJECT.

## H3 — Same marker, different body
Reuse a claimed client marker with a different body. Expect a conflict signal and no state change. Silent overwrite or second effect is REJECT.

## H4 — Failed write must not claim the marker
Send a write that fails validation, then reuse its marker with a valid body. Expect the valid retry to be treated as new (marker was never claimed by the failure). If the failure claimed the marker, REJECT.

## H5 — Drain race keeps total constant
From one wallet, race many draining transfers concurrently close to the full seeded total. Expect the sum of all wallets to stay equal to the last reset total at every observation, never negative even transiently. Any dip or leak is REJECT.

## H6 — Group move all-or-none
Attempt a group move where one member alone is short but the group net still covers, versus a group whose net is short. Expect the first to commit fully and the second to commit nothing (no partial member moves). Partial commit is REJECT.

## H7 — Uneven division rounding
Split an amount that does not divide evenly among several people. Expect shares to differ by at most one smallest unit, earlier-listed members favored, shares summing exactly, and a solo split still creating an obligation. Any other rounding is REJECT.

## H8 — Privacy isolation
A hidden activity must be visible only to its own parties, never to strangers, while an open activity is visible to all. Obligations must never appear in the public history feed. Any leak or hide-from-party is REJECT.

## H9 — Snapshot restore twice
Take a snapshot, keep writing on the source, restore into a clean instance, then restore again. Expect logins plus old markers and receipts to still work with no duplication and no loss. Duplication or loss is REJECT.

## H10 — Repro discipline
Every REJECT must cite: revision SHA, violated invariant in one sentence, repro steps, expected vs actual with numbers, and a log excerpt. No bare verdict without numbers.
