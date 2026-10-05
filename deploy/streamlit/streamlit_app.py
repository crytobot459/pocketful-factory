"""A judge-facing face for stage-4, not a second implementation of it.

Streamlit reruns this whole script on every interaction, which cannot hold a wallet's state
in process variables and cannot hold an idempotency key across a click. So this does not
reimplement anything: it starts `src.app` -- the exact module the factory produced -- as a
subprocess, and every button here is one HTTP call against it. The service under the UI is
byte-identical to `stage-4/`, which is the point. A demo that showed a Streamlit
reimplementation of the wallet would be a demo of a different program than the one submitted.

Each tab reproduces one claim the video makes, and reads both sides of the invariant from
the server rather than from a value it computed itself. `pay_more_than_you_have` prints
"unchanged" only after two reads of /me agree; `pay_twice` counts the feed entries for the
payment id the service returned rather than trusting the payment response.

The service behind the page is one per process, so every visitor to a deployed URL shares
it. That is a property of a demo, not a bug to paper over: the write keys are per session,
the assertions are about what this session's own payment did, and seeding is the first
thing the page asks for.
"""
from __future__ import annotations

import atexit
import json
import os
import pathlib
import socket
import subprocess
import sys
import time
import uuid

import requests
import streamlit as st

HERE = pathlib.Path(__file__).resolve().parent
API_PORT = int(os.environ.get("POCKETFUL_API_PORT", "8080"))
BASE = os.environ.get("POCKETFUL_BASE", f"http://127.0.0.1:{API_PORT}")
TIMEOUT = 10

st.set_page_config(page_title="Pocketful Factory", page_icon="💸", layout="centered")


# --- the service -----------------------------------------------------------------

def _free_port(start: int = API_PORT) -> int:
    for port in range(start, start + 40):
        with socket.socket() as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise RuntimeError("no free port for the service")


