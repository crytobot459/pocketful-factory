"""Pocketful Stage-1 — full spec implementation.

Covers spec/stage-1.md sections 3-11:
auth, payments, requests, splits, settlements,
idempotency (5 paths), feed, export/import, reset.
"""
import copy
import hashlib
import hmac
import os
import re
import secrets
import threading
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
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
    "seq": 0,
}

HANDLE_RE = re.compile(r"^[a-z0-9_]{1,20}$")
LIMIT_RE = re.compile(r"^[0-9]+$")


def now_iso():
    return datetime.now(timezone.utc).isoformat()


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
        "created_at": p["created_at"],
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
    if not isinstance(currency, str) or not currency:
        return err(422, "validation_failed", "bad currency")
    if minor_units not in (0, 2, 3):
        return err(422, "validation_failed", "bad minor_units")
    if not isinstance(users, list):
        return err(422, "validation_failed", "bad users")
    if not isinstance(payments, list) or not isinstance(requests_, list):
        return err(422, "validation_failed", "bad seeded lists")
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
        _state["idempotency"] = {}
        _state["currency"] = currency
        _state["minor_units"] = minor_units
        _state["settlement_operator_ids"] = [str(x) for x in ops if isinstance(x, str)]
        _state["seq"] = 0
        ts = now_iso()
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
            _state["seq"] += 1
            _state["payments"][pid] = {
                "payment_id": pid, "from_user_id": fuid, "from_handle": fu["handle"],
                "to_user_id": tuid, "to_handle": tu["handle"],
                "amount": amt, "currency": currency, "note": note, "visibility": vis,
                "request_id": p.get("request_id"), "settlement_id": p.get("settlement_id"),
                "created_at": p.get("created_at", ts), "_seq": _state["seq"],
            }
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
    with _lock:
        return {
            "user_id": u["id"], "display_name": u["display_name"], "handle": u["handle"],
            "balance": u["balance"], "currency": _state["currency"], "minor_units": _state["minor_units"],
        }


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
        if u["balance"] < amt:
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
            "request_id": None, "settlement_id": None, "created_at": ts, "_seq": seq,
        }
        u["balance"] = nb_from
        _state["users_by_id"][target_uid]["balance"] = nb_to
        _state["payments"][pid] = p
        resp = payment_view(p)
        idem_store(uid, key, "POST", path, body, resp)
    return JSONResponse(resp, status_code=201)


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
        if payer["balance"] < amt:
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
            "request_id": rid, "settlement_id": None, "created_at": ts, "_seq": _state["seq"],
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
        items.sort(key=lambda x: x["_seq"], reverse=True)
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
        items.sort(key=lambda x: x["_seq"], reverse=True)
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
            "seq": _state["seq"],
        }
    return {"track": "pocketful", "format_version": 1, "state": snap}


@app.post("/_test/import")
async def import_state(request: Request):
    body, e = await parse_obj(request)
    if e:
        return e
    if body.get("track") != "pocketful" or body.get("format_version") != 1 or not isinstance(body.get("state"), dict):
        return err(422, "validation_failed", "bad import")
    st = body["state"]
    try:
        if not isinstance(st.get("users"), list):
            return err(422, "validation_failed", "bad state")
        # basic sanity
        n_users_by_id = {}
        n_by_email = {}
        n_by_handle = {}
        for u in st["users"]:
            if not isinstance(u, dict):
                return err(422, "validation_failed", "bad user")
            uid = str(u.get("id", ""))
            email = u.get("email", "")
            handle = u.get("handle", "")
            if not uid or not isinstance(email, str) or not isinstance(handle, str):
                return err(422, "validation_failed", "bad user fields")
            n_users_by_id[uid] = {
                "id": uid, "email": email,
                "password_hash": str(u.get("password_hash", "")),
                "display_name": str(u.get("display_name", handle)),
                "handle": handle, "balance": int(u.get("balance", 0)),
            }
            n_by_email[email] = uid
            n_by_handle[handle] = uid
        n_payments = {}
        for p in st.get("payments", []):
            if not isinstance(p, dict) or "payment_id" not in p:
                return err(422, "validation_failed", "bad payment")
            n_payments[str(p["payment_id"])] = p
        n_requests = {}
        for r in st.get("requests", []):
            if not isinstance(r, dict) or "request_id" not in r:
                return err(422, "validation_failed", "bad request")
            n_requests[str(r["request_id"])] = r
        n_tokens = dict(st.get("tokens", {}))
        n_idem = {}
        for rec in st.get("idempotency", []):
            if not isinstance(rec, dict):
                return err(422, "validation_failed", "bad idempotency")
            k = (str(rec.get("uid")), str(rec.get("key")), str(rec.get("method")), str(rec.get("path")))
            n_idem[k] = {"body": rec.get("body"), "response": rec.get("response")}
        with _lock:
            _state["users_by_id"] = n_users_by_id
            _state["users_by_email"] = n_by_email
            _state["users_by_handle"] = n_by_handle
            _state["tokens"] = {str(k): str(v) for k, v in n_tokens.items()}
            _state["payments"] = n_payments
            _state["requests"] = n_requests
            _state["splits"] = dict(st.get("splits", {}))
            _state["settlements"] = dict(st.get("settlements", {}))
            _state["idempotency"] = n_idem
            _state["currency"] = st.get("currency", "EUR")
            _state["minor_units"] = st.get("minor_units", 2)
            _state["settlement_operator_ids"] = list(st.get("settlement_operator_ids", []))
            _state["seq"] = int(st.get("seq", 0))
    except Exception:
        return err(422, "validation_failed", "bad state")
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
        # affordability: net per wallet
        delta = {}
        for p in parsed:
            delta[p["from_uid"]] = delta.get(p["from_uid"], 0) - p["amount"]
            delta[p["to_uid"]] = delta.get(p["to_uid"], 0) + p["amount"]
        for w, d in delta.items():
            nb = _state["users_by_id"][w]["balance"] + d
            if nb < 0:
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
