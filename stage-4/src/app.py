"""Pocketful Stage-4 — stage-3 API plus refunds and batch corrections.

Receivers can refund a payment (new linked reverse payment). Settlement
operators can correct several payments atomically, including whole
settlements. Ten idempotent write paths. Earlier receipts, retries and
snapshots keep their original form.
"""
import copy
import hashlib
import hmac
import os
import re
import secrets
import threading
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi import Response

app = FastAPI()
_lock = threading.Lock()

_state = {
    "currency": "EUR",
    "minor_units": 2,
    "users_by_id": {},
    "users_by_email": {},
    "users_by_handle": {},
    "tokens": {},
    "payments": {},
    "requests": {},
    "splits": {},
    "settlements": {},
    "idempotency": {},
    "settlement_operator_ids": [],
    "authorizations": {},
    "authorization_ttl_seconds": 600,
    "openings": {},
    "snapshots": {},
    "correction_batches": {},
    "seq": 0,
}

HANDLE_RE = re.compile(r"^[a-z0-9_]{1,20}$")
LIMIT_RE = re.compile(r"^[0-9]+$")


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def _now():
    return datetime.now(timezone.utc)


def _parse_ts(s):
    try:
        if not isinstance(s, str):
            return None
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


def auth_effectively_open(a) -> bool:
    """An authorization holds funds iff stored open and not clock-expired."""
    if a.get("status") != "open":
        return False
    exp = _parse_ts(a.get("expires_at"))
    if exp is None:
        return False
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    return exp > _now()


def auth_status(a) -> str:
    if a.get("status") != "open":
        return a.get("status", "open")
    return "open" if auth_effectively_open(a) else "expired"


def auth_remaining(a) -> int:
    if not auth_effectively_open(a):
        return 0
    try:
        return max(0, int(a.get("amount", 0)) - int(a.get("captured_amount", 0)))
    except Exception:
        return 0


def held_for(uid) -> int:
    total = 0
    for a in _state["authorizations"].values():
        if a.get("from_user_id") == uid and auth_effectively_open(a):
            try:
                total += max(0, int(a.get("amount", 0)) - int(a.get("captured_amount", 0)))
            except Exception:
                pass
    return total


def available_for(user) -> int:
    return int(user.get("balance", 0)) - held_for(user.get("id"))


_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


def _parse_instant(s):
    """Strict RFC 3339 instant with an explicit offset; None otherwise.

    Rejects naive local times, bare dates and empty values.
    """
    if not isinstance(s, str) or not s:
        return None
    try:
        d = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None
    if not isinstance(d, datetime) or d.tzinfo is None:
        return None
    return d


def _is_int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def _newest_first(items):
    """Newest first by created_at; ties keep creation (_seq) order."""
    def keyf(x):
        return (_parse_instant(x.get("created_at")) or _EPOCH, x.get("_seq", 0))
    return sorted(items, key=keyf, reverse=True)


def _pay_revisions(p):
    revs = p.get("revisions")
    if isinstance(revs, list) and revs:
        return revs
    return [{"revision": 1, "amount": p.get("amount", 0),
             "effective_at": p.get("created_at"), "recorded_at": p.get("created_at"),
             "reason": ""}]


def _selected_rev(p, K):
    """Latest revision recorded at or before K; None if none was yet recorded."""
    best = None
    for r in _pay_revisions(p):
        rd = _parse_instant(r.get("recorded_at"))
        if rd is None or rd > K:
            continue
        best = r
    return best


def _latest_rev(p):
    revs = _pay_revisions(p)
    return revs[-1]


def _signed(uid, p, amount):
    return amount if p.get("to_user_id") == uid else -amount


def _balance_at(uid, T, K):
    """Total for uid at instant T under knowledge K (latest recorded <= K,
    applied by effective time)."""
    bal = _state["openings"].get(uid, 0)
    for p in _state["payments"].values():
        if p.get("from_user_id") != uid and p.get("to_user_id") != uid:
            continue
        r = _selected_rev(p, K)
        if r is None:
            continue
        eff = _parse_instant(r.get("effective_at"))
        if eff is None or eff > T:
            continue
        bal += _signed(uid, p, r.get("amount", 0))
    return bal


def _capture_events(a):
    """(time, amount) of each capture linked to an authorization."""
    out = []
    for pid in a.get("payment_ids", []) or []:
        cp = _state["payments"].get(pid)
        if not cp:
            continue
        ct = _parse_instant(cp.get("created_at"))
        if ct is None:
            continue
        try:
            out.append((ct, int(cp.get("amount", 0))))
        except Exception:
            pass
    return out


def _auth_closed_at(a):
    ca = a.get("closed_at")
    if isinstance(ca, str) and _parse_instant(ca) is not None:
        return _parse_instant(ca)
    return None


def _held_at(uid, T):
    """Funds held for uid at instant T from authorization lifecycle events."""
    held = 0
    for a in _state["authorizations"].values():
        if a.get("from_user_id") != uid:
            continue
        c = _parse_instant(a.get("created_at"))
        if c is None or T < c:
            continue
        exp = _parse_instant(a.get("expires_at"))
        if exp is not None and T >= exp:
            continue
        cd = _auth_closed_at(a)
        if cd is not None and T >= cd:
            continue
        try:
            amt = int(a.get("amount", 0))
        except Exception:
            continue
        cap = sum(v for (t, v) in _capture_events(a) if t <= T)
        held += max(0, amt - cap)
    return held


def _hold_event_times(uid):
    times = set()
    for a in _state["authorizations"].values():
        if a.get("from_user_id") != uid:
            continue
        for key in ("created_at", "expires_at", "closed_at"):
            v = a.get(key)
            if isinstance(v, str):
                d = _parse_instant(v)
                if d is not None:
                    times.add(d)
        for (t, _v) in _capture_events(a):
            times.add(t)
    return times


def _revision_view(pid, r):
    return {
        "payment_id": pid,
        "revision": r.get("revision", 1),
        "amount": r.get("amount", 0),
        "effective_at": r.get("effective_at"),
        "recorded_at": r.get("recorded_at"),
        "reason": r.get("reason", ""),
        "correction_batch_id": r.get("correction_batch_id"),
    }


def _refunded_total(pid):
    """Sum of refund payment amounts targeting pid (latest revision each)."""
    total = 0
    for q in _state["payments"].values():
        if q.get("refund_of") == pid:
            total += _latest_rev(q).get("amount", 0)
    return total


def err(status, code, message="error"):
    return JSONResponse({"error": {"code": code, "message": message}}, status_code=status)


def _next_seq():
    _state["seq"] += 1
    return _state["seq"]


def _unique_id(prefix, existing):
    while True:
        _state["seq"] += 1
        cand = f"{prefix}_{_state['seq']}"
        if cand not in existing and len(cand) <= 64:
            return cand


def hash_password(pw: str) -> str:
    salt = secrets.token_hex(16)
    it = 12000
    dk = hashlib.pbkdf2_hmac("sha256", pw.encode("utf-8"), salt.encode("utf-8"), it)
    return f"pbkdf2${it}${salt}${dk.hex()}"


def verify_password(pw: str, stored: str) -> bool:
    try:
        parts = stored.split("$")
        if parts[0] != "pbkdf2" or len(parts) != 4:
            return False
        it = int(parts[1])
        salt = parts[2]
        expect = parts[3]
        dk = hashlib.pbkdf2_hmac("sha256", pw.encode("utf-8"), salt.encode("utf-8"), it)
        return hmac.compare_digest(dk.hex(), expect)
    except Exception:
        return False


def derive_handle(email: str) -> str:
    local = email.split("@")[0].lower() if "@" in email else email.lower()
    h = "".join(c if (c.isalnum() and c.isascii() and (c.islower() or c.isdigit()) or c == "_") else "_" for c in local)
    # redo strictly: keep [a-z0-9_]
    out = []
    for c in local:
        if "a" <= c <= "z" or "0" <= c <= "9" or c == "_":
            out.append(c)
        else:
            out.append("_")
    h = "".join(out)[:20]
    return h or "user"


def valid_email(email: str) -> bool:
    if not isinstance(email, str) or " " in email:
        return False
    if email.count("@") != 1:
        return False
    local, domain = email.split("@", 1)
    if not local or not domain:
        return False
    return True


def parse_amount(v):
    if isinstance(v, bool):
        return None, False
    if isinstance(v, int):
        if 1 <= v <= 1000000000:
            return v, True
        return None, False
    if isinstance(v, float):
        if v.is_integer() and 1 <= int(v) <= 1000000000:
            return int(v), True
        return None, False
    return None, False


def validate_note(body, key="note"):
    if key not in body:
        return "", True
    v = body[key]
    if not isinstance(v, str):
        return None, False
    if len(v) > 200:
        return None, False
    return v, True


def validate_visibility(body):
    if "visibility" not in body:
        return "public", True
    v = body["visibility"]
    if not isinstance(v, str) or v not in ("public", "private"):
        return None, False
    return v, True


def get_auth_user(request: Request):
    auth = request.headers.get("authorization")
    if not auth or not auth.startswith("Bearer "):
        return None
    token = auth[len("Bearer "):]
    if not token:
        return None
    with _lock:
        uid = _state["tokens"].get(token)
        if not uid:
            return None
        u = _state["users_by_id"].get(uid)
        return u


def get_idem_key(request: Request):
    v = request.headers.get("idempotency-key")
    if v is None:
        v = request.headers.get("Idempotency-Key")
    return v


def idem_lookup(uid, key, method, path, body):
    k = (uid, key, method, path)
    rec = _state["idempotency"].get(k)
    if rec is None:
        return None, False
    if rec["body"] == body:
        return rec, True
    return rec, False  # same key different body


def idem_store(uid, key, method, path, body, response_body):
    k = (uid, key, method, path)
    _state["idempotency"][k] = {"body": copy.deepcopy(body), "response": copy.deepcopy(response_body)}


def payment_view(p):
    return {
        "payment_id": p["payment_id"],
        "from_user_id": p["from_user_id"],
        "from_handle": p["from_handle"],
        "to_user_id": p["to_user_id"],
        "to_handle": p["to_handle"],
        "amount": p["amount"],
        "currency": p["currency"],
        "note": p["note"],
        "visibility": p["visibility"],
        "request_id": p.get("request_id"),
        "settlement_id": p.get("settlement_id"),
        "authorization_id": p.get("authorization_id"),
        "refund_of": p.get("refund_of"),
        "created_at": p["created_at"],
    }


def auth_view(a):
    st = auth_status(a)
    if st == "open":
        closed = None
    else:
        closed = a.get("closed_at")
        if not isinstance(closed, str):
            closed = a.get("expires_at") if st == "expired" else a.get("created_at")
    return {
        "authorization_id": a["authorization_id"],
        "from_user_id": a["from_user_id"],
        "from_handle": a["from_handle"],
        "to_user_id": a["to_user_id"],
        "to_handle": a["to_handle"],
        "amount": a["amount"],
        "captured_amount": int(a.get("captured_amount", 0)),
        "remaining_amount": auth_remaining(a),
        "currency": a["currency"],
        "note": a["note"],
        "visibility": a["visibility"],
        "status": st,
        "expires_at": a["expires_at"],
        "closed_at": closed,
        "payment_id": a.get("payment_id"),
        "payment_ids": list(a.get("payment_ids", [])),
        "created_at": a["created_at"],
    }


