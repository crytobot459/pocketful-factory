#!/usr/bin/env python3
"""The reviewer's scenarios, executable.

`holdouts/stage-N.md` says what should hold. This says what actually does, against a
running service, so that anyone can re-run the checks instead of taking the verdict's
word for it. Each scenario is named after the note it came from.

    # terminal one
    cd stage-4 && PORT=8080 python3 -m src.app

    # terminal two
    python3 holdouts/run_scenarios.py --base-url http://127.0.0.1:8080 --stage 4

Exit status is 0 when every scenario passed, 1 otherwise, and every failure prints what
was expected against what was read.

The three seeded accounts and their balances come from the event's published fixtures,
which is why the amounts below are the ones they are.
"""
from __future__ import annotations

import argparse
import json
import sys
import threading
import urllib.error
import urllib.request

BASE_HINT = "start the service first: cd stage-N && PORT=8080 python3 -m src.app"
USERS = [
    {"id": "u_ada", "email": "ada@example.com", "password": "correct horse",
     "display_name": "Ada", "handle": "ada", "balance": 10000},
    {"id": "u_bob", "email": "bob@example.com", "password": "correct horse",
     "display_name": "Bob", "handle": "bob", "balance": 2500},
    {"id": "u_cy", "email": "cy@example.com", "password": "correct horse",
     "display_name": "Cy", "handle": "cy", "balance": 500},
]
SEEDED_TOTAL = 13000


class Service:
    def __init__(self, base_url: str) -> None:
        self.base = base_url.rstrip("/")

    def call(self, method, path, body=None, key=None, token=None):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.base + path, data=data, method=method)
        req.add_header("Accept", "application/json")
        if data is not None:
            req.add_header("Content-Type", "application/json")
        if key:
            req.add_header("Idempotency-Key", key)
        if token:
            req.add_header("Authorization", "Bearer " + token)
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                return resp.status, json.loads(resp.read() or b"{}")
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read() or b"{}")

    def login(self, email):
        _, body = self.call("POST", "/auth/login",
                            {"email": email, "password": "correct horse"})
        return body.get("token") or body.get("access_token")

    def reset(self):
        self.call("POST", "/_test/reset",
                  {"currency": "EUR", "minor_units": 2, "users": USERS})

    @staticmethod
    def code(body):
        return (body.get("error") or {}).get("code", "")

    @staticmethod
    def payment(body):
        return body.get("payment") or body


class Report:
    def __init__(self, stage: int) -> None:
        self.stage = stage
        self.failures: list[tuple[str, object, object]] = []

    def check(self, name: str, got, want) -> None:
        ok = got == want
        if not ok:
            self.failures.append((name, got, want))
        print(f"  {'PASS' if ok else 'FAIL'}  {name}: got {got!r}, want {want!r}")


# --- stage 1 ---------------------------------------------------------------

