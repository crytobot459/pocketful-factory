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
cp "$SRC/streamlit_app.py" "$SRC/requirements.txt" "$SRC/README.md" "$DEST/"
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

say "1/5  reading the three claims out of the running UI"
# Streamlit's own test harness, so what is checked is the page a judge gets rather than the
# functions behind it. It clicks Seed, Sign in and Fire-it-twice, and the run fails if the
# service does not refuse the overdraft and leaves the balance alone, or if the same
# idempotency key twice moves the money twice.
PY=$(command -v python3)
VENV=$(mktemp -d /tmp/pf-demo-venv.XXXXXX)
trap 'rm -rf "$VENV"' EXIT
"$PY" -m venv "$VENV" >/dev/null
"$VENV/bin/pip" install -q --disable-pip-version-check -r "$DEST/requirements.txt"
"$VENV/bin/pip" install -q --disable-pip-version-check "streamlit==1.40.2"
"$VENV/bin/python" - "$DEST" <<'PYCHECK'
import sys, pathlib
from streamlit.testing.v1 import AppTest

dest = pathlib.Path(sys.argv[1])
at = AppTest.from_file(str(dest / "streamlit_app.py"), default_timeout=120)
at.run()

def click(label):
    for b in at.button:
        if b.label == label:
            b.click(); at.run(); return
    raise SystemExit(f"FAIL: no button labelled {label!r}; has {[b.label for b in at.button]}")

def texts(kind):
    return [m.value for m in getattr(at, kind)]

def metric(label):
    for m in at.metric:
        if m.label == label:
            return m.value
    raise SystemExit(f"FAIL: no metric labelled {label!r}")

if at.exception:
    raise SystemExit(f"FAIL: the page raised {[e.value for e in at.exception]}")

click("Seed the fixture")
click("Sign in as Ada")
click("Try to overdraw")
click("Fire it twice")

if at.exception:
    raise SystemExit(f"FAIL: the page raised {[e.value for e in at.exception]}")

ok = texts("success")
err = texts("error")
for line in err:
    raise SystemExit(f"FAIL: the page reported {line!r}")

need = [
    ("seeded", lambda: any("seeded" in s for s in ok)),
    ("signed in as Ada at EUR 100.00",
     lambda: any("signed in as Ada" in s and "100.00" in s for s in ok)),
    ("the overdraft is refused at 409 and the balance does not move",
     lambda: metric("response").startswith("409")
             and metric("balance after") == metric("balance before")
             and any("unchanged" in s for s in ok)),
    ("the same key twice moves the money once, 100.00 -> 92.23",
     lambda: metric("balance") == "EUR 100.00 → EUR 92.23"
             and metric("feed entries for this note") == "1"
             and any("one write, one entry" in s for s in ok)),
]
for name, check in need:
    if not check():
        raise SystemExit(f"FAIL: {name} did not hold; page said ok={ok} num="
                         f"{[(m.label, m.value) for m in at.metric]}")
    print(f"  ok: {name}")
print(f"ok: {len(need)} of {len(need)} claims hold against stage-4")
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
git init -q -b main
git -c user.name="crytobot459" -c user.email="crytobot459@users.noreply.github.com" \
    add -A
git -c user.name="crytobot459" -c user.email="crytobot459@users.noreply.github.com" \
    commit -q -F - <<'MSG'
Pocketful Factory demo: stage-4 behind a Streamlit page

The submission form wants a live demo URL and offered Streamlit, but the wallet is a
FastAPI service. Rather than reimplement the wallet to look like a Streamlit app, this
runs stage-4's own src/app.py in a subprocess and drives it over HTTP: what a judge
clicks is the code in the repository, not a second program.

Streamlit reruns the whole script on every interaction and cannot hold an idempotency
key across a click, so a reimplementation was never going to work anyway.

src/ is copied from stage-4/src at build time and the build refuses to push if the copy
is not byte-identical, so the demo cannot drift from the submission.
MSG
echo "  $(git rev-list --count HEAD) commit, $(git ls-files | wc -l | tr -d ' ') files"

say "4/5  pushing"
if ! gh repo view "$REPO" >/dev/null 2>&1; then
  gh repo create "$REPO" --public --description \
    "Stage-4 demo for crytobot459/pocketful-factory: the unmodified FastAPI service the agent factory built, with a Streamlit page driving it over HTTP" >/dev/null
fi
git remote remove origin 2>/dev/null || true
git remote add origin "https://github.com/$REPO.git"
git push -q -u origin main
echo "  pushed: https://github.com/$REPO"

say "5/5  the one thing left is yours"
cat <<'EOF'

  1. https://share.streamlit.io -> "Deploy" -> "Deploy from GitHub"
  2. Pick crytobot459 / pocketful-demo, branch main. The file it looks for is
     streamlit_app.py at the root, which is already there.
  3. Wait for the build, then open the app and click through: Seed, Sign in as Ada,
     Fire it twice. If those three work, the demo URL is safe to paste into the form.

  The app sleeps on the free tier, so the first visit after a pause takes 30-60 seconds
  to wake. That is worth saying in the form rather than letting a judge assume it is broken.
EOF