def request_view(r):
    return {
        "request_id": r["request_id"],
        "requester_id": r["requester_id"],
        "requester_handle": r["requester_handle"],
        "payer_id": r["payer_id"],
        "payer_handle": r["payer_handle"],
        "amount": r["amount"],
        "currency": r["currency"],
        "note": r["note"],
        "status": r["status"],
        "payment_id": r.get("payment_id"),
        "created_at": r["created_at"],
    }


async def parse_obj(request: Request):
    try:
        body = await request.json()
    except Exception:
        return None, err(400, "malformed_request", "malformed request")
    if not isinstance(body, dict):
        return None, err(400, "malformed_request", "malformed request")
    return body, None


def parse_limit_offset(params, defaults=(50, 0)):
    raw_limit = params.get("limit")
    raw_offset = params.get("offset")
    if raw_limit is None:
        limit = defaults[0]
    else:
        s = str(raw_limit)
        if not LIMIT_RE.match(s):
            return None, None, err(422, "validation_failed", "bad limit")
        limit = int(s)
        if not (1 <= limit <= 200):
            return None, None, err(422, "validation_failed", "bad limit")
    if raw_offset is None:
        offset = defaults[1]
    else:
        s = str(raw_offset)
        if not LIMIT_RE.match(s):
            return None, None, err(422, "validation_failed", "bad offset")
        offset = int(s)
        if offset < 0:
            return None, None, err(422, "validation_failed", "bad offset")
    return limit, offset, None


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/_test/reset")
async def test_reset(request: Request):
    body, e = await parse_obj(request)
    if e:
        return e
    currency = body.get("currency")
    minor_units = body.get("minor_units")
    users = body.get("users")
    payments = body.get("payments", [])
    requests_ = body.get("requests", [])
    ops = body.get("settlement_operator_ids", [])
    auths_seed = body.get("authorizations", [])
    ttl_raw = body.get("authorization_ttl_seconds", 600)
    if isinstance(ttl_raw, bool):
        return err(422, "validation_failed", "bad authorization_ttl_seconds")
    if isinstance(ttl_raw, int):
        ttl = ttl_raw
    elif isinstance(ttl_raw, float) and float(ttl_raw).is_integer():
        ttl = int(ttl_raw)
    else:
        return err(422, "validation_failed", "bad authorization_ttl_seconds")
    if ttl < 1:
        return err(422, "validation_failed", "bad authorization_ttl_seconds")
    if not isinstance(currency, str) or not currency:
        return err(422, "validation_failed", "bad currency")
    if minor_units not in (0, 2, 3):
        return err(422, "validation_failed", "bad minor_units")
    if not isinstance(users, list):
        return err(422, "validation_failed", "bad users")
    if not isinstance(payments, list) or not isinstance(requests_, list):
        return err(422, "validation_failed", "bad seeded lists")
    if not isinstance(auths_seed, list):
        return err(422, "validation_failed", "bad seeded authorizations")
    if not isinstance(ops, list):
        return err(422, "validation_failed", "bad operators")
    for u in users:
        if not isinstance(u, dict):
            return err(422, "validation_failed", "bad user")
        bal = u.get("balance")
        if isinstance(bal, bool) or not isinstance(bal, int):
            # fixture balances are ints; non-int is invalid fixture
            return err(422, "validation_failed", "bad balance")
        if bal < 0:
            return err(422, "validation_failed", "negative seeded balance")
    for p in payments:
        if not isinstance(p, dict):
            continue
        c = p.get("created_at")
        if c is None:
            continue
        d = _parse_instant(c)
        if d is None or d > _now():
            return err(422, "validation_failed", "bad seeded created_at")
    # pre-validate seeded open holds against balances (available is derived)
    _seed_bal = {}
    for u in users:
        if isinstance(u, dict):
            _seed_bal[str(u.get("id", ""))] = u.get("balance", 0)
    _seed_hold = {}
    for a in auths_seed:
        if not isinstance(a, dict):
            continue
        if a.get("status", "open") != "open":
            continue
        exp = _parse_ts(a.get("expires_at", ""))
        if exp is None:
            continue
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if exp <= _now():
            continue
        amt = a.get("amount", 0)
        if isinstance(amt, float) and float(amt).is_integer():
            amt = int(amt)
        cap = a.get("captured_amount", 0)
        if isinstance(cap, float) and float(cap).is_integer():
            cap = int(cap)
        if not isinstance(amt, int) or isinstance(amt, bool):
            continue
        if not isinstance(cap, int) or isinstance(cap, bool):
            cap = 0
        fuid = str(a.get("from_user_id", ""))
        _seed_hold[fuid] = _seed_hold.get(fuid, 0) + max(0, amt - cap)
    for fuid, held in _seed_hold.items():
        if held > _seed_bal.get(fuid, 0):
            return err(422, "validation_failed", "seeded holds exceed balance")
    with _lock:
        # build fresh
        n_users_by_id = {}
        n_by_email = {}
        n_by_handle = {}
        for u in users:
            uid = str(u.get("id", ""))
            email = u.get("email", "")
            handle = u.get("handle", "")
            pw = u.get("password", "correct horse")
            dn = u.get("display_name", handle)
            bal = u.get("balance", 0)
            if not uid or not isinstance(email, str) or not isinstance(handle, str):
                return err(422, "validation_failed", "bad user fields")
            n_users_by_id[uid] = {
                "id": uid, "email": email,
                "password_hash": hash_password(str(pw)) if isinstance(pw, str) else hash_password("x"),
                "display_name": str(dn), "handle": handle, "balance": bal,
            }
            n_by_email[email] = uid
            n_by_handle[handle] = uid
        _state["users_by_id"] = n_users_by_id
        _state["users_by_email"] = n_by_email
        _state["users_by_handle"] = n_by_handle
        _state["tokens"] = {}
        _state["payments"] = {}
        _state["requests"] = {}
        _state["splits"] = {}
        _state["settlements"] = {}
        _state["authorizations"] = {}
        _state["authorization_ttl_seconds"] = ttl
        _state["openings"] = {}
        _state["snapshots"] = {}
        _state["correction_batches"] = {}
        _state["idempotency"] = {}
        _state["currency"] = currency
        _state["minor_units"] = minor_units
        _state["settlement_operator_ids"] = [str(x) for x in ops if isinstance(x, str)]
        _state["seq"] = 0
        ts = now_iso()
        seed_net = {}
        for p in payments:
            if not isinstance(p, dict):
                continue
            pid = str(p.get("id", ""))
            if not pid:
                _state["seq"] += 1
                pid = f"p_{_state['seq']}"
            fuid = str(p.get("from_user_id", ""))
            tuid = str(p.get("to_user_id", ""))
            fu = n_users_by_id.get(fuid)
            tu = n_users_by_id.get(tuid)
            if not fu or not tu:
                continue
            amt = p.get("amount", 0)
            if isinstance(amt, float) and float(amt).is_integer():
                amt = int(amt)
            note = p.get("note", "")
            if not isinstance(note, str):
                note = ""
            vis = p.get("visibility", "public")
            if vis not in ("public", "private"):
                vis = "public"
            created = p.get("created_at", ts)
            _state["seq"] += 1
            _state["payments"][pid] = {
                "payment_id": pid, "from_user_id": fuid, "from_handle": fu["handle"],
                "to_user_id": tuid, "to_handle": tu["handle"],
                "amount": amt, "currency": currency, "note": note, "visibility": vis,
                "request_id": p.get("request_id"), "settlement_id": p.get("settlement_id"),
                "authorization_id": p.get("authorization_id"),
                "refund_of": None,
                "revisions": [{"revision": 1, "amount": amt,
                               "effective_at": created, "recorded_at": created,
                               "reason": ""}],
                "created_at": created, "_seq": _state["seq"],
            }
            if _is_int(amt):
                seed_net[fuid] = seed_net.get(fuid, 0) - amt
                seed_net[tuid] = seed_net.get(tuid, 0) + amt
        for uid, u in n_users_by_id.items():
            _state["openings"][uid] = u["balance"] - seed_net.get(uid, 0)
        for r in requests_:
            if not isinstance(r, dict):
                continue
            rid = str(r.get("id", r.get("request_id", "")))
            if not rid:
                _state["seq"] += 1
                rid = f"rq_{_state['seq']}"
            rqer = str(r.get("requester_id", ""))
            payer = str(r.get("payer_id", ""))
            ru = n_users_by_id.get(rqer)
            pu = n_users_by_id.get(payer)
            if not ru or not pu:
                continue
            amt = r.get("amount", 0)
            if isinstance(amt, float) and float(amt).is_integer():
                amt = int(amt)
            note = r.get("note", "")
            if not isinstance(note, str):
                note = ""
            status = r.get("status", "pending")
            if status not in ("pending", "paid", "declined", "cancelled"):
                status = "pending"
            _state["seq"] += 1
            _state["requests"][rid] = {
                "request_id": rid, "requester_id": rqer, "requester_handle": ru["handle"],
                "payer_id": payer, "payer_handle": pu["handle"],
                "amount": amt, "currency": currency, "note": note,
                "status": status, "payment_id": r.get("payment_id"),
                "created_at": r.get("created_at", ts), "_seq": _state["seq"],
            }
        for a in auths_seed:
            if not isinstance(a, dict):
                continue
            aid = str(a.get("id", a.get("authorization_id", "")))
            if not aid:
                _state["seq"] += 1
                aid = f"a_{_state['seq']}"
            fuid = str(a.get("from_user_id", ""))
            tuid = str(a.get("to_user_id", ""))
            fu = n_users_by_id.get(fuid)
            tu = n_users_by_id.get(tuid)
            if not fu or not tu:
                continue
            amt = a.get("amount", 0)
            if isinstance(amt, float) and float(amt).is_integer():
                amt = int(amt)
            if not isinstance(amt, int) or isinstance(amt, bool):
                continue
            cap = a.get("captured_amount", 0)
            if isinstance(cap, float) and float(cap).is_integer():
                cap = int(cap)
            if not isinstance(cap, int) or isinstance(cap, bool):
                cap = 0
            note = a.get("note", "")
            if not isinstance(note, str):
                note = ""
            vis = a.get("visibility", "public")
            if vis not in ("public", "private"):
                vis = "public"
            status = a.get("status", "open")
            if status not in ("open", "captured", "voided", "expired"):
                status = "open"
            exp = a.get("expires_at")
            if not isinstance(exp, str) or _parse_ts(exp) is None:
                exp = (_now() + timedelta(seconds=ttl)).isoformat()
            pids = a.get("payment_ids", [])
            if not isinstance(pids, list):
                pids = []
            pids = [str(x) for x in pids if isinstance(x, (str, int))]
            pid1 = a.get("payment_id")
            if pid1 is not None and not isinstance(pid1, str):
                pid1 = None
            if pid1 and pid1 not in pids:
                pids = pids + [pid1]
            if not pid1 and pids:
                pid1 = pids[-1]
            created_a = a.get("created_at", ts)
            closed_a = a.get("closed_at")
            if not isinstance(closed_a, str) or _parse_instant(closed_a) is None:
                if status == "open":
                    closed_a = None
                elif status == "expired":
                    closed_a = exp
                else:
                    closed_a = created_a
            _state["seq"] += 1
            _state["authorizations"][aid] = {
                "authorization_id": aid, "from_user_id": fuid, "from_handle": fu["handle"],
                "to_user_id": tuid, "to_handle": tu["handle"],
                "amount": amt, "captured_amount": cap, "currency": currency,
                "note": note, "visibility": vis, "status": status,
                "expires_at": exp, "closed_at": closed_a,
                "payment_id": pid1, "payment_ids": pids,
                "created_at": created_a, "_seq": _state["seq"],
            }
    return Response(status_code=204)


