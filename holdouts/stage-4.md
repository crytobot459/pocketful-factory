# Holdouts stage-4 — REVIEWER ONLY (implementer cấm đọc)

> **Transcribed after the fact**, the same way as `stage-3.md`. The reviewer reported these
> against revision `92d9a5f` as the stage-4 folder, before the last fix landed as `b88cb7b`;
> the three gaps below are what that verdict found and what `b88cb7b` closed.

## S4-H1 — The refund cap follows the corrected amount, not the original
Correct a payment down, then try to refund more than the corrected amount. Expect a refusal.
[correction 1000 → 500, refund 600 → `refund_exceeds_payment`]

## S4-H2 — Refunding a refund is refused
Refund a payment, then try to refund the refund. Expect a refusal.

## S4-H3 — A refund cannot itself be corrected
Try to correct a refund payment. Expect a refusal.
[observed as `linked_payment_immutable`]

## S4-H4 — A correction cannot go below what was already refunded
Refund part of a payment, then try to correct it to less than the refunded amount. Expect a
refusal rather than a balance that disagrees with the refund.

## S4-H5 — A refund moves available, not held
Hold funds, then refund from the same wallet. Expect the hold to be untouched and the refund to
come out of what is available, or to fail if only held funds exist.

## S4-H6 — Only the receiver may refund
Attempt a refund from the sender's side. Expect a refusal.

## S4-H7 — A batch correction is all or nothing
Attempt a batch where one member's share is short. Expect nothing in the batch to be applied.

## S4-H8 — A batch covering a settlement takes all of its members
Attempt a batch correction naming some but not all members of a settlement. Expect a refusal
and no change to any member.

## S4-H9 — A batch is checked for money across all its members together
Two corrections in one batch against one wallet's available funds. Expect the batch to succeed
only if the sum is affordable.
[observed: two +1000 deltas against 1000 available → `insufficient_funds`]

## S4-H10 — Repro discipline for this stage
Every rejection cites the revision, the violated invariant, the repro, expected against actual
with numbers, and a log excerpt.