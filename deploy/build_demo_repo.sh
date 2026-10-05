#!/usr/bin/env bash
# Build the judge-facing Streamlit demo repository, check it, and push it.
#
# Why this exists: the submission form wants a live demo URL, and its platform list offered
# Streamlit. The wallet is a FastAPI service, so this does not pretend it was a Streamlit
# app all along -- it puts a Streamlit page in front of the *unmodified* stage-4 service and
# runs the real thing underneath. What a judge clicks is `stage-4/src/app.py`, byte for byte.
#
# The service is copied from `stage-4/src/` at build time rather than kept as a second copy
# under deploy/, because two copies of app.py in one git history is a file that will drift
# and nobody will notice until a judge reads the wrong one.
#
#   bash deploy/build_demo_repo.sh --check-only   # assemble and run the UI check, no push
#   bash deploy/build_demo_repo.sh                # the same, then create/push the repo
set -euo pipefail

REPO=crytobot459/pocketful-demo
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="$ROOT/deploy/streamlit"
STAGE="$ROOT/stage-4"
DEST=/tmp/pocketful-demo

say() { printf '\n\033[1m%s\033[0m\n' "$*"; }

[ "$#" -gt 0 ] && [ "$1" = "--check-only" ] && CHECK_ONLY=1 || CHECK_ONLY=0

say "0/5  assembling $DEST"
rm -rf "$DEST"
mkdir -p "$DEST/.streamlit"
cp "$SRC/streamlit_app.py" "$SRC/requirements.txt" "$SRC/README.md" "$SRC/runtime.txt" "$DEST/"
cp "$SRC/.streamlit/config.toml" "$DEST/.streamlit/"
cp -r "$STAGE/src" "$DEST/src"
rm -rf "$DEST/src/__pycache__" "$DEST/src"/**/__pycache__
# The service is the submission's, so the demo must not drift from it silently: if the copy
# is not byte-identical, stop rather than shipping a demo of something else. Only .py files
# are compared, because __pycache__ is dropped from the copy on purpose.
if ! diff -r --exclude=__pycache__ "$STAGE/src" "$DEST/src" >/dev/null; then
  echo "REFUSING: the assembled src/ is not identical to stage-4/src" >&2
  exit 1
fi
for f in .env agent_config.yaml; do
  [ -e "$DEST/$f" ] && { echo "REFUSING: $f is in the demo tree" >&2; exit 1; }
done
echo "ok: $(find "$DEST" -type f -not -path '*/.git/*' | wc -l | tr -d ' ') files, src identical to stage-4/src"

say "1/5  reading the claims out of the running UI"
# Streamlit's own test harness, so what is checked is the page a judge gets rather than the
# functions behind it. It clicks Seed, Sign in and Fire-it-twice, and the run fails if the
# service does not refuse the overdraft and leaves the balance alone, or if the same
# idempotency key twice moves the money twice.
#
# It then opens a *second* session against the same service without reseeding, which is the
# situation every judge after the first one is in. That phase is here because the first one
# passed while the demo was broken for everyone but the first visitor: the write keys were
# scoped to the minute, so two visitors shared one key and the second was served a replay.
PY=$(command -v python3)
VENV=$(mktemp -d /tmp/pf-demo-venv.XXXXXX)
trap 'rm -rf "$VENV"' EXIT
"$PY" -m venv "$VENV" >/dev/null
"$VENV/bin/pip" install -q --disable-pip-version-check -r "$DEST/requirements.txt"
"$VENV/bin/pip" install -q --disable-pip-version-check "streamlit==1.40.2"
"$VENV/bin/python" - "$DEST" <<'PYCHECK'
import pathlib, re, sys
from streamlit.testing.v1 import AppTest

dest = pathlib.Path(sys.argv[1])
app = str(dest / "streamlit_app.py")


def open_page():
    """A new browser session. The service underneath is `cache_resource`, so it is the
    same one for every session in this process -- which is the deployed situation."""
    at = AppTest.from_file(app, default_timeout=120)
    at.run()
    if at.exception:
        raise SystemExit(f"FAIL: the page raised {[e.value for e in at.exception]}")
    return at


def click(at, label):
    for b in at.button:
        if b.label == label:
            b.click(); at.run(); return
    raise SystemExit(f"FAIL: no button labelled {label!r}; has {[b.label for b in at.button]}")


def texts(at, kind):
    return [m.value for m in getattr(at, kind)]


def metric(at, label):
    for m in at.metric:
        if m.label == label:
            return m.value
    raise SystemExit(f"FAIL: no metric labelled {label!r}")


def fail(msg):
    ok = texts(at, "success")
    num = [(m.label, m.value) for m in at.metric]
    raise SystemExit(f"FAIL: {msg}; page said ok={ok} err={texts(at, 'error')} num={num}")