@app.post("/auth/signup")
async def signup(request: Request):
    body, e = await parse_obj(request)
    if e:
        return e
    if "email" not in body or "password" not in body or "display_name" not in body:
        return err(422, "validation_failed", "missing field")
    email, pw, dn = body["email"], body["password"], body["display_name"]
    if not isinstance(email, str) or not isinstance(pw, str) or not isinstance(dn, str):
        return err(400, "malformed_request", "wrong type")
    if not valid_email(email):
        return err(422, "validation_failed", "bad email")
    if len(pw) < 8:
        return err(422, "validation_failed", "bad password")
    with _lock:
        if email in _state["users_by_email"]:
            return err(409, "email_taken", "email taken")
        handle = derive_handle(email)
        if handle in _state["users_by_handle"]:
            return err(409, "handle_taken", "handle taken")
        uid = _unique_id("u", _state["users_by_id"])
        _state["users_by_id"][uid] = {
            "id": uid, "email": email, "password_hash": hash_password(pw),
            "display_name": dn, "handle": handle, "balance": 0,
        }
        _state["users_by_email"][email] = uid
        _state["users_by_handle"][handle] = uid
        _state["openings"][uid] = 0
        token = secrets.token_urlsafe(32)
        while token in _state["tokens"]:
            token = secrets.token_urlsafe(32)
        _state["tokens"][token] = uid
    return JSONResponse({"user_id": uid, "display_name": dn, "token": token}, status_code=201)


@app.post("/auth/login")
async def login(request: Request):
    body, e = await parse_obj(request)
    if e:
        return e
    if "email" not in body or "password" not in body:
        return err(422, "validation_failed", "missing field")
    email, pw = body["email"], body["password"]
    if not isinstance(email, str) or not isinstance(pw, str):
        return err(400, "malformed_request", "wrong type")
    with _lock:
        uid = _state["users_by_email"].get(email)
        if not uid:
            return err(401, "unauthenticated", "bad credentials")
        u = _state["users_by_id"][uid]
        if not verify_password(pw, u["password_hash"]):
            return err(401, "unauthenticated", "bad credentials")
        token = secrets.token_urlsafe(32)
        while token in _state["tokens"]:
            token = secrets.token_urlsafe(32)
        _state["tokens"][token] = uid
        dn = u["display_name"]
    return {"user_id": uid, "display_name": dn, "token": token}


@app.get("/me")
def me(request: Request):
    u = get_auth_user(request)
    if not u:
        return err(401, "unauthenticated", "unauthenticated")
    
    qp = dict(request.query_params)
    as_of_str = qp.get("as_of")
    known_at_str = qp.get("known_at")
    
    as_of = None
    if as_of_str is not None:
        as_of = _parse_instant(as_of_str)
        if as_of is None:
            return err(422, "validation_failed", "bad as_of")
    
    known_at = None
    if known_at_str is not None:
        known_at = _parse_instant(known_at_str)
        if known_at is None:
            return err(422, "validation_failed", "bad known_at")
    
    with _lock:
        if as_of is None:
            as_of = _now()
        if known_at is None:
            known_at = _now()
        
        uid = u["id"]
        total = _balance_at(uid, as_of, known_at)
        held = _held_at(uid, as_of)
        available = total - held
        
        resp = {
            "user_id": uid, "display_name": u["display_name"], "handle": u["handle"],
            "balance": total, "total": total,
            "available": available, "held": held,
            "currency": _state["currency"], "minor_units": _state["minor_units"],
        }
        if "as_of" in qp:
            resp["as_of"] = qp["as_of"]
        if "known_at" in qp:
            resp["known_at"] = qp["known_at"]
        return resp


def _require_idem(request, uid, body):
    key = get_idem_key(request)
    if key is None or key == "":
        return None, err(400, "missing_idempotency_key", "missing key")
    if len(key) > 255:
        return None, err(422, "validation_failed", "bad key")
    return key, None


@app.post("/payments")
async def create_payment(request: Request):
    body, e = await parse_obj(request)
    if e:
        return e
    u = get_auth_user(request)
    if not u:
        return err(401, "unauthenticated", "unauthenticated")
    uid = u["id"]
    path = request.url.path
    key, ke = _require_idem(request, uid, body)
    if ke:
        return ke
    with _lock:
        rec, same = idem_lookup(uid, key, "POST", path, body)
        if rec is not None:
            if same:
                return JSONResponse(rec["response"], status_code=200)
            return err(409, "idempotency_key_reuse", "key reuse")
        if "to_handle" not in body or "amount" not in body:
            return err(422, "validation_failed", "missing field")
        to_h = body["to_handle"]
        amt_raw = body["amount"]
        if not isinstance(to_h, str):
            return err(400, "malformed_request", "bad handle type")
        amt, ok = parse_amount(amt_raw)
        if not ok:
            return err(422, "validation_failed", "bad amount")
        note, ok = validate_note(body)
        if not ok:
            return err(422, "validation_failed", "bad note")
        vis, ok = validate_visibility(body)
        if not ok:
            return err(422, "validation_failed", "bad visibility")
        if to_h == u["handle"]:
            return err(422, "self_payment", "self payment")
        target_uid = _state["users_by_handle"].get(to_h)
        if target_uid is None:
            return err(404, "not_found", "unknown handle")
        if available_for(u) < amt:
            return err(409, "insufficient_funds", "insufficient funds")
        nb_from = u["balance"] - amt
        nb_to = _state["users_by_id"][target_uid]["balance"] + amt
        if abs(nb_from) > 2**53 or abs(nb_to) > 2**53:
            return err(422, "validation_failed", "range")
        pid = _unique_id("p", _state["payments"])
        ts = now_iso()
        _state["seq"] += 1
        seq = _state["seq"]
        p = {
            "payment_id": pid, "from_user_id": uid, "from_handle": u["handle"],
            "to_user_id": target_uid, "to_handle": to_h,
            "amount": amt, "currency": _state["currency"], "note": note, "visibility": vis,
            "request_id": None, "settlement_id": None, "authorization_id": None,
            "refund_of": None,
            "revisions": [{"revision": 1, "amount": amt,
                           "effective_at": ts, "recorded_at": ts, "reason": ""}],
            "created_at": ts, "_seq": seq,
        }
        u["balance"] = nb_from
        _state["users_by_id"][target_uid]["balance"] = nb_to
        _state["payments"][pid] = p
        resp = payment_view(p)
        idem_store(uid, key, "POST", path, body, resp)
    return JSONResponse(resp, status_code=201)


def _statement_data(uid, from_dt, to_dt, K):
    """Full-window statement: (opening, closing, entries) regardless of paging."""
    opening_net = _state["openings"].get(uid, 0)
    sel = []
    for p in _state["payments"].values():
        if p.get("from_user_id") != uid and p.get("to_user_id") != uid:
            continue
        r = _selected_rev(p, K)
        if r is None:
            continue
        eff = _parse_instant(r.get("effective_at"))
        if eff is None:
            continue
        sel.append((eff, p.get("payment_id", ""), p, r))
    if from_dt is None:
        opening = opening_net
    else:
        opening = opening_net + sum(_signed(uid, p, r.get("amount", 0))
                                    for (eff, _pid, p, r) in sel if eff < from_dt)
    closing = opening_net + sum(_signed(uid, p, r.get("amount", 0))
                                for (eff, _pid, p, r) in sel if eff < to_dt)
    win = [(eff, pid, p, r) for (eff, pid, p, r) in sel
           if (from_dt is None or eff >= from_dt) and eff < to_dt]
    win.sort(key=lambda t: (t[0], t[1]))
    entries = []
    run = opening
    for (eff, pid, p, r) in win:
        amt = r.get("amount", 0)
        d = _signed(uid, p, amt)
        run += d
        pay = payment_view(p)
        pay["amount"] = amt
        entries.append({"payment": pay, "delta": d, "balance_after": run,
                        "revision": r.get("revision", 1),
                        "effective_at": r.get("effective_at"),
                        "recorded_at": r.get("recorded_at")})
    return opening, closing, entries


def _page_entries(entries, limit, offset):
    page = entries[offset:offset + limit]
    return page, (offset + limit) < len(entries)


@app.get("/statement")
def get_statement(request: Request):
    qp = dict(request.query_params)
    limit, offset, e = parse_limit_offset(qp)
    if e:
        return e
    snap_tok = qp.get("snapshot")
    if snap_tok is not None:
        if "from" in qp or "to" in qp or "known_at" in qp:
            return err(422, "validation_failed", "snapshot is exclusive")
        u = get_auth_user(request)
        if not u:
            return err(401, "unauthenticated", "unauthenticated")
        with _lock:
            snap = _state["snapshots"].get(snap_tok)
            if snap is None or snap.get("user_id") != u["id"]:
                return err(404, "not_found", "unknown snapshot")
            page, has_more = _page_entries(snap["entries"], limit, offset)
            return {"opening_balance": snap["opening"], "entries": copy.deepcopy(page),
                    "closing_balance": snap["closing"], "has_more": has_more,
                    "snapshot": snap_tok}
    u = get_auth_user(request)
    if not u:
        return err(401, "unauthenticated", "unauthenticated")
    from_raw = qp.get("from")
    to_raw = qp.get("to")
    known_raw = qp.get("known_at")
    if from_raw is not None:
        from_dt = _parse_instant(from_raw)
        if from_dt is None:
            return err(422, "validation_failed", "bad from")
    else:
        from_dt = None
    if known_raw is not None:
        K = _parse_instant(known_raw)
        if K is None:
            return err(422, "validation_failed", "bad known_at")
    else:
        K = None
    with _lock:
        now = _now()
        if to_raw is not None:
            to_dt = _parse_instant(to_raw)
            if to_dt is None:
                return err(422, "validation_failed", "bad to")
        else:
            to_dt = now
        if K is None:
            K = now
        opening, closing, entries = _statement_data(u["id"], from_dt, to_dt, K)
        tok = secrets.token_urlsafe(24)
        while tok in _state["snapshots"]:
            tok = secrets.token_urlsafe(24)
        _state["snapshots"][tok] = {
            "user_id": u["id"],
            "from": from_raw,
            "to": to_dt.isoformat(),
            "known_at": (known_raw if known_raw is not None else now.isoformat()),
            "opening": opening, "closing": closing,
            "entries": copy.deepcopy(entries),
        }
        page, has_more = _page_entries(entries, limit, offset)
        resp = {"opening_balance": opening, "entries": page,
                "closing_balance": closing, "has_more": has_more,
                "snapshot": tok}
        if known_raw is not None:
            resp["known_at"] = known_raw
        return resp


