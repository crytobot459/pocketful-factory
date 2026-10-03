# Holdouts stage-2 — REVIEWER ONLY (the implementer must not read this)

> Written in plain English so the reviewer can turn each one into a concrete repro. Do not
> paste this file into the room while the implementer can still read it. The reviewer publishes
> verdicts only: ACCEPT or REJECT, with the violated invariant and expected against actual.

The stage-2 specification describes a browser product. These notes ask the questions a
shipped check tends to skip: what the person sees when the answer is "no", and what happens
to the money and the state when the browser and the server disagree.

## S2-H1 — A refusal is visible, and nothing else is
Submit a payment the service refuses: too little money, an unknown destination, an amount with
more decimal places than the currency allows. Expect the refusal to be shown where the person
is looking, and the balance to be exactly what it was before the attempt. A refusal that is
reported only in a console, or that still moves money, is a REJECT.

## S2-H2 — No error element when there is no error
After a successful action, nothing that reports failure may still be on the page, not even
hidden. Expect a page state where "no error" is distinguishable from "error shown and then
dismissed", because a person cannot tell those apart either. A hidden leftover message is a
REJECT.

## S2-H3 — Two clicks move the money once
Submit the same form twice without changing anything. Expect exactly one effect and the second
attempt to report the first one's result rather than a refusal. Money moving twice is a REJECT.

## S2-H4 — Editing before submitting is a new action
Change a field, then submit. Expect the changed action to go through on its own merits rather
than being replayed from the previous attempt. Expect a refusal from the earlier attempt not to
appear against the new one. A stale refusal, or the new action being swallowed as a replay, is
a REJECT.

## S2-H5 — A preview agrees with what the server does
Compute a split's shares in the browser, then post it and read back what the server recorded.
Expect the previewed shares and the recorded shares to be identical, to the minor unit, for an
amount that does not divide evenly and for an odd participant order. A preview that is
approximately right is a REJECT: a person decides whether to agree based on that number.

## S2-H6 — Stale page, fresh server
Load a page, let the state change underneath it from another session, then act on what the
page shows. Expect the person's action to reflect the server's current state, never the state
the page was rendered from. Expect the page to re-read before it decides.

## S2-H7 — A lost response is recoverable without guessing
Have the request reach the server and commit, then lose the response on the way back. Expect
the person to be told the outcome is unknown and to be given a way to retry that cannot move
the money twice. Expect no message that leaves them unable to tell whether they were paid.

## S2-H8 — One person's money is not another's screen
With a hidden activity, load the feed as each party and as an uninvolved person. Expect the
involved parties to see it and the uninvolved person not to. Expect the same for an
outstanding obligation. Anything else is a REJECT.

## S2-H9 — Holds do not change the total
Take a hold, capture part of it, release the rest. Expect the total to be untouched by the hold
itself and to move only by what was actually captured. Expect spending to be judged against
what is available, never against what is held. Expect the three numbers on screen to be
distinguishable from each other.

## S2-H10 — The page works at a small size and with no network beyond its own origin
At a narrow viewport, expect every control reachable without horizontal scrolling and the
amounts still legible. With the outbound network unavailable, expect the page to render and
state its own failure rather than hanging.

## S2-H11 — Every state a person can reach has a name
Enumerate the states each screen can be in: signed out, signed in with an empty wallet,
signed in with activity, signed in after a refusal, signed in after an ambiguous outcome.
Expect each to have its own visible element, and expect the empty ones to say they are empty
rather than showing a blank area. A state with no testable element is a REJECT.

## S2-H12 — Repro discipline for this stage
Every REJECT must cite the revision SHA, the violated invariant in one sentence, the repro
steps, expected against actual with numbers, and a log excerpt. No bare verdict without
numbers.