@st.cache_resource(show_spinner="Starting stage-4...")
def service() -> tuple[str, subprocess.Popen | None]:
    """Run stage-4's own `src.app` and wait for it to answer.

    This is `cache_resource`, so the service is started **once per process, not once per
    session**: every visitor on a deployed URL talks to the same wallet, the same balances
    and the same idempotency store. That is not hidden here, it is designed around -- the
    write keys below are per session and the assertions are about what this session's own
    payment did, so a second judge arriving mid-demo sees his own result rather than a
    replay of the first judge's.

    A URL may also point at a service that is already running, which is what CI does. If
    POCKETFUL_BASE is set we use it and start nothing, so the same file serves both the
    local check and a deployed instance.
    """
    remote = os.environ.get("POCKETFUL_BASE")
    if remote and requests.get(f"{remote}/health", timeout=3).ok:
        return remote.rstrip("/"), None

    port = _free_port()
    env = {**os.environ, "PORT": str(port)}
    proc = subprocess.Popen([sys.executable, "-m", "src.app"], cwd=str(HERE),
                            env=env, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    atexit.register(lambda: proc.terminate() if proc.poll() is None else None)
    base = f"http://127.0.0.1:{port}"
    for _ in range(80):
        try:
            if requests.get(f"{base}/health", timeout=2).ok:
                return base, proc
        except requests.RequestException:
            pass
        time.sleep(0.25)
    proc.terminate()
    raise RuntimeError("stage-4 did not answer /health within 20s")


BASE_URL, _PROC = service()

# One id per browser session, drawn once and then carried in the session. Every idempotency
# key on this page is built from it, because the service above is shared: a key scoped to
# the page or to the minute is one key for every visitor, so the second judge to press the
# button gets the first judge's replay back -- 200 instead of 201, no money moved, and a
# red "expected exactly one entry" on a service that is behaving perfectly.
if "sid" not in st.session_state:
    st.session_state["sid"] = uuid.uuid4().hex[:8]
SID = st.session_state["sid"]


def call(method: str, path: str, token: str | None = None, idem: str | None = None, **body):
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    # The idempotency key is a header, not a field. `get_idem_key` reads `idempotency-key`
    # or `Idempotency-Key` and nothing else, and a key sent in the body is ignored: the
    # service answers 400 missing_idempotency_key. Every write here therefore takes `idem`.
    if idem:
        headers["Idempotency-Key"] = idem
    r = requests.request(method, f"{BASE_URL}{path}", headers=headers,
                         json=body or None, timeout=TIMEOUT)
    try:
        payload = r.json()
    except ValueError:
        payload = {"_raw": r.text[:200]}
    return r.status_code, payload


# --- the fixture, exactly as stage-4/RUN.md tells a judge to seed it --------------

SEED = {
    "currency": "EUR", "minor_units": 2,
    "users": [
        {"id": "u_ada", "email": "ada@example.com", "password": "correct horse",
         "display_name": "Ada", "handle": "ada", "balance": 10000},
        {"id": "u_bob", "email": "bob@example.com", "password": "correct horse",
         "display_name": "Bob", "handle": "bob", "balance": 2500},
    ],
    "payments": [
        {"id": "p_1", "from_user_id": "u_ada", "to_user_id": "u_bob",
         "amount": 500, "note": "coffee", "visibility": "public"},
    ],
    "requests": [
        {"id": "rq_1", "requester_id": "u_bob", "payer_id": "u_ada",
         "amount": 1200, "note": "taxi", "status": "pending"},
    ],
}


def money(minor: int | float | None) -> str:
    if minor is None:
        return "—"
    return f"EUR {minor / 100:,.2f}"


def sign_in(email: str = "ada@example.com", password: str = "correct horse"):
    st_, body = call("POST", "/auth/login", email=email, password=password)
    if st_ != 200:
        st.error(f"login failed: {st_} {body}")
        return None
    return body["token"]


def balance_of(token: str):
    st_, body = call("GET", "/me", token)
    return body.get("balance") if st_ == 200 else None


def feed(token: str, limit: int = 50) -> list[dict]:
    st_, body = call("GET", f"/activity?limit={limit}", token)
    return body.get("payments", []) if st_ == 200 else []


# --- header ----------------------------------------------------------------------

st.title("Pocketful Factory")
st.caption(
    "Stage 4 of the pocketful specification, built by three coding-agent seats in one BAND "
    "room. This page drives the service in `src/app.py` over HTTP; it does not reimplement "
    "the wallet."
)

with st.expander("What is running here"):
    st_health, health = call("GET", "/health")
    st.json({"base_url": BASE_URL, "health": st_health, "body": health,
             "same code as": "stage-4/ in the repository"})

# --- 1. seed and sign in ---------------------------------------------------------

st.header("1. Seed the accounts and sign in")
st.caption("A fresh container holds no users. `POST /_test/reset` is how the specification "
           "seeds state, and stage-4/RUN.md tells a judge to call it before opening the app. "
           "One service serves every visitor to this URL, so seeding puts it back to the "
           "starting balances for whoever comes next, including you.")

c1, c2 = st.columns(2)
if c1.button("Seed the fixture", type="primary"):
    st_, body = call("POST", "/_test/reset", **SEED)
    st.session_state.pop("token", None)
    st.session_state.pop("two", None)
    st.session_state["seeded"] = st_ == 204
    st.session_state["seed_body"] = body if st_ != 204 else None

if c2.button("Sign in as Ada"):
    tok = sign_in()
    if tok:
        st.session_state["token"] = tok
        st.session_state["signed_in"] = True
    else:
        st.session_state["signed_in"] = False

# Streamlit throws away every message from the previous run, so a confirmation that is not
# written into the session is a confirmation the judge never gets to read: clicking a second
# button silently un-confirms the first one. Two ticks that stay put are worth more here than
# two toasts that flash.
if st.session_state.get("seeded"):
    st.success("seeded — `POST /_test/reset` returned 204 and no body")
elif st.session_state.get("seed_body"):
    st.error(f"seeding failed: {st.session_state['seed_body']}")

if st.session_state.get("signed_in"):
    st.success(f"signed in as Ada — {money(balance_of(st.session_state['token']))}")
elif st.session_state.get("token") is None and st.session_state.get("signed_in") is False:
    st.error("login failed")

token = st.session_state.get("token")
if not token:
    st.info("Seed, then sign in. Everything below needs a token.")
    st.stop()

ada_now = balance_of(token)
st.caption(f"**Ada's balance: {money(ada_now)}**")
if not st.session_state.get("seeded") and ada_now != 10000:
    st.warning(f"Ada holds {money(ada_now)}, not the {money(10000)} the fixture seeds. "
               f"Someone has already used this service — press **Seed the fixture** to put "
               f"it back. The claims below hold either way; they are about what your own "
               f"payment does, not about the opening number.")

# --- 2. pay more than you have ----------------------------------------------------

st.header("2. Pay more than you have")
st.caption("The refusal arrives before the error code, and the balance does not move. The "
           "two balances below are both read from the server.")

# This runs once, from the button, and the outcome is kept. Firing it during render would
# send a payment on every rerun: idempotent, so the service is right, but a judge watching
# the network tab would see a write on every click anywhere on the page.
if "overdraft" not in st.session_state:
    st.session_state["overdraft"] = None
if st.button("Try to overdraw"):
    before = balance_of(token)
    st_, body = call("POST", "/payments", token, idem=f"ui-overdraft-{SID}",
                     to_handle="bob", amount=999999, note="more than she has")
    st.session_state["overdraft"] = (before, st_, body, balance_of(token))

od = st.session_state["overdraft"]
if od:
    before, st_, body, after = od
    c1, c2, c3 = st.columns(3)
    c1.metric("balance before", money(before))
    c2.metric("response", f"{st_} {body.get('error', {}).get('code', '')}".strip())
    c3.metric("balance after", money(after))
    if before == after and st_ == 409:
        st.success(f"refused, and the balance is unchanged at {money(after)}")
    else:
        st.error(f"expected 409 and an unchanged balance; got {st_}, "
                 f"{money(before)} → {money(after)}")
else:
    st.info("Press the button. Nothing is sent until you do.")

# --- 3. pay twice -----------------------------------------------------------------

st.header("3. Pay the same thing twice")
st.caption("One idempotency key, fired twice. The money moves once.")

key = st.session_state.setdefault("idem", f"ui-{SID}-{int(time.time()) // 60}")
st.caption(f"session id `{SID}` — idempotency key `{key}`")
st.caption("The key goes in the `Idempotency-Key` header, which is where `get_idem_key` "
           "looks. It carries this session's id, because the service above is shared with "
           "every other visitor on a deployed URL: a key scoped to the page, or to the "
           "minute, is one key for all of them, and whoever presses this button second is "
           "handed the first one's replay — 200 instead of 201, and no money moved.")

if st.button("Fire it twice"):
    # Everything the claim below rests on is read here, at the moment of the write, and kept.
    # Re-reading /me on a later rerun would compare the balance against itself, and on a
    # shared service it would also be comparing against whatever the last visitor did.
    before = balance_of(token)
    first = call("POST", "/payments", token, idem=key, to_handle="bob", amount=777,
                 note="same payment")
    second = call("POST", "/payments", token, idem=key, to_handle="bob", amount=777,
                  note="same payment")
    pid = first[1].get("payment_id")
    after = balance_of(token)
    # Counted by payment id and not by note. The note is the same fixed string on the page
    # for everyone, so counting by note lets another judge's payment land in this judge's
    # count and makes a correct service read as a broken one.
    entries = [p for p in feed(token) if p.get("payment_id") == pid]
    st.session_state["two"] = (before, first, second, pid, after, len(entries))

two = st.session_state.get("two")
if two:
    before, (s1, b1), (s2, b2), pid, after, n_entries = two
    c1, c2 = st.columns(2)
    c1.write({"first": {"status": s1, "body": b1}})
    c2.write({"second": {"status": s2, "body": b2}})
    st.caption(f"Both calls carry the same key, so the second is a replay of `{pid}` and "
               f"not a second payment: {s1} on the write, {s2} on the replay.")
else:
    before, after, n_entries = balance_of(token), balance_of(token), 0

c1, c2 = st.columns(2)
c1.metric("balance", f"{money(before)} → {money(after)}")
c2.metric("feed entries for this payment", n_entries)
if two and after == before - 777 and n_entries == 1:
    st.success(f"one write, one entry, {money(before)} → {money(after)}")
elif two:
    st.error(f"expected exactly one entry and -7.77; got {n_entries} entries, "
             f"{money(before)} → {money(after)}")
else:
    st.info("Nothing has been sent yet. Press the button.")

# --- 4. the feed ------------------------------------------------------------------

st.header("4. The feed")
# `payment_view` names the field `payment_id`; `GET /activity` returns those views verbatim.
rows = [{"payment_id": p.get("payment_id"), "from": p.get("from_handle"),
         "to": p.get("to_handle"), "amount": money(p.get("amount")),
         "note": p.get("note"), "refund_of": p.get("refund_of"),
         "when": p.get("created_at")} for p in feed(token)]
if rows:
    st.dataframe(rows, use_container_width=True)
else:
    st.write("no payments yet")

# --- 5. what stage 4 added ---------------------------------------------------------

st.header("5. What stage 4 added")
st.caption("Refunds and batch corrections. The refund cap is the one the reviewer's own "
           "scenario caught: it used the original amount, so a later correction downward "
           "did not tighten it.")

# Only the receiver may refund (`uid != p["to_user_id"] -> 403 forbidden`), so the refund is
# made as Bob. Ada sending the money and Ada refunding it is the one thing that cannot work.
bob_pids = [p["payment_id"] for p in feed(token)
            if p.get("to_handle") == "bob" and p.get("from_handle") == "ada"
            and p.get("refund_of") is None]
if not bob_pids:
    st.info("Make the payment in section 3 first — there is nothing for Bob to refund yet.")
else:
    bob = st.session_state.get("bob") or sign_in("bob@example.com")
    if bob:
        st.session_state["bob"] = bob
    by_id = {p["payment_id"]: p for p in feed(token)}
    pid = st.selectbox("payment Bob received from Ada", bob_pids,
                       format_func=lambda x: f"{x} — {by_id[x].get('note')}, "
                                             f"{money(by_id[x].get('amount'))}")
    amount = st.number_input("refund amount (EUR)", min_value=0.01, value=1.00,
                             step=0.01, format="%.2f")
    rkey = f"ui-refund-{SID}-{pid}-{int(amount * 100)}"

    c1, c2 = st.columns(2)
    if c1.button("Bob refunds it"):
        st.session_state["refund"] = call(
            "POST", f"/payments/{pid}/refunds", bob, idem=rkey,
            amount=round(amount * 100))
        st.session_state["refund_bob"] = balance_of(bob)
    if c2.button("Ada tries the same refund"):
        # The same call, the same body, the other caller. Without an amount the service
        # answers 400 on the empty body before it ever reaches the rule being shown.
        st.session_state["refund_ada"] = call(
            "POST", f"/payments/{pid}/refunds", token, idem=f"ui-refund-ada-{SID}-{pid}",
            amount=round(amount * 100))

    if "refund" in st.session_state:
        st.write({"bob": {"status": st.session_state["refund"][0],
                          "body": st.session_state["refund"][1],
                          "balance": money(st.session_state.get("refund_bob"))}})
    if "refund_ada" in st.session_state:
        st.write({"ada": {"status": st.session_state["refund_ada"][0],
                          "body": st.session_state["refund_ada"][1]}})
        if st.session_state["refund_ada"][0] == 403:
            st.caption("403 from the sender, which is the rule doing its job: a refund "
                       "moves money, so only the party holding it may issue one.")

    st_ = call("GET", f"/payments/{pid}/refunds", bob)[0]
    st.caption(f"GET /payments/{pid}/refunds as Bob → {st_}")

# --- footer -----------------------------------------------------------------------

st.divider()
st.caption(
    "Repository: https://github.com/crytobot459/pocketful-factory — `stage-1/` through "
    "`stage-4/`, the BAND room export, and the factory document. Every figure in the "
    "documents is checked against the room, the git history and the harness report by "
    "`verify_claims.py`, and CI fails the build when one disagrees."
)