@app.post("/requests")
async def create_request(request: Request):
    body, e = await parse_obj(request)
    if e:
        return e
    u = get_auth_user(request)
    if not u:
        return err(401, "unauthenticated", "unauthenticated")
    uid = u["id"]
    path = request.url.path
    key, ke = _require_idem(request, uid, body)
    if ke:
        return ke
    with _lock:
        rec, same = idem_lookup(uid, key, "POST", path, body)
        if rec is not None:
            if same:
                return JSONResponse(rec["response"], status_code=200)
            return err(409, "idempotency_key_reuse", "key reuse")
        if "payer_handle" not in body or "amount" not in body:
            return err(422, "validation_failed", "missing field")
        ph = body["payer_handle"]
        amt_raw = body["amount"]
        if not isinstance(ph, str):
            return err(400, "malformed_request", "bad handle type")
        amt, ok = parse_amount(amt_raw)
        if not ok:
            return err(422, "validation_failed", "bad amount")
        note, ok = validate_note(body)
        if not ok:
            return err(422, "validation_failed", "bad note")
        if ph == u["handle"]:
            return err(422, "self_request", "self request")
        payer_uid = _state["users_by_handle"].get(ph)
        if payer_uid is None:
            return err(404, "not_found", "unknown handle")
        rid = _unique_id("rq", _state["requests"])
        ts = now_iso()
        _state["seq"] += 1
        r = {
            "request_id": rid, "requester_id": uid, "requester_handle": u["handle"],
            "payer_id": payer_uid, "payer_handle": ph,
            "amount": amt, "currency": _state["currency"], "note": note,
            "status": "pending", "payment_id": None, "created_at": ts, "_seq": _state["seq"],
        }
        _state["requests"][rid] = r
        resp = request_view(r)
        idem_store(uid, key, "POST", path, body, resp)
    return JSONResponse(resp, status_code=201)


@app.post("/requests/{rid}/pay")
async def pay_request(rid: str, request: Request):
    body, e = await parse_obj(request)
    if e:
        return e
    u = get_auth_user(request)
    if not u:
        return err(401, "unauthenticated", "unauthenticated")
    uid = u["id"]
    path = request.url.path
    key, ke = _require_idem(request, uid, body)
    if ke:
        return ke
    with _lock:
        rec, same = idem_lookup(uid, key, "POST", path, body)
        if rec is not None:
            if same:
                return JSONResponse(rec["response"], status_code=200)
            return err(409, "idempotency_key_reuse", "key reuse")
        r = _state["requests"].get(rid)
        if r is None:
            # hide existence from non-parties? spec: unknown request 404.
            # also non-party gets 403/404; check parties first for info leak?
            return err(404, "not_found", "unknown request")
        if uid != r["payer_id"] and uid != r["requester_id"]:
            # not involved at all -> 403 or 404 allowed
            return err(403, "forbidden", "forbidden")
        if uid != r["payer_id"]:
            return err(403, "forbidden", "forbidden")
        vis, ok = validate_visibility(body)
        if not ok:
            return err(422, "validation_failed", "bad visibility")
        if r["status"] != "pending":
            return err(409, "request_not_pending", "not pending")
        amt = r["amount"]
        payer = _state["users_by_id"][r["payer_id"]]
        reqer = _state["users_by_id"][r["requester_id"]]
        if available_for(payer) < amt:
            return err(409, "insufficient_funds", "insufficient funds")
        nb_p = payer["balance"] - amt
        nb_r = reqer["balance"] + amt
        if abs(nb_p) > 2**53 or abs(nb_r) > 2**53:
            return err(422, "validation_failed", "range")
        pid = _unique_id("p", _state["payments"])
        ts = now_iso()
        _state["seq"] += 1
        p = {
            "payment_id": pid, "from_user_id": payer["id"], "from_handle": payer["handle"],
            "to_user_id": reqer["id"], "to_handle": reqer["handle"],
            "amount": amt, "currency": _state["currency"], "note": r["note"], "visibility": vis,
            "request_id": rid, "settlement_id": None, "authorization_id": None,
            "refund_of": None,
            "revisions": [{"revision": 1, "amount": amt,
                           "effective_at": ts, "recorded_at": ts, "reason": ""}],
            "created_at": ts, "_seq": _state["seq"],
        }
        payer["balance"] = nb_p
        reqer["balance"] = nb_r
        _state["payments"][pid] = p
        r["status"] = "paid"
        r["payment_id"] = pid
        resp = payment_view(p)
        idem_store(uid, key, "POST", path, body, resp)
    return JSONResponse(resp, status_code=201)


@app.post("/requests/{rid}/decline")
async def decline_request(rid: str, request: Request):
    u = get_auth_user(request)
    if not u:
        return err(401, "unauthenticated", "unauthenticated")
    uid = u["id"]
    with _lock:
        r = _state["requests"].get(rid)
        if r is None:
            return err(404, "not_found", "unknown request")
        if uid != r["payer_id"] and uid != r["requester_id"]:
            return err(403, "forbidden", "forbidden")
        if uid != r["payer_id"]:
            return err(403, "forbidden", "forbidden")
        if r["status"] == "declined":
            return request_view(r)
        if r["status"] != "pending":
            return err(409, "request_not_pending", "not pending")
        r["status"] = "declined"
        return request_view(r)


@app.post("/requests/{rid}/cancel")
async def cancel_request(rid: str, request: Request):
    u = get_auth_user(request)
    if not u:
        return err(401, "unauthenticated", "unauthenticated")
    uid = u["id"]
    with _lock:
        r = _state["requests"].get(rid)
        if r is None:
            return err(404, "not_found", "unknown request")
        if uid != r["payer_id"] and uid != r["requester_id"]:
            return err(403, "forbidden", "forbidden")
        if uid != r["requester_id"]:
            return err(403, "forbidden", "forbidden")
        if r["status"] == "cancelled":
            return request_view(r)
        if r["status"] != "pending":
            return err(409, "request_not_pending", "not pending")
        r["status"] = "cancelled"
        return request_view(r)


@app.get("/requests")
def list_requests(request: Request):
    accepts = request.headers.get("accept", "")
    if "text/html" in accepts:
        from .ui import page_requests
        return HTMLResponse(page_requests())
    u = get_auth_user(request)
    if not u:
        return err(401, "unauthenticated", "unauthenticated")
    qp = dict(request.query_params)
    direction = qp.get("direction")
    status = qp.get("status")
    if direction is not None and direction not in ("incoming", "outgoing"):
        return err(422, "validation_failed", "bad direction")
    if status is not None and status not in ("pending", "paid", "declined", "cancelled"):
        return err(422, "validation_failed", "bad status")
    limit, offset, e = parse_limit_offset(qp)
    if e:
        return e
    # strict plain-digits already enforced; also reject limit/offset with weird types handled above
    with _lock:
        items = [r for r in _state["requests"].values()
                 if r["requester_id"] == u["id"] or r["payer_id"] == u["id"]]
        if direction == "incoming":
            items = [r for r in items if r["payer_id"] == u["id"]]
        elif direction == "outgoing":
            items = [r for r in items if r["requester_id"] == u["id"]]
        if status is not None:
            items = [r for r in items if r["status"] == status]
        items = _newest_first(items)
        total = len(items)
        page = items[offset:offset + limit]
        has_more = (offset + limit) < total
        out = [request_view(r) for r in page]
    return {"requests": out, "has_more": has_more}


def equal_split(amount, n):
    base = amount // n
    rem = amount - base * n
    return [base + (1 if i < rem else 0) for i in range(n)]


@app.post("/splits")
async def create_split(request: Request):
    body, e = await parse_obj(request)
    if e:
        return e
    u = get_auth_user(request)
    if not u:
        return err(401, "unauthenticated", "unauthenticated")
    uid = u["id"]
    path = request.url.path
    key, ke = _require_idem(request, uid, body)
    if ke:
        return ke
    with _lock:
        rec, same = idem_lookup(uid, key, "POST", path, body)
        if rec is not None:
            if same:
                return JSONResponse(rec["response"], status_code=200)
            return err(409, "idempotency_key_reuse", "key reuse")
        if "amount" not in body or "participant_handles" not in body:
            return err(422, "validation_failed", "missing field")
        amt_raw = body["amount"]
        ph = body["participant_handles"]
        amt, ok = parse_amount(amt_raw)
        if not ok:
            return err(422, "validation_failed", "bad amount")
        note, ok = validate_note(body)
        if not ok:
            return err(422, "validation_failed", "bad note")
        if not isinstance(ph, list):
            return err(400, "malformed_request", "bad participants type")
        if len(ph) == 0:
            return err(422, "validation_failed", "empty participants")
        for h in ph:
            if not isinstance(h, str):
                return err(400, "malformed_request", "bad handle type")
        if len(set(ph)) != len(ph):
            return err(422, "validation_failed", "duplicate handle")
        # unknown handle check (before balance, no balance check at all)
        for h in ph:
            if h not in _state["users_by_handle"]:
                return err(404, "not_found", "unknown handle")
        # 1000 participants with unknown already 404; if all known but huge, still process?
        # guard: if huge and all known (unlikely), allow but cap work
        n = len(ph)
        shares = equal_split(amt, n)
        sid = _unique_id("sp", _state["splits"])
        ts = now_iso()
        _state["seq"] += 1
        req_objs = []
        for h, share in zip(ph, shares):
            if h == u["handle"]:
                continue
            payer_uid = _state["users_by_handle"][h]
            _state["seq"] += 1
            rid = f"rq_{_state['seq']}"
            while rid in _state["requests"]:
                _state["seq"] += 1
                rid = f"rq_{_state['seq']}"
            r = {
                "request_id": rid, "requester_id": uid, "requester_handle": u["handle"],
                "payer_id": payer_uid, "payer_handle": h,
                "amount": share, "currency": _state["currency"], "note": note,
                "status": "pending", "payment_id": None, "created_at": ts, "_seq": _state["seq"],
            }
            _state["requests"][rid] = r
            req_objs.append(request_view(r))
        share_list = [{"handle": h, "amount": s} for h, s in zip(ph, shares)]
        resp = {
            "split_id": sid, "amount": amt, "currency": _state["currency"], "note": note,
            "shares": share_list, "requests": req_objs, "created_at": ts,
        }
        _state["splits"][sid] = {
            "split_id": sid, "amount": amt, "currency": _state["currency"], "note": note,
            "participant_handles": list(ph), "shares": share_list,
            "request_ids": [r["request_id"] for r in req_objs],
            "created_at": ts, "_seq": _state["seq"],
        }
        idem_store(uid, key, "POST", path, body, resp)
    return JSONResponse(resp, status_code=201)


@app.get("/activity")
def activity(request: Request):
    u = get_auth_user(request)
    if not u:
        return err(401, "unauthenticated", "unauthenticated")
    qp = dict(request.query_params)
    limit, offset, e = parse_limit_offset(qp)
    if e:
        return e
    with _lock:
        items = [p for p in _state["payments"].values()
                 if p["visibility"] == "public" or p["from_user_id"] == u["id"] or p["to_user_id"] == u["id"]]
        items = _newest_first(items)
        total = len(items)
        page = items[offset:offset + limit]
        has_more = (offset + limit) < total
        out = [payment_view(p) for p in page]
    return {"payments": out, "has_more": has_more}


