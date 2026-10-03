# Holdouts stage-3 — REVIEWER ONLY (the implementer must not read this)

> **Transcribed after the fact.** The reviewer seat ran these scenarios during the stage-3
> verification and reported the results in the room; it did not persist them to a file first.
> They are written down here from that verdict, and the gap is real: a scenario that lives only
> in one seat's context cannot be re-run by anyone else. The fix is for the reviewer to write the
> file before it starts, and `mandates/factory-tester-df.md` now says so.

Plain English, one line per scenario. Expected values in brackets are the ones the reviewer
reported against revision `92d9a5f`.

## S3-H1 — A correction that cannot be afforded changes nothing
Correct a payment down by more than the sender can cover. Expect a refusal and the balance
exactly as it was. [correction 1000 → 500 rejected, balance stayed 1000]

## S3-H2 — A correction that succeeds leaves no error behind
Apply a correction that is affordable. Expect the revision to advance, the balance to move, and
no failure message anywhere on the response. [revision 2, balance 9500]

## S3-H3 — The same correction twice is one correction
Resend a correction with the same key and body. Expect the same revision back and one movement
of money. [revision 2 again, balance 9500]

## S3-H4 — The same key with a different correction is a conflict
Resend a correction key with different content. Expect a conflict and no movement, rather than
the second correction quietly replacing the first.

## S3-H5 — A statement's arithmetic closes
Take a statement and check that opening balance, each delta, and the balance after each entry
reconcile against the balances the service reports. [opening 10000, delta -500, balance after
9500]

## S3-H6 — A statement is frozen once taken
Take a statement, then let more payments land, then read the statement again. Expect the
statement to be identical. [snapshot closing 9500, fresh closing 7500]

## S3-H7 — A lost response after a correction is recoverable
Let the correction commit, lose the response, retry with the same key. Expect the same revision,
not a second movement. [revision 3, balance 7700]

## S3-H8 — Two people's statements are two different statements
Ask two parties for their statements over the same window. Expect each to see only their own
side, and the two to disagree. [Ada 7700, Bob 2300]

## S3-H9 — Conservation survives corrections
Sum every balance after a run of corrections. Expect the seeded total. [7700 + 2300 = 10000]

## S3-H10 — Repro discipline for this stage
Every rejection cites the revision, the violated invariant, the repro, expected against actual
with numbers, and a log excerpt.

## S3-H11 — Hold accounting over time
A hold taken before a correction, then read afterwards, must still show what was held and when.