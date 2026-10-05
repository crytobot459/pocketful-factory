"""A judge-facing face for stage-4, not a second implementation of it.

Streamlit reruns this whole script on every interaction, which cannot hold a wallet's state
in process variables and cannot hold an idempotency key across a click. So this does not
reimplement anything: it starts `src.app` -- the exact module the factory produced -- as a
subprocess, and every button here is one HTTP call against it. The service under the UI is
byte-identical to `stage-4/`, which is the point. A demo that showed a Streamlit
reimplementation of the wallet would be a demo of a different program than the one submitted.

Each tab reproduces one claim the video makes, and reads both sides of the invariant from
the server rather than from a value it computed itself. `pay_more_than_you_have` prints
"unchanged" only after two reads of /me agree; `pay_twice` counts the feed entries rather
than trusting the payment response.
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
    """Run stage-4's own `src.app`, once per session, and wait for it to answer.

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
           "seeds state, and stage-4/RUN.md tells a judge to call it before opening the app.")

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

st.caption(f"**Ada's balance: {money(balance_of(token))}**")

# --- 2. pay more than you have ----------------------------------------------------

st.header("2. Pay more than you have")
st.caption("The refusal arrives before the error code, and the balance does not move. The "
           "two balances below are both read from the server.")

before = balance_of(token)
st_, body = call("POST", "/payments", token, idem="ui-overdraft-1",
                 to_handle="bob", amount=999999,
                 note="more than she has")
after = balance_of(token)

c1, c2, c3 = st.columns(3)
c1.metric("balance before", money(before))
c2.metric("response", f"{st_} {body.get('code', '')}".strip())
c3.metric("balance after", money(after))
if before == after and st_ == 409:
    st.success(f"refused, and the balance is unchanged at {money(after)}")
else:
    st.error(f"expected 409 and an unchanged balance; got {st_}, {before} → {after}")

# --- 3. pay twice -----------------------------------------------------------------

st.header("3. Pay the same thing twice")
st.caption("One idempotency key, fired twice. The money moves once.")

before = balance_of(token)
key = st.session_state.setdefault("idem", f"ui-{int(time.time()) // 60}")
st.write(f"idempotency key: `{key}`")

if st.button("Fire it twice"):
    first = call("POST", "/payments", token, idem=key, to_handle="bob", amount=777,
                 note="same payment")
    second = call("POST", "/payments", token, idem=key, to_handle="bob", amount=777,
                  note="same payment")
    st.session_state["two"] = (first, second)

two = st.session_state.get("two")
if two:
    (s1, b1), (s2, b2) = two
    c1, c2 = st.columns(2)
    c1.write({"first": {"status": s1, "body": b1}})
    c2.write({"second": {"status": s2, "body": b2}})

after = balance_of(token)
entries = [p for p in feed(token) if p.get("note") == "same payment"]
c1, c2 = st.columns(2)
c1.metric("balance", f"{money(before)} → {money(after)}")
c2.metric("feed entries for this note", len(entries))
if after == before - 777 and len(entries) == 1:
    st.success(f"one write, one entry, {money(before)} → {money(after)}")
elif two:
    st.error(f"expected exactly one entry and -7.77; got {len(entries)} entries, "
             f"{money(before)} → {money(after)}")

# --- 4. the feed ------------------------------------------------------------------

st.header("4. The feed")
rows = [{"id": p.get("id"), "from": p.get("from_handle"), "to": p.get("to_handle"),
         "amount": money(p.get("amount")), "note": p.get("note"),
         "when": p.get("created_at") or p.get("recorded_at")} for p in feed(token)]
if rows:
    st.dataframe(rows, use_container_width=True)
else:
    st.write("no payments yet")

# --- 5. what the reviewer added in stage 4 ----------------------------------------

st.header("5. What stage 4 added")
st.caption("Refunds and batch corrections. The refund cap is the one the reviewer's own "
           "scenario caught: it used the original amount, so a later correction downward "
           "did not tighten it.")

pids = [p.get("id") for p in feed(token) if p.get("from_handle") == "ada"]
if pids:
    pid = st.selectbox("payment to refund", pids)
    amount = st.number_input("refund amount (EUR)", min_value=0.01, value=1.00,
                             step=0.01, format="%.2f")
    if st.button("Refund it"):
        st.session_state["refund"] = call(
            "POST", f"/payments/{pid}/refunds", token,
            idem=f"ui-refund-{pid}-{int(amount * 100)}", amount=round(amount * 100))
    if "refund" in st.session_state:
        st.write({"status": st.session_state["refund"][0], "body": st.session_state["refund"][1]})
    st_ = call("GET", f"/payments/{pid}/refunds", token)[0]
    st.caption(f"GET /payments/{pid}/refunds → {st_}")

# --- footer -----------------------------------------------------------------------

st.divider()
st.caption(
    "Repository: https://github.com/crytobot459/pocketful-factory — `stage-1/` through "
    "`stage-4/`, the BAND room export, and the factory document. Every figure in the "
    "documents is checked against the room, the git history and the harness report by "
    "`verify_claims.py`, and CI fails the build when one disagrees."
)