def stage_one(svc: Service, rep: Report) -> None:
    """holdouts/stage-1.md — H1..H10."""
    svc.reset()
    ada = svc.login("ada@example.com")
    bob = svc.login("bob@example.com")

    # H1 lost-response retry moves money once
    body = {"to_handle": "bob", "amount": 500, "note": "dinner", "visibility": "public"}
    first = svc.call("POST", "/payments", body, "h1", ada)[0]
    _, feed = svc.call("GET", "/activity", None, None, ada)
    moving = lambda: len([p for p in svc.call("GET", "/activity", None, None, bob)[1]
                          .get("payments", []) if p.get("amount") == 500])
    rep.check("H1 first write is created", first, 201)
    rep.check("H1 retry replays the same body", svc.call("POST", "/payments", body, "h1", ada)[0], 200)
    rep.check("H1 and the money moved once", moving(), 1)

    # H2 a burst of identical writes
    results = []
    lock = threading.Lock()

    def burst():
        r = svc.call("POST", "/payments",
                     {"to_handle": "bob", "amount": 250, "note": "burst", "visibility": "public"},
                     "h2", ada)[0]
        with lock:
            results.append(r)

    threads = [threading.Thread(target=burst) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    rep.check("H2 exactly one burst write is created", results.count(201), 1)
    rep.check("H2 the rest replay", results.count(200), 9)
    _, feed = svc.call("GET", "/activity", None, None, bob)
    rep.check("H2 and 250 moved once",
              len([p for p in feed.get("payments", []) if p.get("amount") == 250]), 1)

    # H3 the same marker with a different body
    st, body_out = svc.call("POST", "/payments",
                            {"to_handle": "bob", "amount": 999, "note": "x", "visibility": "public"},
                            "h1", ada)
    rep.check("H3 a reused marker with a different body conflicts",
              (st, svc.code(body_out)), (409, "idempotency_key_reuse"))

    # H4 a failed write must not claim the marker
    svc.call("POST", "/payments", {"to_handle": "bob", "amount": -5}, "h4", ada)
    st, _ = svc.call("POST", "/payments",
                     {"to_handle": "bob", "amount": 300, "note": "fresh", "visibility": "public"},
                     "h4", ada)
    rep.check("H4 the marker was still free after a failure", st, 201)

    # H5 a drain race keeps the total constant
    def total():
        return sum(int(svc.call("GET", "/me", None, None,
                                svc.login(u["email"]))[1]["balance"]) for u in USERS)
    rep.check("H5 the total is the seeded total before the race", total(), SEEDED_TOTAL)
    outs = []

    def drain():
        st, b = svc.call("POST", "/payments",
                         {"to_handle": "bob", "amount": 4000, "note": "d", "visibility": "public"},
                         f"drain-{threading.get_ident()}", ada)
        with lock:
            outs.append(st)

    threads = [threading.Thread(target=drain) for _ in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    rep.check("H5 the total is unchanged after the race", total(), SEEDED_TOTAL)
    rep.check("H5 and no balance went negative",
              any(int(svc.call("GET", "/me", None, None, svc.login(u["email"]))[1]["balance"]) < 0
                  for u in USERS), False)

    # H7 uneven division rounding
    # H7 uneven division rounding, with the earlier-listed member taking the odd unit
    st, sp = svc.call("POST", "/splits",
                      {"amount": 1000, "participant_handles": ["ada", "bob", "cy"],
                       "note": "split"}, "h7", ada)
    shares = [s.get("amount") for s in sp.get("shares", [])]
    rep.check("H7 a split of 1000 among three is accepted", st, 201)
    rep.check("H7 and the shares sum to 1000", sum(shares), 1000)
    rep.check("H7 the earlier member takes the odd unit", shares[:3], [334, 333, 333])
    rep.check("H7 and no part differs by more than one",
              max(shares) - min(shares) <= 1, True)

    # H8 privacy isolation
    svc.call("POST", "/payments", {"to_handle": "bob", "amount": 100, "note": "secret",
                                   "visibility": "private"}, "h8", ada)
    cy = svc.login("cy@example.com")
    _, f_ada = svc.call("GET", "/activity", None, None, ada)
    _, f_bob = svc.call("GET", "/activity", None, None, bob)
    _, f_cy = svc.call("GET", "/activity", None, None, cy)
    rep.check("H8 a stranger cannot see a private activity",
              any(p.get("visibility") == "private" for p in f_cy.get("payments", [])), False)
    rep.check("H8 its parties can",
              (any(p.get("visibility") == "private" for p in f_ada.get("payments", [])),
               any(p.get("visibility") == "private" for p in f_bob.get("payments", []))),
              (True, True))


# --- stage 3 ---------------------------------------------------------------

def stage_three(svc: Service, rep: Report) -> None:
    """holdouts/stage-3.md — S3-H1..S3-H11."""
    svc.reset()
    ada = svc.login("ada@example.com")
    bob = svc.login("bob@example.com")

    _, p = svc.call("POST", "/payments", {"to_handle": "bob", "amount": 1000, "note": "dinner",
                                          "visibility": "public"}, "s3-a", ada)
    pid = svc.payment(p).get("payment_id") or svc.payment(p).get("id")
    before = int(svc.call("GET", "/me", None, None, ada)[1]["balance"])

    # S3-H1 a correction that cannot be afforded changes nothing
    st, out = svc.call("POST", f"/payments/{pid}/corrections",
                       {"expected_revision": 1, "amount": 100000,
                        "effective_at": "2026-09-20T12:00:00+00:00", "reason": "t"}, "s3-b", ada)
    rep.check("S3-H1 an unaffordable correction is refused",
              (st, svc.code(out)), (409, "insufficient_funds"))
    rep.check("S3-H1 and the balance did not move",
              int(svc.call("GET", "/me", None, None, ada)[1]["balance"]), before)

    # S3-H2 a correction that succeeds advances the revision. Correcting a 1000
    # payment down to 500 gives the difference back, so the balance rises.
    st, out = svc.call("POST", f"/payments/{pid}/corrections",
                       {"expected_revision": 1, "amount": 500,
                        "effective_at": "2026-09-20T12:00:00+00:00", "reason": "t"}, "s3-c", ada)
    rep.check("S3-H2 an affordable correction is accepted", st, 201)
    rep.check("S3-H2 and the revision advanced", out.get("revision"), 2)
    rep.check("S3-H2 and the difference came back",
              int(svc.call("GET", "/me", None, None, ada)[1]["balance"]), before + 500)

    # S3-H3 the same correction twice is one correction
    rep.check("S3-H3 replaying it returns the same revision",
              svc.call("POST", f"/payments/{pid}/corrections",
                       {"expected_revision": 1, "amount": 500,
                        "effective_at": "2026-09-20T12:00:00+00:00", "reason": "t"},
                       "s3-c", ada)[1].get("revision"), 2)
    rep.check("S3-H3 and the balance is unchanged",
              int(svc.call("GET", "/me", None, None, ada)[1]["balance"]), before + 500)

    # S3-H4 the same key with a different correction is a conflict
    st, out = svc.call("POST", f"/payments/{pid}/corrections",
                       {"expected_revision": 1, "amount": 400,
                        "effective_at": "2026-09-20T12:00:00+00:00", "reason": "t"}, "s3-c", ada)
    rep.check("S3-H4 a reused marker with a different correction conflicts",
              (st, svc.code(out)), (409, "idempotency_key_reuse"))

    # S3-H5 a statement's arithmetic closes
    _, st_body = svc.call("GET", "/statement", None, None, ada)
    entries = st_body.get("entries", [])
    closes = True
    running = st_body.get("opening_balance")
    for e in entries:
        running += e.get("delta", 0)
        closes = closes and running == e.get("balance_after")
    rep.check("S3-H5 the statement's running balance closes", closes, True)
    rep.check("S3-H5 and ends at the reported balance",
              entries[-1].get("balance_after") if entries else st_body.get("opening_balance"),
              int(svc.call("GET", "/me", None, None, ada)[1]["balance"]))

    # S3-H6 a statement is frozen once taken
    snapshot = st_body.get("snapshot")
    svc.call("POST", "/payments", {"to_handle": "bob", "amount": 300, "note": "later",
                                   "visibility": "public"}, "s3-d", ada)
    query = f"?snapshot={snapshot}" if snapshot else ""
    _, again = svc.call("GET", "/statement" + query, None, None, ada)
    rep.check("S3-H6 a snapshot does not pick up later writes",
              len(again.get("entries", [])), len(entries))
    rep.check("S3-H6 while a fresh statement does",
              len(svc.call("GET", "/statement", None, None, ada)[1].get("entries", [])) > len(entries),
              True)

    # S3-H8 two parties see two different statements
    _, s_ada = svc.call("GET", "/statement", None, None, ada)
    _, s_bob = svc.call("GET", "/statement", None, None, bob)
    rep.check("S3-H8 the two statements are not the same",
              s_ada.get("opening_balance") == s_bob.get("opening_balance"), False)

    # S3-H9 conservation survives corrections
    rep.check("S3-H9 every balance still sums to the seeded total",
              sum(int(svc.call("GET", "/me", None, None, svc.login(u["email"]))[1]["balance"])
                  for u in USERS), SEEDED_TOTAL)


# --- stage 4 ---------------------------------------------------------------

def stage_four(svc: Service, rep: Report) -> None:
    """holdouts/stage-4.md — S4-H1..S4-H10."""
    svc.reset()
    ada = svc.login("ada@example.com")
    bob = svc.login("bob@example.com")
    cy = svc.login("cy@example.com")

    _, p = svc.call("POST", "/payments", {"to_handle": "bob", "amount": 1000, "note": "n",
                                          "visibility": "public"}, "s4-a", ada)
    pid = svc.payment(p).get("payment_id") or svc.payment(p).get("id")
    rep.check("the sender may correct",
              svc.call("POST", f"/payments/{pid}/corrections",
                       {"expected_revision": 1, "amount": 500,
                        "effective_at": "2026-09-20T12:00:00+00:00", "reason": "t"},
                       "s4-a", ada)[0], 201)

    # S4-H1 the cap follows the corrected amount
    st, out = svc.call("POST", f"/payments/{pid}/refunds", {"amount": 600}, "s4-b", bob)
    rep.check("S4-H1 a refund above the corrected amount is refused",
              (st, svc.code(out)), (422, "refund_exceeds_payment"))
    st, r = svc.call("POST", f"/payments/{pid}/refunds", {"amount": 500}, "s4-c", bob)
    rep.check("S4-H1 a refund at the corrected amount is accepted", st, 201)
    rid = svc.payment(r).get("payment_id") or svc.payment(r).get("id")

    # S4-H2 the refund flows bob -> ada, so ada is its receiver
    st, out = svc.call("POST", f"/payments/{rid}/refunds", {"amount": 100}, "s4-d", ada)
    rep.check("S4-H2 refunding a refund is refused",
              (st, svc.code(out)), (422, "invalid_refund_target"))

    # S4-H3 a refund cannot itself be corrected
    st, out = svc.call("POST", f"/payments/{rid}/corrections",
                       {"expected_revision": 1, "amount": 0,
                        "effective_at": "2026-09-20T12:00:00+00:00", "reason": "t"}, "s4-e", bob)
    rep.check("S4-H3 correcting a refund is refused",
              (st, svc.code(out)), (422, "linked_payment_immutable"))

    # S4-H4 a correction cannot go below what was refunded
    st, out = svc.call("POST", f"/payments/{pid}/corrections",
                       {"expected_revision": 2, "amount": 400,
                        "effective_at": "2026-09-21T12:00:00+00:00", "reason": "t"}, "s4-f", ada)
    rep.check("S4-H4 a correction below the refunded amount is refused",
              (st, svc.code(out)), (422, "refund_exceeds_payment"))

    # S4-H6 only the receiver may refund
    _, p2 = svc.call("POST", "/payments", {"to_handle": "cy", "amount": 200, "note": "x",
                                           "visibility": "public"}, "s4-g", bob)
    p2id = svc.payment(p2).get("payment_id") or svc.payment(p2).get("id")
    rep.check("S4-H6 the receiver may refund",
              svc.call("POST", f"/payments/{p2id}/refunds", {"amount": 100}, "s4-h", cy)[0], 201)
    st, out = svc.call("POST", f"/payments/{p2id}/refunds", {"amount": 100}, "s4-i", bob)
    rep.check("S4-H6 the sender may not refund",
              (st, svc.code(out)), (403, "forbidden"))

    # S4-H7 a batch short on one member applies nothing
    _, revs_before = svc.call("GET", f"/payments/{p2id}/revisions", None, None, bob)
    st, _ = svc.call("POST", "/correction-batches", {"corrections": [
        {"payment_id": pid, "expected_revision": 2, "amount": 0,
         "effective_at": "2026-09-22T12:00:00+00:00", "reason": "r"},
        {"payment_id": p2id, "expected_revision": 1, "amount": 5000,
         "effective_at": "2026-09-22T12:00:00+00:00", "reason": "r"}]}, "s4-j", ada)
    rep.check("S4-H7 an unaffordable batch is refused", st in (403, 422), True)
    _, revs_after = svc.call("GET", f"/payments/{p2id}/revisions", None, None, bob)
    rep.check("S4-H7 and left the affordable member untouched", revs_after, revs_before)


# --- main ------------------------------------------------------------------

STAGES = {1: ("stage-1: idempotency, conservation, privacy", stage_one),
          3: ("stage-3: corrections, statements, snapshots", stage_three),
          4: ("stage-4: refunds, batch corrections", stage_four)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base-url", default="http://127.0.0.1:8080")
    ap.add_argument("--stage", type=int, required=True, choices=sorted(STAGES))
    args = ap.parse_args()

    if args.stage not in STAGES:
        print(f"No executable scenarios for stage {args.stage}; see holdouts/stage-{args.stage}.md",
              file=sys.stderr)
        return 0

    title, runner = STAGES[args.stage]
    svc = Service(args.base_url)
    rep = Report(args.stage)
    print(f"{title}\nagainst {svc.base}\n")
    try:
        runner(svc, rep)
    except urllib.error.URLError as exc:
        print(f"could not reach the service: {exc}\n{BASE_HINT}", file=sys.stderr)
        return 2

    print()
    if rep.failures:
        print(f"{len(rep.failures)} scenario(s) failed on this build:")
        for name, got, want in rep.failures:
            print(f"  {name}: expected {want!r}, got {got!r}")
        return 1
    print("every scenario in this file passes on this build")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())