@app.get("/_test/export")
def export_state():
    with _lock:
        snap = {
            "currency": _state["currency"],
            "minor_units": _state["minor_units"],
            "users": [
                {"id": v["id"], "email": v["email"], "password_hash": v["password_hash"],
                 "display_name": v["display_name"], "handle": v["handle"], "balance": v["balance"]}
                for v in _state["users_by_id"].values()
            ],
            "tokens": dict(_state["tokens"]),
            "payments": copy.deepcopy(list(_state["payments"].values())),
            "requests": copy.deepcopy(list(_state["requests"].values())),
            "splits": copy.deepcopy(_state["splits"]),
            "settlements": copy.deepcopy(_state["settlements"]),
            "idempotency": copy.deepcopy([
                {"uid": k[0], "key": k[1], "method": k[2], "path": k[3],
                 "body": v["body"], "response": v["response"]}
                for k, v in _state["idempotency"].items()
            ]),
            "settlement_operator_ids": list(_state["settlement_operator_ids"]),
            "authorization_ttl_seconds": int(_state["authorization_ttl_seconds"]),
            "authorizations": copy.deepcopy(list(_state["authorizations"].values())),
            "openings": dict(_state["openings"]),
            "snapshots": copy.deepcopy(_state["snapshots"]),
            "correction_batches": copy.deepcopy(_state["correction_batches"]),
            "seq": _state["seq"],
        }
    return {"track": "pocketful", "format_version": 1, "state": snap}


def _validate_revision_list(revs, created_at):
    """Validate a stored revision history. Returns deep-copied list or None."""
    if not isinstance(revs, list) or not revs:
        return None
    out = []
    last_rec = None
    for i, r in enumerate(revs, start=1):
        if not isinstance(r, dict):
            return None
        if r.get("revision") != i:
            return None
        amt = r.get("amount")
        if not _is_int(amt) or not (0 <= amt <= 1000000000):
            return None
        eff = _parse_instant(r.get("effective_at"))
        rec = _parse_instant(r.get("recorded_at"))
        if eff is None or rec is None:
            return None
        if not isinstance(r.get("reason"), str):
            return None
        if last_rec is not None and rec <= last_rec:
            return None
        last_rec = rec
        out.append(copy.deepcopy(r))
    return out


def _synthesize_revisions(p):
    amt = p.get("amount", 0)
    if isinstance(amt, float) and float(amt).is_integer():
        amt = int(amt)
    if not _is_int(amt):
        return None
    created = p.get("created_at")
    if _parse_instant(created) is None:
        return None
    return [{"revision": 1, "amount": amt,
             "effective_at": created, "recorded_at": created, "reason": ""}]


def _validate_import_state(st):
    """Validate an import `state` object and build a fresh, fully-owned
    replacement state. Returns the new state dict, or None if invalid.
    Everything is deep-copied so the live state never aliases the request
    body: repeating an import restores the same snapshot without loss or
    duplication, and later writes cannot mutate a previously sent export.
    Stage-1/2 exports omit revision history, openings, snapshots and close
    times; those are synthesized or defaulted."""
    if not isinstance(st, dict):
        return None
    if not isinstance(st.get("users"), list):
        return None
    currency = st.get("currency")
    if not isinstance(currency, str) or not currency:
        return None
    minor_units = st.get("minor_units")
    if minor_units not in (0, 2, 3):
        return None
    n_users_by_id = {}
    n_by_email = {}
    n_by_handle = {}
    for u in st["users"]:
        if not isinstance(u, dict):
            return None
        uid = u.get("id")
        email = u.get("email")
        handle = u.get("handle")
        if not isinstance(uid, str) or not uid:
            return None
        if not isinstance(email, str) or not isinstance(handle, str):
            return None
        if not isinstance(u.get("password_hash", ""), str):
            return None
        if not isinstance(u.get("display_name", handle), str):
            return None
        bal = u.get("balance", 0)
        if not _is_int(bal):
            return None
        n_users_by_id[uid] = {
            "id": uid, "email": email,
            "password_hash": str(u.get("password_hash", "")),
            "display_name": str(u.get("display_name", handle)),
            "handle": handle, "balance": bal,
        }
        n_by_email[email] = uid
        n_by_handle[handle] = uid
    raw_payments = st.get("payments", [])
    if not isinstance(raw_payments, list):
        return None
    n_payments = {}
    for p in raw_payments:
        if not isinstance(p, dict):
            return None
        pid = p.get("payment_id")
        if not isinstance(pid, str) or not pid:
            return None
        for k in ("from_user_id", "to_user_id", "from_handle", "to_handle",
                  "currency", "note", "visibility", "created_at"):
            if k not in p:
                return None
        if not isinstance(p["from_user_id"], str) or not isinstance(p["to_user_id"], str):
            return None
        if not isinstance(p["from_handle"], str) or not isinstance(p["to_handle"], str):
            return None
        if not _is_int(p["amount"]):
            return None
        if not isinstance(p["currency"], str) or not isinstance(p["note"], str):
            return None
        if p["visibility"] not in ("public", "private"):
            return None
        if not isinstance(p["created_at"], str):
            return None
        for k in ("request_id", "settlement_id", "authorization_id"):
            v = p.get(k)
            if v is not None and not isinstance(v, str):
                return None
        if p.get("refund_of") is not None and not isinstance(p.get("refund_of"), str):
            return None
        seq = p.get("_seq", 0)
        if not _is_int(seq):
            return None
        if "revisions" in p and p["revisions"] is not None:
            revs = _validate_revision_list(p["revisions"], p.get("created_at"))
            if revs is None or revs[0]["amount"] != p["amount"]:
                return None
            for r in revs:
                cb = r.get("correction_batch_id")
                if cb is not None and not isinstance(cb, str):
                    return None
        else:
            # stage-1/2 exports carry no revision history: revision 1 is the
            # payment as originally paid.
            revs = _synthesize_revisions(p)
            if revs is None:
                return None
        pp = copy.deepcopy(p)
        pp["revisions"] = revs
        n_payments[str(pid)] = pp
    raw_requests = st.get("requests", [])
    if not isinstance(raw_requests, list):
        return None
    n_requests = {}
    for r in raw_requests:
        if not isinstance(r, dict):
            return None
        rid = r.get("request_id")
        if not isinstance(rid, str) or not rid:
            return None
        for k in ("requester_id", "requester_handle", "payer_id", "payer_handle",
                  "currency", "note", "status", "created_at"):
            if k not in r:
                return None
        if not isinstance(r["requester_id"], str) or not isinstance(r["payer_id"], str):
            return None
        if not isinstance(r["requester_handle"], str) or not isinstance(r["payer_handle"], str):
            return None
        if not _is_int(r["amount"]):
            return None
        if not isinstance(r["currency"], str) or not isinstance(r["note"], str):
            return None
        if r["status"] not in ("pending", "paid", "declined", "cancelled"):
            return None
        if not isinstance(r["created_at"], str):
            return None
        payid = r.get("payment_id")
        if payid is not None and not isinstance(payid, str):
            return None
        seq = r.get("_seq", 0)
        if not _is_int(seq):
            return None
        n_requests[str(rid)] = copy.deepcopy(r)
    raw_auths = st.get("authorizations", [])
    if not isinstance(raw_auths, list):
        return None
    n_auths = {}
    for a in raw_auths:
        if not isinstance(a, dict):
            return None
        aid = a.get("authorization_id")
        if not isinstance(aid, str) or not aid:
            return None
        for k in ("from_user_id", "to_user_id", "from_handle", "to_handle",
                  "currency", "note", "visibility", "status",
                  "expires_at", "created_at"):
            if k not in a:
                return None
        if not isinstance(a["from_user_id"], str) or not isinstance(a["to_user_id"], str):
            return None
        if not isinstance(a["from_handle"], str) or not isinstance(a["to_handle"], str):
            return None
        if not _is_int(a["amount"]):
            return None
        cap = a.get("captured_amount", 0)
        if not _is_int(cap) or cap < 0:
            return None
        if not isinstance(a["currency"], str) or not isinstance(a["note"], str):
            return None
        if a["visibility"] not in ("public", "private"):
            return None
        if a["status"] not in ("open", "captured", "voided", "expired"):
            return None
        if not isinstance(a["expires_at"], str) or _parse_ts(a["expires_at"]) is None:
            return None
        if not isinstance(a["created_at"], str):
            return None
        pid1 = a.get("payment_id")
        if pid1 is not None and not isinstance(pid1, str):
            return None
        pids = a.get("payment_ids", [])
        if not isinstance(pids, list) or any(not isinstance(x, str) for x in pids):
            return None
        seq = a.get("_seq", 0)
        if not _is_int(seq):
            return None
        ca = a.get("closed_at")
        if ca is not None and (not isinstance(ca, str) or _parse_instant(ca) is None):
            return None
        aa = copy.deepcopy(a)
        if ca is None:
            # legacy records without a close time: seeded/open semantics.
            if a["status"] == "open":
                aa["closed_at"] = None
            elif a["status"] == "expired":
                aa["closed_at"] = a["expires_at"]
            else:
                aa["closed_at"] = a["created_at"]
        n_auths[str(aid)] = aa
    n_ttl = st.get("authorization_ttl_seconds", 600)
    if isinstance(n_ttl, bool):
        return None
    if isinstance(n_ttl, float) and float(n_ttl).is_integer():
        n_ttl = int(n_ttl)
    if not isinstance(n_ttl, int) or n_ttl < 1:
        return None
    raw_tokens = st.get("tokens", {})
    if not isinstance(raw_tokens, dict):
        return None
    n_tokens = {}
    for k, v in raw_tokens.items():
        if not isinstance(k, str) or not isinstance(v, str):
            return None
        n_tokens[k] = v
    raw_idem = st.get("idempotency", [])
    if not isinstance(raw_idem, list):
        return None
    n_idem = {}
    for rec in raw_idem:
        if not isinstance(rec, dict):
            return None
        for k in ("uid", "key", "method", "path"):
            if not isinstance(rec.get(k), str):
                return None
        kk = (rec["uid"], rec["key"], rec["method"], rec["path"])
        n_idem[kk] = {"body": copy.deepcopy(rec.get("body")),
                      "response": copy.deepcopy(rec.get("response"))}
    raw_splits = st.get("splits", {})
    if not isinstance(raw_splits, dict):
        return None
    raw_settlements = st.get("settlements", {})
    if not isinstance(raw_settlements, dict):
        return None
    raw_ops = st.get("settlement_operator_ids", [])
    if not isinstance(raw_ops, list) or any(not isinstance(x, str) for x in raw_ops):
        return None
    raw_open = st.get("openings", {})
    if not isinstance(raw_open, dict):
        return None
    n_open = {}
    for k, v in raw_open.items():
        if not isinstance(k, str) or not _is_int(v):
            return None
        n_open[k] = v
    for uid, u in n_users_by_id.items():
        if uid not in n_open:
            # legacy exports carry no openings: opening is the balance before
            # any stored movement, i.e. balance minus the net latest effect.
            net = 0
            for p in n_payments.values():
                if p.get("from_user_id") != uid and p.get("to_user_id") != uid:
                    continue
                amt = p["revisions"][-1]["amount"]
                net += amt if p.get("to_user_id") == uid else -amt
            n_open[uid] = u["balance"] - net
    raw_snaps = st.get("snapshots", {})
    if not isinstance(raw_snaps, dict):
        return None
    n_snaps = {}
    for tok, s in raw_snaps.items():
        if not isinstance(tok, str) or not isinstance(s, dict):
            return None
        # Accept both export format (uid, from, to, known_at, opening_balance, closing_balance, entries, created_at)
        # and legacy format (user_id, to, known_at, opening, closing, entries)
        if "uid" in s:
            uid_val = s.get("uid")
            from_val = s.get("from")
            to_val = s.get("to")
            known_at_val = s.get("known_at")
            opening_val = s.get("opening_balance")
            closing_val = s.get("closing_balance")
            entries_val = s.get("entries")
        elif "user_id" in s:
            uid_val = s.get("user_id")
            from_val = s.get("from")
            to_val = s.get("to")
            known_at_val = s.get("known_at")
            opening_val = s.get("opening")
            closing_val = s.get("closing")
            entries_val = s.get("entries")
        else:
            return None
        if not isinstance(uid_val, str):
            return None
        if from_val is not None and not isinstance(from_val, str):
            return None
        if to_val is not None and _parse_instant(to_val) is None:
            return None
        if known_at_val is not None and _parse_instant(known_at_val) is None:
            return None
        if not _is_int(opening_val) or not _is_int(closing_val):
            return None
        if not isinstance(entries_val, list):
            return None
        n_snaps[tok] = {
            "uid": uid_val,
            "from": from_val,
            "to": to_val,
            "known_at": known_at_val,
            "opening_balance": opening_val,
            "closing_balance": closing_val,
            "entries": copy.deepcopy(entries_val),
            "created_at": s.get("created_at", now_iso()),
        }
    raw_batches = st.get("correction_batches", {})
    if not isinstance(raw_batches, dict):
        return None
    n_batches = {}
    for bid, b in raw_batches.items():
        if not isinstance(bid, str) or not isinstance(b, dict):
            return None
        if b.get("correction_batch_id", bid) != bid:
            return None
        if _parse_instant(b.get("recorded_at")) is None:
            return None
        if not isinstance(b.get("revisions"), list):
            return None
        n_batches[bid] = copy.deepcopy(b)
    seq = st.get("seq", 0)
    if not _is_int(seq):
        return None
    return {
        "users_by_id": n_users_by_id,
        "users_by_email": n_by_email,
        "users_by_handle": n_by_handle,
        "tokens": n_tokens,
        "payments": n_payments,
        "requests": n_requests,
        "splits": copy.deepcopy(raw_splits),
        "settlements": copy.deepcopy(raw_settlements),
        "authorizations": n_auths,
        "authorization_ttl_seconds": n_ttl,
        "openings": n_open,
        "snapshots": n_snaps,
        "correction_batches": n_batches,
        "idempotency": n_idem,
        "currency": currency,
        "minor_units": minor_units,
        "settlement_operator_ids": list(raw_ops),
        "seq": seq,
    }


