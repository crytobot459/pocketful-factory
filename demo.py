#!/usr/bin/env python3
"""Narrate this factory, in English, from its own evidence.

One command, no keys:

    python3 demo.py              # print, and speak each section aloud
    python3 demo.py --quiet      # print only
    python3 demo.py --no-speak   # print only, and say why it is not speaking

Everything it says is read out of `room.json`, the git history and the harness report under
`docs/harness-runs/`. Nothing is hard-coded except the sentence templates, so if a number
changes in the evidence it changes here too.

Speech is `edge-tts`, which is free and needs no key. If it is not installed the demo prints
and carries on: a missing narrator is never a reason for the demo to fail.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent
ROOM = ROOT / "room.json"
RUNS = ROOT / "docs" / "harness-runs"
VOICE = "en-US-AriaNeural"


# --- evidence ---------------------------------------------------------------

def room_stats() -> dict:
    if not ROOM.is_file():
        return {}
    msgs = json.loads(ROOM.read_text()).get("messages", [])
    texts = [m for m in msgs if m.get("messageType") == "text"]
    by_seat: dict[str, int] = {}
    for m in texts:
        name = m.get("senderName", "?")
        by_seat[name] = by_seat.get(name, 0) + 1
    tokens_in = tokens_out = 0
    for m in msgs:
        hit = re.match(r"Token usage: input=(\d+) output=(\d+)", str(m.get("content", "")))
        if hit:
            tokens_in += int(hit.group(1))
            tokens_out += int(hit.group(2))
    stamps = sorted(m.get("inserted_at") or "" for m in msgs if m.get("inserted_at"))
    accept = reject = 0
    for m in texts:
        head = " ".join(str(m.get("content", "")).split())[:90]
        if re.match(r"^(@\S+\s+)*ACCEPT\b", head):
            accept += 1
        elif re.match(r"^(@\S+\s+)*REJECT\b", head):
            reject += 1
    return {
        "messages": len(msgs),
        "texts": len(texts),
        "by_seat": by_seat,
        "accept": accept,
        "reject": reject,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "first": stamps[0][:16] if stamps else "",
        "last": stamps[-1][:16] if stamps else "",
    }


def stage_claims() -> list[tuple[str, bool, float]]:
    """(folder, claimed, share) per stage, newest harness summary first."""
    out = []
    for summary in sorted(RUNS.glob("*/summary.json"), reverse=True):
        data = json.loads(summary.read_text())
        for stage, info in sorted(data.get("folders", {}).items()):
            out.append((f"stage-{stage}", bool(info.get("claimed")),
                        float(info.get("share") or 0.0)))
        if out:
            return out
    return out


def git_revisions() -> list[str]:
    try:
        text = subprocess.run(["git", "log", "--format=%s", "--", "stage-1", "stage-2",
                               "stage-3", "stage-4"],
                              cwd=ROOT, capture_output=True, text=True, timeout=20).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    return [line for line in text.splitlines()
            if re.match(r"pocketful stage-\d", line)]


# --- narration --------------------------------------------------------------

def build_sections() -> list[tuple[str, str]]:
    stats = room_stats()
    claims = stage_claims()
    revisions = git_revisions()
    seats = sorted(stats.get("by_seat", {}))

    lines: list[tuple[str, str]] = []

    def add(title: str, text: str) -> None:
        lines.append((title, text))

    add("What this is", "Three coding agents in one room. One decomposes a stage of a written "
                        "specification, one implements it, and one checks that exact revision "
                        "and can veto it. Once a stage is dispatched, no human is in the loop "
                        "until the stage is locked.")

    if seats:
        spoken = ", ".join(s.replace("factory-", "").replace("-df", "") for s in seats)
        add("The seats", f"{len(seats)} seats: {spoken}. The first two share a model. The "
                         f"reviewer does not, on purpose, because a reviewer sharing the "
                         f"implementer's blind spot is not a reviewer.")

    if stats:
        per = ", ".join(f"{n} from {s.replace('factory-', '').replace('-df', '')}"
                        for s, n in sorted(stats["by_seat"].items(), key=lambda kv: -kv[1]))
        add("The room", f"{stats['messages']} messages. {stats['texts']} of them are the agents "
                        f"themselves: {per}. Every one carries a revision, a count or a "
                        f"decision, because a filler message is a message that costs points.")
        add("The verdicts", f"{stats['accept']} acceptances and {stats['reject']} rejections. "
                            f"The reviewer wrote its own scenarios, the ones the published "
                            f"checks never asked for, and the implementer was not allowed to "
                            f"read them.")

    if revisions:
        stages = sorted({re.search(r"stage-(\d)", r).group(1) for r in revisions if
                         re.search(r"stage-(\d)", r)})
        span = (f"stage {stages[0]}" if len(stages) == 1
                else f"stages {stages[0]} through {stages[-1]}")
        add("What it built", f"{len(stages)} stages of a wallet service, each one a complete "
                            f"program that builds on its own and still passes every stage "
                            f"before it. {span.capitalize()}.")

    if claims:
        claimed = [c for c, ok, _ in claims if ok]
        shares = {s for _, _, s in claims if s}
        add("Verified", f"The event's own harness, in isolated mode, built every folder from a "
                        f"clean container. {len(claimed)} of {len(claims)} claim their stage"
                        + (f", each at share {max(shares):.0%}" if shares else "")
                        + ". Not our word: the organiser's own report is committed in the "
                          "repository, under the folder named harness-runs.")

    if stats.get("tokens_in"):
        add("What it cost", f"Zero dollars; every seat ran on a free tier. The room log records "
                            f"{stats['tokens_in']:,} input tokens and "
                            f"{stats['tokens_out']:,} output tokens, all attributed to one "
                            f"seat, so that is a floor rather than a total.")

    add("Where it broke", "A seat checked out a revision to review it, which moved the branch "
                         "tip and stranded a commit. That happened twice. One turn hit its "
                         "deadline part-way through the last stage and had to be re-dispatched. "
                         "And the room downloader silently returned half the room, so the log "
                         "looked like it proved nothing when it was the script. All three are "
                         "written up in the factory document, because that is what saves the "
                         "next team the day.")

    add("Close", "The factory is three mandates, three adapters and one room. Point it at a "
                 "different specification and the routing, the veto and the discipline carry "
                 "over unchanged.")
    return lines


# --- speech -----------------------------------------------------------------

def speak_lines(lines: list[str], voice: str = VOICE,
                keep: pathlib.Path | None = None) -> tuple[int, str]:
    """Speak each line in turn, and optionally keep the audio for the video.

    Returns (lines spoken, note). The note is empty on a clean run and says what
    happened otherwise; speech failing is never fatal.
    """
    try:
        import asyncio

        import edge_tts
    except Exception:
        return 0, "edge-tts is not installed; run `pip install edge-tts` for the narration"

    import tempfile

    out = pathlib.Path(keep) if keep else pathlib.Path(tempfile.mkdtemp(prefix="pf-demo-"))
    out.mkdir(parents=True, exist_ok=True)
    player = next((p for p in ("afplay", "mpv", "ffplay") if _which(p)), None)
    played = 0
    for number, text in enumerate(lines, 1):
        path = out / f"{number:02d}.mp3"
        try:
            asyncio.run(edge_tts.Communicate(text, voice).save(str(path)))
        except Exception as exc:                       # network down, voice refused, whatever
            return played, f"speech stopped after {played} line(s): {exc}"
        if player is None:
            return played, f"{out} written; no player found to play it"
        if subprocess.run([player, str(path)], capture_output=True).returncode != 0:
            return played, f"could not play {path}"
        played += 1
    return played, (f"audio kept in {out}" if keep else "")


def _which(program: str) -> str | None:
    from shutil import which

    return which(program)


# --- main -------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--quiet", action="store_true", help="print only, never speak")
    parser.add_argument("--no-speak", action="store_true",
                        help="print only, and report why it is not speaking")
    parser.add_argument("--voice", default=VOICE)
    parser.add_argument("--save", metavar="DIR",
                        help="keep the audio as numbered mp3 files, for the video")
    args = parser.parse_args()

    sections = build_sections()
    spoken: list[str] = []
    for i, (title, text) in enumerate(sections, 1):
        print(f"\n{i}. {title}\n   {' '.join(text.split())}")
        spoken.append(text)

    want_speech = not (args.quiet or args.no_speak)
    if want_speech:
        print(f"\nSpeaking as {args.voice} ...", flush=True)
        played, note = speak_lines(spoken, args.voice,
                                   pathlib.Path(args.save) if args.save else None)
        if note:
            print(f"   {note}")
        print(f"   spoke {played} of {len(spoken)} section(s)")
    elif args.no_speak:
        print("\n--no-speak given, so nothing was said.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())