def session(at):
    """(session id, idempotency key) as the page prints them."""
    sid = key = None
    for m in list(at.markdown) + list(at.caption):
        v = m.value
        hit = re.search(r"session id `([0-9a-f]+)`", v)
        if hit:
            sid = hit.group(1)
        hit = re.search(r"idempotency key `([^`]+)`", v)
        if hit:
            key = hit.group(1)
    return sid, key


# --- one visitor, on a fresh service -------------------------------------------------
at = open_page()
click(at, "Seed the fixture")
click(at, "Sign in as Ada")
click(at, "Try to overdraw")
click(at, "Fire it twice")

if at.exception:
    raise SystemExit(f"FAIL: the page raised {[e.value for e in at.exception]}")

ok = texts(at, "success")
err = texts(at, "error")
checked = 0
for line in err:
    fail(f"the page reported {line!r}")

need = [
    ("seeded", lambda: any("seeded" in s for s in ok)),
    ("signed in as Ada at EUR 100.00",
     lambda: any("signed in as Ada" in s and "100.00" in s for s in ok)),
    ("the overdraft is refused at 409 and the balance does not move",
     lambda: metric(at, "response").startswith("409")
             and metric(at, "balance after") == metric(at, "balance before")
             and any("unchanged" in s for s in ok)),
    ("the same key twice moves the money once, 100.00 -> 92.23",
     lambda: metric(at, "balance") == "EUR 100.00 → EUR 92.23"
             and metric(at, "feed entries for this payment") == "1"
             and any("one write, one entry" in s for s in ok)),
]
for name, check in need:
    if not check():
        fail(name)
    checked += 1
    print(f"  ok: {name}")

# --- the stage-4 capability, which is the only reason this section exists --------------
# Refunds are new in stage 4, so a demo that never fires one is not showing stage 4. The
# receiver holds the money, so Bob refunds what Ada sent; the same call from Ada is refused.
click(at, "Bob refunds it")
click(at, "Ada tries the same refund")
if at.exception:
    raise SystemExit(f"FAIL: the refund section raised {[e.value for e in at.exception]}")
for line in texts(at, "error"):
    fail(f"the refund section reported {line!r}")

def shown(at, needle):
    """`st.write({...})` reaches the page as json, so read every block the page printed."""
    return [j.value for j in at.json if needle in j.value]


refunds = [
    ("the receiver's refund settles at 201",
     lambda: any('"bob"' in j and '"status": 201' in j for j in shown(at, '"bob"'))),
    ("the sender's refund of the same payment is refused at 403",
     lambda: any('"ada"' in j and '"status": 403' in j and "forbidden" in j
                 for j in shown(at, '"ada"'))),
    ("the rule is stated on the page, not left as a bare status code",
     lambda: any("403 from the sender" in c.value for c in at.caption)),
]
for name, check in refunds:
    if not check():
        fail(name)
    checked += 1
    print(f"  ok: {name}")

# --- the second visitor, on the service the first one just used ----------------------
# The service is `cache_resource`, so it is one wallet for every session in this process --
# which is the deployed situation, where the URL is public and judges arrive in their own
# time. This phase is here because the first one passed while the demo was broken for
# everyone but the first visitor: the write key was scoped to the minute, so two visitors
# shared one key and the second was served the first one's replay.
#
# The assertion is the requirement itself -- the key belongs to the session -- rather than
# "two keys came out different". Two keys do come out different on a live clock whenever the
# minute rolls between the two page opens, which is how the minute-scoped key shipped: the
# check passed, by luck, most times.
sid_a, key_a = session(at)
b = open_page()
click(b, "Sign in as Ada")          # no reseed: this is what a returning judge does
sid_b, key_b = session(b)

scoped = [
    ("the page names the session the key belongs to",
     lambda: bool(sid_a) and bool(sid_b)),
    ("the key carries this session's id, so a second visitor cannot be served a replay",
     lambda: sid_a in key_a and sid_b in key_b),
    ("two sessions are two keys",
     lambda: sid_a != sid_b and key_a != key_b),
]
for name, check in scoped:
    if not check():
        raise SystemExit(f"FAIL: {name}; session A was ({sid_a!r}, {key_a!r}) and "
                         f"session B was ({sid_b!r}, {key_b!r})")
    checked += 1
    print(f"  ok: {name}  [{sid_a}/{key_a}] [{sid_b}/{key_b}]")

click(b, "Fire it twice")
if b.exception:
    raise SystemExit(f"FAIL: the second session raised {[e.value for e in b.exception]}")
for line in texts(b, "error"):
    fail(f"the second session reported {line!r}")

def span(at, label):
    """'EUR 92.23 → EUR 84.46' -> (9223, 8446), so a balance claim is arithmetic and not
    string matching."""
    left, right = metric(at, label).split("→")

    def one(s):
        return int(round(float(s.strip().split()[-1].replace(",", "")) * 100))

    return one(left), one(right)