@app.post("/_test/import")
async def import_state(request: Request):
    body, e = await parse_obj(request)
    if e:
        return e
    if body.get("track") != "pocketful" or body.get("format_version") != 1 or not isinstance(body.get("state"), dict):
        return err(422, "validation_failed", "bad import")
    try:
        nxt = _validate_import_state(body["state"])
    except Exception:
        nxt = None
    if nxt is None:
        return err(422, "validation_failed", "bad state")
    with _lock:
        _state["users_by_id"] = nxt["users_by_id"]
        _state["users_by_email"] = nxt["users_by_email"]
        _state["users_by_handle"] = nxt["users_by_handle"]
        _state["tokens"] = nxt["tokens"]
        _state["payments"] = nxt["payments"]
        _state["requests"] = nxt["requests"]
        _state["splits"] = nxt["splits"]
        _state["settlements"] = nxt["settlements"]
        _state["authorizations"] = nxt["authorizations"]
        _state["authorization_ttl_seconds"] = nxt["authorization_ttl_seconds"]
        _state["openings"] = nxt["openings"]
        _state["snapshots"] = nxt["snapshots"]
        _state["correction_batches"] = nxt["correction_batches"]
        _state["idempotency"] = nxt["idempotency"]
        _state["currency"] = nxt["currency"]
        _state["minor_units"] = nxt["minor_units"]
        _state["settlement_operator_ids"] = nxt["settlement_operator_ids"]
        _state["seq"] = nxt["seq"]
    return Response(status_code=204)


@app.post("/settlements")
async def create_settlement(request: Request):
    body, e = await parse_obj(request)
    if e:
        return e
    u = get_auth_user(request)
    if not u:
        return err(401, "unauthenticated", "unauthenticated")
    uid = u["id"]
    path = request.url.path
    key, ke = _require_idem(request, uid, body)
    if ke:
        return ke
    with _lock:
        rec, same = idem_lookup(uid, key, "POST", path, body)
        if rec is not None:
            if same:
                return JSONResponse(rec["response"], status_code=200)
            return err(409, "idempotency_key_reuse", "key reuse")
        if uid not in _state["settlement_operator_ids"]:
            return err(403, "forbidden", "forbidden")
        transfers = body.get("transfers")
        if not isinstance(transfers, list) or not (1 <= len(transfers) <= 32):
            return err(422, "validation_failed", "bad transfers")
        # entry errors in input order
        parsed = []
        for t in transfers:
            if not isinstance(t, dict):
                return err(422, "validation_failed", "bad transfer")
            fh = t.get("from_handle")
            th = t.get("to_handle")
            amt_raw = t.get("amount")
            if fh is None or th is None or amt_raw is None:
                return err(422, "validation_failed", "missing transfer field")
            if not isinstance(fh, str) or not isinstance(th, str):
                return err(422, "validation_failed", "bad handle")
            amt, ok = parse_amount(amt_raw)
            if not ok:
                return err(422, "validation_failed", "bad amount")
            note = t.get("note", "")
            if "note" in t:
                if not isinstance(note, str):
                    return err(422, "validation_failed", "bad note")
                if len(note) > 200:
                    return err(422, "validation_failed", "bad note")
            else:
                note = ""
            vis = t.get("visibility", "public")
            if "visibility" in t:
                if not isinstance(vis, str) or vis not in ("public", "private"):
                    return err(422, "validation_failed", "bad visibility")
            else:
                vis = "public"
            fuid = _state["users_by_handle"].get(fh)
            tuid = _state["users_by_handle"].get(th)
            if fuid is None or tuid is None:
                return err(404, "not_found", "unknown handle")
            if fh == th:
                return err(422, "self_payment", "self payment")
            parsed.append({"from_handle": fh, "to_handle": th, "from_uid": fuid, "to_uid": tuid,
                           "amount": amt, "note": note, "visibility": vis})
        # affordability: net per wallet, evaluated against available
        delta = {}
        for p in parsed:
            delta[p["from_uid"]] = delta.get(p["from_uid"], 0) - p["amount"]
            delta[p["to_uid"]] = delta.get(p["to_uid"], 0) + p["amount"]
        for w, d in delta.items():
            uo = _state["users_by_id"][w]
            nb = uo["balance"] + d
            if nb - held_for(w) < 0:
                return err(409, "insufficient_funds", "insufficient funds")
            if abs(nb) > 2**53:
                return err(422, "validation_failed", "range")
        sid = _unique_id("st", _state["settlements"])
        ts = now_iso()
        pay_views = []
        for p in parsed:
            _state["seq"] += 1
            pid = f"p_{_state['seq']}"
            while pid in _state["payments"]:
                _state["seq"] += 1
                pid = f"p_{_state['seq']}"
            obj = {
                "payment_id": pid, "from_user_id": p["from_uid"], "from_handle": p["from_handle"],
                "to_user_id": p["to_uid"], "to_handle": p["to_handle"],
                "amount": p["amount"], "currency": _state["currency"], "note": p["note"],
                "visibility": p["visibility"], "request_id": None, "settlement_id": sid,
                "authorization_id": None,
                "refund_of": None,
                "revisions": [{"revision": 1, "amount": p["amount"],
                               "effective_at": ts, "recorded_at": ts, "reason": ""}],
                "created_at": ts, "_seq": _state["seq"],
            }
            _state["payments"][pid] = obj
            pay_views.append(payment_view(obj))
        for w, d in delta.items():
            _state["users_by_id"][w]["balance"] += d
        _state["seq"] += 1
        _state["settlements"][sid] = {
            "settlement_id": sid, "committed_at": ts,
            "payment_ids": [p["payment_id"] for p in pay_views], "_seq": _state["seq"],
        }
        resp = {"settlement_id": sid, "committed_at": ts, "payments": pay_views}
        idem_store(uid, key, "POST", path, body, resp)
    return JSONResponse(resp, status_code=201)


@app.post("/authorizations")
async def create_authorization(request: Request):
    body, e = await parse_obj(request)
    if e:
        return e
    u = get_auth_user(request)
    if not u:
        return err(401, "unauthenticated", "unauthenticated")
    uid = u["id"]
    path = request.url.path
    key, ke = _require_idem(request, uid, body)
    if ke:
        return ke
    with _lock:
        rec, same = idem_lookup(uid, key, "POST", path, body)
        if rec is not None:
            if same:
                return JSONResponse(rec["response"], status_code=200)
            return err(409, "idempotency_key_reuse", "key reuse")
        if "to_handle" not in body or "amount" not in body:
            return err(422, "validation_failed", "missing field")
        to_h = body["to_handle"]
        amt_raw = body["amount"]
        if not isinstance(to_h, str):
            return err(400, "malformed_request", "bad handle type")
        amt, ok = parse_amount(amt_raw)
        if not ok:
            return err(422, "validation_failed", "bad amount")
        note, ok = validate_note(body)
        if not ok:
            return err(422, "validation_failed", "bad note")
        vis, ok = validate_visibility(body)
        if not ok:
            return err(422, "validation_failed", "bad visibility")
        if to_h == u["handle"]:
            return err(422, "self_payment", "self payment")
        target_uid = _state["users_by_handle"].get(to_h)
        if target_uid is None:
            return err(404, "not_found", "unknown handle")
        if available_for(u) < amt:
            return err(409, "insufficient_funds", "insufficient funds")
        aid = _unique_id("a", _state["authorizations"])
        ts = now_iso()
        exp = (_now() + timedelta(seconds=int(_state["authorization_ttl_seconds"]))).isoformat()
        _state["seq"] += 1
        a = {
            "authorization_id": aid, "from_user_id": uid, "from_handle": u["handle"],
            "to_user_id": target_uid, "to_handle": to_h,
            "amount": amt, "captured_amount": 0, "currency": _state["currency"],
            "note": note, "visibility": vis, "status": "open",
            "expires_at": exp, "closed_at": None,
            "payment_id": None, "payment_ids": [],
            "created_at": ts, "_seq": _state["seq"],
        }
        _state["authorizations"][aid] = a
        resp = auth_view(a)
        idem_store(uid, key, "POST", path, body, resp)
    return JSONResponse(resp, status_code=201)


def _capture_amount(body):
    if "amount" not in body:
        return "default", None
    v = body["amount"]
    if isinstance(v, bool):
        return None, False
    if isinstance(v, int):
        return v, True
    if isinstance(v, float) and float(v).is_integer():
        return int(v), True
    return None, False


@app.post("/authorizations/{aid}/capture")
async def capture_authorization(aid: str, request: Request):
    body, e = await parse_obj(request)
    if e:
        return e
    u = get_auth_user(request)
    if not u:
        return err(401, "unauthenticated", "unauthenticated")
    uid = u["id"]
    path = request.url.path
    key, ke = _require_idem(request, uid, body)
    if ke:
        return ke
    with _lock:
        rec, same = idem_lookup(uid, key, "POST", path, body)
        if rec is not None:
            if same:
                return JSONResponse(rec["response"], status_code=200)
            return err(409, "idempotency_key_reuse", "key reuse")
        a = _state["authorizations"].get(aid)
        if a is None:
            return err(404, "not_found", "unknown authorization")
        if uid != a["to_user_id"] and uid != a["from_user_id"]:
            return err(403, "forbidden", "forbidden")
        if uid != a["to_user_id"]:
            return err(403, "forbidden", "forbidden")
        if a.get("status") != "open":
            return err(409, "authorization_not_open", "not open")
        if not auth_effectively_open(a):
            return err(409, "authorization_expired", "expired")
        remaining = int(a["amount"]) - int(a.get("captured_amount", 0))
        mode, ok = _capture_amount(body)
        if mode == "default":
            cap_amt = remaining
        elif not ok:
            return err(422, "validation_failed", "bad amount")
        else:
            cap_amt = mode
        if cap_amt is not None and cap_amt < 1:
            return err(422, "validation_failed", "bad amount")
        if cap_amt > remaining:
            return err(422, "capture_exceeds_authorization", "exceeds authorization")
        final = body.get("final", True)
        if "final" in body and not isinstance(final, bool):
            return err(400, "malformed_request", "bad final type")
        if not isinstance(final, bool):
            final = True
        payer = _state["users_by_id"][a["from_user_id"]]
        receiver = _state["users_by_id"][a["to_user_id"]]
        nb_p = payer["balance"] - cap_amt
        nb_r = receiver["balance"] + cap_amt
        if abs(nb_p) > 2**53 or abs(nb_r) > 2**53:
            return err(422, "validation_failed", "range")
        _state["seq"] += 1
        pid = f"p_{_state['seq']}"
        while pid in _state["payments"]:
            _state["seq"] += 1
            pid = f"p_{_state['seq']}"
        ts = now_iso()
        p = {
            "payment_id": pid, "from_user_id": payer["id"], "from_handle": payer["handle"],
            "to_user_id": receiver["id"], "to_handle": receiver["handle"],
            "amount": cap_amt, "currency": _state["currency"],
            "note": a["note"], "visibility": a["visibility"],
            "request_id": None, "settlement_id": None, "authorization_id": aid,
            "refund_of": None,
            "revisions": [{"revision": 1, "amount": cap_amt,
                           "effective_at": ts, "recorded_at": ts, "reason": ""}],
            "created_at": ts, "_seq": _state["seq"],
        }
        payer["balance"] = nb_p
        receiver["balance"] = nb_r
        _state["payments"][pid] = p
        a["captured_amount"] = int(a.get("captured_amount", 0)) + cap_amt
        a["payment_id"] = pid
        pids = list(a.get("payment_ids", []))
        pids.append(pid)
        a["payment_ids"] = pids
        new_remaining = int(a["amount"]) - int(a["captured_amount"])
        if final or new_remaining <= 0:
            a["status"] = "captured"
            a["closed_at"] = ts
        resp = payment_view(p)
        idem_store(uid, key, "POST", path, body, resp)
    return JSONResponse(resp, status_code=201)


@app.post("/authorizations/{aid}/void")
async def void_authorization(aid: str, request: Request):
    u = get_auth_user(request)
    if not u:
        return err(401, "unauthenticated", "unauthenticated")
    uid = u["id"]
    with _lock:
        a = _state["authorizations"].get(aid)
        if a is None:
            return err(404, "not_found", "unknown authorization")
        if uid != a["from_user_id"] and uid != a["to_user_id"]:
            return err(403, "forbidden", "forbidden")
        if uid != a["from_user_id"]:
            return err(403, "forbidden", "forbidden")
        if a.get("status") == "voided":
            return auth_view(a)
        if a.get("status") != "open" or not auth_effectively_open(a):
            return err(409, "authorization_not_open", "not open")
        a["status"] = "voided"
        a["closed_at"] = now_iso()
        return auth_view(a)


def parse_amount_zero(v):
    if isinstance(v, bool):
        return None, False
    if isinstance(v, int):
        if 0 <= v <= 1000000000:
            return v, True
        return None, False
    if isinstance(v, float):
        if v.is_integer() and 0 <= int(v) <= 1000000000:
            return int(v), True
        return None, False
    return None, False


def _batch_history_ok(replacements):
    """Check the corrected ledger stays nonnegative (total and available)
    at every effective/event boundary for every affected party, under the
    combined effect of all proposed revisions."""
    parties = set()
    for pid in replacements:
        p = _state["payments"].get(pid)
        if p is None:
            return False
        parties.add(p.get("from_user_id"))
        parties.add(p.get("to_user_id"))
    for uid in parties:
        movs = []
        bounds = set()
        for q in _state["payments"].values():
            if q.get("from_user_id") != uid and q.get("to_user_id") != uid:
                continue
            if q.get("payment_id") in replacements:
                amt, eff = replacements[q.get("payment_id")]
            else:
                r = _latest_rev(q)
                amt = r.get("amount", 0)
                eff = _parse_instant(r.get("effective_at"))
                if eff is None:
                    return False
            movs.append((eff, _signed(uid, q, amt)))
            bounds.add(eff)
        for t in _hold_event_times(uid):
            bounds.add(t)
        opening = _state["openings"].get(uid, 0)
        for b in sorted(bounds):
            tot = opening + sum(s for (e, s) in movs if e <= b)
            if tot < 0:
                return False
            if tot - _held_at(uid, b) < 0:
                return False
    return True


def _correction_history_ok(p, new_amount, new_eff):
    """Check the corrected ledger stays nonnegative (total and available)
    at every effective/event boundary for both parties."""
    return _batch_history_ok({p.get("payment_id"): (new_amount, new_eff)})


@app.post("/payments/{pid}/corrections")
async def create_correction(pid: str, request: Request):
    body, e = await parse_obj(request)
    if e:
        return e
    u = get_auth_user(request)
    if not u:
        return err(401, "unauthenticated", "unauthenticated")
    uid = u["id"]
    path = request.url.path
    key, ke = _require_idem(request, uid, body)
    if ke:
        return ke
    with _lock:
        rec, same = idem_lookup(uid, key, "POST", path, body)
        if rec is not None:
            if same:
                return JSONResponse(rec["response"], status_code=200)
            return err(409, "idempotency_key_reuse", "key reuse")
        p = _state["payments"].get(pid)
        if p is None:
            return err(404, "not_found", "unknown payment")
        # Linked payments (settlement members, captures, refunds) cannot be corrected
        if p.get("settlement_id") is not None or p.get("authorization_id") is not None \
                or p.get("refund_of") is not None:
            return err(422, "linked_payment_immutable", "linked payment")
        if uid != p.get("from_user_id"):
            return err(403, "forbidden", "forbidden")
        if ("expected_revision" not in body or "amount" not in body
                or "effective_at" not in body or "reason" not in body):
            return err(422, "validation_failed", "missing field")
        exp_raw, amt_raw = body["expected_revision"], body["amount"]
        eff_raw, reason = body["effective_at"], body["reason"]
        if isinstance(exp_raw, bool):
            return err(422, "validation_failed", "bad revision")
        if isinstance(exp_raw, int):
            exp_rev = exp_raw
        elif isinstance(exp_raw, float) and float(exp_raw).is_integer():
            exp_rev = int(exp_raw)
        else:
            return err(422, "validation_failed", "bad revision")
        if exp_rev < 1:
            return err(422, "validation_failed", "bad revision")
        amt, ok = parse_amount_zero(amt_raw)
        if not ok:
            return err(422, "validation_failed", "bad amount")
        new_eff = _parse_instant(eff_raw)
        if new_eff is None or new_eff > _now():
            return err(422, "validation_failed", "bad effective_at")
        if not isinstance(reason, str) or not (1 <= len(reason) <= 200):
            return err(422, "validation_failed", "bad reason")
        revs = p.get("revisions")
        if not isinstance(revs, list) or not revs:
            return err(422, "validation_failed", "bad payment")
        cur = len(revs)
        if exp_rev != cur:
            return err(409, "stale_revision", "stale revision")
        if amt < _refunded_total(pid):
            return err(422, "refund_exceeds_payment", "refund exceeds payment")
        old_amt = revs[-1].get("amount", 0)
        delta = amt - old_amt
        sender = _state["users_by_id"].get(p["from_user_id"])
        receiver = _state["users_by_id"].get(p["to_user_id"])
        if sender is None or receiver is None:
            return err(422, "validation_failed", "bad payment")
        if delta > 0 and available_for(sender) < delta:
            return err(409, "insufficient_funds", "insufficient funds")
        if delta < 0 and available_for(receiver) < -delta:
            return err(409, "insufficient_funds", "insufficient funds")
        if not _correction_history_ok(p, amt, new_eff):
            return err(409, "historical_overdraft", "historical overdraft")
        last_rec = _parse_instant(revs[-1].get("recorded_at")) or _EPOCH
        stamp = _now()
        if stamp <= last_rec:
            stamp = last_rec + timedelta(microseconds=1)
        rev = {"revision": cur + 1, "amount": amt,
               "effective_at": eff_raw, "recorded_at": stamp.isoformat(),
               "reason": reason}
        sender["balance"] -= delta
        receiver["balance"] += delta
        if abs(sender["balance"]) > 2**53 or abs(receiver["balance"]) > 2**53:
            sender["balance"] += delta
            receiver["balance"] -= delta
            return err(422, "validation_failed", "range")
        revs.append(rev)
        resp = _revision_view(pid, rev)
        idem_store(uid, key, "POST", path, body, resp)
    return JSONResponse(resp, status_code=201)


@app.post("/payments/{pid}/refunds")
async def create_refund(pid: str, request: Request):
    body, e = await parse_obj(request)
    if e:
        return e
    u = get_auth_user(request)
    if not u:
        return err(401, "unauthenticated", "unauthenticated")
    uid = u["id"]
    path = request.url.path
    key, ke = _require_idem(request, uid, body)
    if ke:
        return ke
    with _lock:
        rec, same = idem_lookup(uid, key, "POST", path, body)
        if rec is not None:
            if same:
                return JSONResponse(rec["response"], status_code=200)
            return err(409, "idempotency_key_reuse", "key reuse")
        p = _state["payments"].get(pid)
        if p is None:
            return err(404, "not_found", "unknown payment")
        if uid != p.get("to_user_id"):
            return err(403, "forbidden", "forbidden")
        if p.get("refund_of") is not None:
            return err(422, "invalid_refund_target", "invalid refund target")
        amt_raw = body.get("amount")
        if amt_raw is None:
            return err(422, "validation_failed", "missing field")
        amt, ok = parse_amount(amt_raw)
        if not ok:
            return err(422, "validation_failed", "bad amount")
        # check cumulative refunds against the current corrected amount
        refunded = _refunded_total(pid)
        if refunded + amt > _latest_rev(p).get("amount", 0):
            return err(422, "refund_exceeds_payment", "refund exceeds payment")
        # check available funds of the receiver
        if available_for(u) < amt:
            return err(409, "insufficient_funds", "insufficient funds")
        nb_receiver = u["balance"] - amt
        sender = _state["users_by_id"][p["from_user_id"]]
        nb_sender = sender["balance"] + amt
        if abs(nb_receiver) > 2**53 or abs(nb_sender) > 2**53:
            return err(422, "validation_failed", "range")
        _state["seq"] += 1
        rpid = f"p_{_state['seq']}"
        while rpid in _state["payments"]:
            _state["seq"] += 1
            rpid = f"p_{_state['seq']}"
        ts = now_iso()
        rp = {
            "payment_id": rpid, "from_user_id": uid, "from_handle": u["handle"],
            "to_user_id": p["from_user_id"], "to_handle": sender["handle"],
            "amount": amt, "currency": _state["currency"], "note": p["note"], "visibility": p["visibility"],
            "request_id": None, "settlement_id": None, "authorization_id": None,
            "refund_of": pid,
            "revisions": [{"revision": 1, "amount": amt,
                           "effective_at": ts, "recorded_at": ts, "reason": ""}],
            "created_at": ts, "_seq": _state["seq"],
        }
        u["balance"] = nb_receiver
        sender["balance"] = nb_sender
        _state["payments"][rpid] = rp
        resp = payment_view(rp)
        idem_store(uid, key, "POST", path, body, resp)
    return JSONResponse(resp, status_code=201)