shared = [
    ("the second session is still shown its own result, not a replay",
     lambda: any("one write, one entry" in s for s in texts(b, "success"))),
    ("the second session's payment is one entry in the feed, counted by payment id",
     lambda: metric(b, "feed entries for this payment") == "1"),
    ("the second session's money moved exactly once, -7.77",
     lambda: (lambda ba: ba[0] - ba[1] == 777)(span(b, "balance"))),
    ("the second session is told the service was already used, instead of quietly "
     "showing someone else's balance as its own",
     lambda: any("already used this service" in w for w in texts(b, "warning"))),
]
for name, check in shared:
    if not check():
        fail(f"second session: {name}")
    checked += 1
    print(f"  ok: {name}")

print(f"ok: {checked} claims hold against stage-4 -- the first visitor on a fresh service, "
      f"and the second on the one the first just used")
PYCHECK

if [ "$CHECK_ONLY" = 1 ]; then
  say "check-only: the demo is good and nothing was pushed"
  exit 0
fi

say "2/5  the target"
gh repo view "$REPO" --json name,visibility,url --jq '"  \(.name)  [\(.visibility)]  \(.url)"' 2>/dev/null \
  || echo "  $REPO does not exist yet; creating it"

say "3/5  committing"
cd "$DEST"
cat > .gitignore <<'EOF'
__pycache__/
*.pyc
.env
agent_config.yaml
EOF
export GIT_AUTHOR_NAME=crytobot459
export GIT_AUTHOR_EMAIL=crytobot459@users.noreply.github.com
export GIT_COMMITTER_NAME=crytobot459
export GIT_COMMITTER_EMAIL=crytobot459@users.noreply.github.com

git init -q -b main
git remote add origin "https://github.com/$REPO.git"

# The history is adopted from the remote rather than thrown away with `git init`. Re-initialising
# made every run an unrelated history, and the second push was rejected as non-fast-forward --
# which is what a force-push would "fix", and a force-push on a submission is not a thing to do.
if gh repo view "$REPO" >/dev/null 2>&1; then
  git fetch -q origin main
  git reset -q origin/main
fi

git add -A
cat > /tmp/pf-demo-commit-msg <<'MSG'
Pocketful Factory demo: stage-4 behind a Streamlit page

The submission form wants a live demo URL and offered Streamlit, but the wallet is a
FastAPI service. Rather than reimplement the wallet to look like a Streamlit app, this
runs stage-4's own src/app.py in a subprocess and drives it over HTTP: what a judge
clicks is the code in the repository, not a second program.

Streamlit reruns the whole script on every interaction and cannot hold an idempotency
key across a click, so a reimplementation was never going to work anyway. Both write
paths go through a button and keep their outcome in the session, so nothing is sent to
the service until a judge asks for it.

src/ is copied from stage-4/src at build time and the build refuses to push if the copy
is not byte-identical, so the demo cannot drift from the submission.
MSG
if git diff --cached --quiet; then
  echo "  nothing changed; the remote is already this commit"
else
  git commit -q -F /tmp/pf-demo-commit-msg
  echo "  $(git rev-list --count HEAD) commits, $(git ls-files | wc -l | tr -d ' ') files"
fi

say "4/5  pushing"
if ! gh repo view "$REPO" >/dev/null 2>&1; then
  gh repo create "$REPO" --public --description \
    "Stage-4 demo for crytobot459/pocketful-factory: the unmodified FastAPI service the agent factory built, with a Streamlit page driving it over HTTP" >/dev/null
fi
git push -u origin main
echo "  pushed: https://github.com/$REPO"

say "5/5  the one thing left is yours"
cat <<'EOF'

  1. https://share.streamlit.io -> "Deploy" -> "Deploy from GitHub"
  2. Pick crytobot459 / pocketful-demo. Three values, all of which have to agree with each
     other, and the form checks each one against the repository:
        Repository      crytobot459/pocketful-demo
        Branch          main
        Main file path  streamlit_app.py
     Pointing it at crytobot459/pocketful-factory instead answers "this branch does not
     exist" and "this file does not exist": that repository has no streamlit_app.py, and
     both repositories are on main, not master.
  3. Leave App URL empty. Streamlit issues one; paste it into the submission form afterwards.
  4. Wait for the build, then open the app and click Seed, Sign in as Ada, Fire it twice.
     Reload and do it again -- the service is one wallet shared by every visitor, and the
     second run is the one that used to fail. If those work, the URL is safe to paste.

  If the build fails on a dependency, the platform picked a Python that streamlit 1.40.2 has
  no wheel for. runtime.txt pins 3.12, which is the version this check ran on; if it is not
  honoured, set Python 3.12 in the app's settings.

  The app sleeps on the free tier, so the first visit after a pause takes 30-60 seconds
  to wake. That is worth saying in the form rather than letting a judge assume it is broken.
EOF