@app.get("/payments/{pid}/refunds")
def list_refunds(pid: str, request: Request):
    u = get_auth_user(request)
    if not u:
        return err(401, "unauthenticated", "unauthenticated")
    with _lock:
        p = _state["payments"].get(pid)
        if p is None:
            return err(404, "not_found", "unknown payment")
        if u["id"] != p.get("from_user_id") and u["id"] != p.get("to_user_id"):
            return err(404, "not_found", "not found")
        refunds = [q for q in _state["payments"].values() if q.get("refund_of") == pid]
        return {"refunds": [payment_view(r) for r in refunds]}


@app.post("/correction-batches")
async def create_correction_batch(request: Request):
    body, e = await parse_obj(request)
    if e:
        return e
    u = get_auth_user(request)
    if not u:
        return err(401, "unauthenticated", "unauthenticated")
    uid = u["id"]
    path = request.url.path
    key, ke = _require_idem(request, uid, body)
    if ke:
        return ke
    if uid not in _state["settlement_operator_ids"]:
        return err(403, "forbidden", "forbidden")
    with _lock:
        rec, same = idem_lookup(uid, key, "POST", path, body)
        if rec is not None:
            if same:
                return JSONResponse(rec["response"], status_code=200)
            return err(409, "idempotency_key_reuse", "key reuse")
        corrections = body.get("corrections")
        if not isinstance(corrections, list) or not (1 <= len(corrections) <= 32):
            return err(422, "validation_failed", "bad corrections")
        # Validate each item and check for duplicate payment_ids
        payment_ids = set()
        items = []
        for idx, item in enumerate(corrections):
            if not isinstance(item, dict):
                return err(422, "validation_failed", f"bad correction at index {idx}")
            for field in ("payment_id", "expected_revision", "amount", "effective_at", "reason"):
                if field not in item:
                    return err(422, "validation_failed", f"missing field at index {idx}")
            pid = item["payment_id"]
            if not isinstance(pid, str):
                return err(422, "validation_failed", f"bad payment_id at index {idx}")
            if pid in payment_ids:
                return err(422, "validation_failed", f"duplicate payment_id at index {idx}")
            payment_ids.add(pid)
            # parse and validate amount
            amt_raw = item["amount"]
            amt, ok = parse_amount_zero(amt_raw)
            if not ok:
                return err(422, "validation_failed", f"bad amount at index {idx}")
            # parse effective_at
            eff = _parse_instant(item["effective_at"])
            if eff is None or eff > _now():
                return err(422, "validation_failed", f"bad effective_at at index {idx}")
            # parse reason
            reason = item["reason"]
            if not isinstance(reason, str) or not (1 <= len(reason) <= 200):
                return err(422, "validation_failed", f"bad reason at index {idx}")
            exp_raw = item["expected_revision"]
            if isinstance(exp_raw, bool):
                return err(422, "validation_failed", f"bad revision at index {idx}")
            if isinstance(exp_raw, int):
                exp_rev = exp_raw
            elif isinstance(exp_raw, float) and float(exp_raw).is_integer():
                exp_rev = int(exp_raw)
            else:
                return err(422, "validation_failed", f"bad revision at index {idx}")
            if exp_rev < 1:
                return err(422, "validation_failed", f"bad revision at index {idx}")
            items.append({
                "pid": pid, "exp_rev": exp_rev, "amt": amt, "eff": eff, "reason": reason,
                "raw_eff": item["effective_at"], "raw_reason": reason,
            })
        # Check for incomplete settlement
        settlement_payments = {}
        for item in items:
            p = _state["payments"].get(item["pid"])
            if p is None:
                return err(404, "not_found", f"unknown payment {item['pid']}")
            sid = p.get("settlement_id")
            if sid:
                settlement_payments.setdefault(sid, []).append(item["pid"])
        for sid, pids in settlement_payments.items():
            settlement = _state["settlements"].get(sid)
            if settlement:
                member_pids = set(settlement.get("payment_ids", []))
                corrected_pids = set(pids)
                if member_pids != corrected_pids:
                    return err(422, "incomplete_settlement", "incomplete settlement")
                # Check identical effective_at for all members
                effs = [item["eff"] for item in items if item["pid"] in pids]
                if len(set(e.isoformat() for e in effs)) > 1:
                    return err(422, "validation_failed", "settlement members have different effective_at")
        # Validate each payment and check stale revision / immutable
        for item in items:
            p = _state["payments"].get(item["pid"])
            if p.get("settlement_id") is not None:
                # settlement member - already checked completeness
                pass
            elif p.get("authorization_id") is not None:
                return err(422, "linked_payment_immutable", "linked payment")
            elif p.get("refund_of") is not None:
                return err(422, "linked_payment_immutable", "linked payment")
            if p.get("payment_id") is None:
                return err(422, "validation_failed", "bad payment")
            revs = p.get("revisions")
            if not isinstance(revs, list) or not revs:
                return err(422, "validation_failed", "bad payment")
            cur = len(revs)
            if item["exp_rev"] != cur:
                return err(409, "stale_revision", "stale revision")
            if item["amt"] < _refunded_total(item["pid"]):
                return err(422, "refund_exceeds_payment", "refund exceeds payment")
        # Combined affordability on the resulting current available funds
        net = {}
        for item in items:
            p = _state["payments"].get(item["pid"])
            d = item["amt"] - p["revisions"][-1].get("amount", 0)
            net[p["from_user_id"]] = net.get(p["from_user_id"], 0) - d
            net[p["to_user_id"]] = net.get(p["to_user_id"], 0) + d
        for w, d in net.items():
            if available_for(_state["users_by_id"][w]) + d < 0:
                return err(409, "insufficient_funds", "insufficient funds")
        # Combined historical check over every affected boundary
        if not _batch_history_ok({item["pid"]: (item["amt"], item["eff"]) for item in items}):
            return err(409, "historical_overdraft", "historical overdraft")
        # Apply all corrections
        stamp = _now()
        # Ensure stamp is strictly later than any recorded_at of all affected payments
        for item in items:
            p = _state["payments"].get(item["pid"])
            last_rec = _parse_instant(p["revisions"][-1].get("recorded_at")) or _EPOCH
            if stamp <= last_rec:
                stamp = last_rec + timedelta(microseconds=1)
        # Apply
        batch_revisions = []
        for item in items:
            p = _state["payments"].get(item["pid"])
            old_amt = p["revisions"][-1].get("amount", 0)
            delta = item["amt"] - old_amt
            sender = _state["users_by_id"][p["from_user_id"]]
            receiver = _state["users_by_id"][p["to_user_id"]]
            sender["balance"] -= delta
            receiver["balance"] += delta
            rev = {"revision": len(p["revisions"]) + 1, "amount": item["amt"],
                   "effective_at": item["raw_eff"], "recorded_at": stamp.isoformat(),
                   "reason": item["raw_reason"], "correction_batch_id": None}
            p["revisions"].append(rev)
            batch_revisions.append(_revision_view(item["pid"], rev))
        cbid = _unique_id("cb", _state.get("correction_batches", {}))
        _state.setdefault("correction_batches", {})[cbid] = {
            "correction_batch_id": cbid, "recorded_at": stamp.isoformat(),
            "revisions": batch_revisions,
        }
        for rev in batch_revisions:
            rev["correction_batch_id"] = cbid
        resp = {"correction_batch_id": cbid, "recorded_at": stamp.isoformat(),
                "revisions": batch_revisions}
        idem_store(uid, key, "POST", path, body, resp)
    return JSONResponse(resp, status_code=201)


@app.get("/payments/{pid}/revisions")
def payment_revisions(pid: str, request: Request):
    u = get_auth_user(request)
    if not u:
        return err(401, "unauthenticated", "unauthenticated")
    with _lock:
        p = _state["payments"].get(pid)
        if p is None:
            return err(404, "not_found", "unknown payment")
        if u["id"] != p.get("from_user_id") and u["id"] != p.get("to_user_id"):
            return err(404, "not_found", "not found")
        return {"revisions": [_revision_view(pid, r) for r in _pay_revisions(p)]}


@app.get("/authorizations")
def list_authorizations(request: Request):
    accepts = request.headers.get("accept", "")
    if "text/html" in accepts:
        from .ui import page_authorizations
        return HTMLResponse(page_authorizations())
    u = get_auth_user(request)
    if not u:
        return err(401, "unauthenticated", "unauthenticated")
    qp = dict(request.query_params)
    direction = qp.get("direction")
    status = qp.get("status")
    if direction is not None and direction not in ("incoming", "outgoing"):
        return err(422, "validation_failed", "bad direction")
    if status is not None and status not in ("open", "captured", "voided", "expired"):
        return err(422, "validation_failed", "bad status")
    limit, offset, e = parse_limit_offset(qp)
    if e:
        return e
    with _lock:
        items = [a for a in _state["authorizations"].values()
                 if a["from_user_id"] == u["id"] or a["to_user_id"] == u["id"]]
        if direction == "outgoing":
            items = [a for a in items if a["from_user_id"] == u["id"]]
        elif direction == "incoming":
            items = [a for a in items if a["to_user_id"] == u["id"]]
        if status is not None:
            items = [a for a in items if auth_status(a) == status]
        items = _newest_first(items)
        total = len(items)
        page = items[offset:offset + limit]
        has_more = (offset + limit) < total
        out = [auth_view(a) for a in page]
    return {"authorizations": out, "has_more": has_more}


@app.get("/")
def ui_home():
    from .ui import page_home
    return HTMLResponse(page_home())


@app.get("/signup")
def ui_signup():
    from .ui import page_signup
    return HTMLResponse(page_signup())


@app.get("/login")
def ui_login():
    from .ui import page_login
    return HTMLResponse(page_login())


@app.get("/split")
def ui_split():
    from .ui import page_split
    return HTMLResponse(page_split())


@app.exception_handler(404)
async def not_found_handler(request, exc):
    return err(404, "not_found", "not found")


@app.exception_handler(405)
async def method_handler(request, exc):
    return err(404, "not_found", "not found")


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port)
