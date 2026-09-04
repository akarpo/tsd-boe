#!/usr/bin/env python3
"""Build the workdir inputs the anchor tools read, for one meeting.

  python3 anchors/prep_meeting.py 2026-09-01                       # utterances from D1
  python3 anchors/prep_meeting.py 2026-09-01 --transcript T.json   # utterances from a local
                                                                   #   AssemblyAI transcript (before
                                                                   #   upload_transcript.py has run)

brief.py, coverage.py, qa_numbers.py and number_anchors.py all read a workdir
(`scratch/anchors-rebuild/`, or $ANCHORS_DATA) that is regenerable from D1 and
therefore not committed. Nothing wrote those files for a *new* meeting -- they
were exported once during the 2026-08 corpus rebuild -- so a meeting anchored
afterwards raised FileNotFoundError from brief.py, was skipped by
number_anchors.py (KeyError in the outline map, which is how 2026-08-18 shipped
with no agenda numbers), and had to be registered by hand in three files.
This writes all of them:

  agenda_outlines.json[date]   the published BoardDocs outline (fetch_agenda.outline)
  agendas.json[date]           {name, agenda:[{item,title}]} from that outline
  meetings.tsv                 date<TAB>meeting_name, appended once
  utts_<date>.json             [{start_ms,end_ms,speaker,text}] -- from D1 transcript_utts,
                               or from --transcript (names resolved through the sibling
                               <base>.speakers.json, or --speakers, if present)
  cur_<date>.json              [{start_ms,label,items}] from D1 transcript_anchors ([] if none)
"""
from __future__ import annotations
import argparse, json, subprocess, sys
from pathlib import Path
import os as _os

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
DATA = Path(_os.environ.get("ANCHORS_DATA") or (REPO / "scratch" / "anchors-rebuild"))
sys.path.insert(0, str(HERE))
import fetch_agenda  # noqa: E402


def d1(sql):
    r = subprocess.run(["npx", "wrangler", "d1", "execute", "tsd-boarddocs", "--remote",
                        "--json", "--command", sql], cwd=REPO, capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"D1 failed (rc={r.returncode}):\n  stdout: {r.stdout[:400]}\n  stderr: {r.stderr[:200]}")
    return json.loads(r.stdout)[0]["results"]


def meeting_name(date):
    for sql in (f"SELECT meeting_name FROM recordings WHERE meeting_date='{date}'",
                f"SELECT DISTINCT meeting_name FROM chunks WHERE meeting_date='{date}' AND id NOT LIKE 'sum:%'"):
        rows = d1(sql)
        if rows:
            return rows[0]["meeting_name"]
    u = json.load(open(REPO / "boarddocs_unids.json"))
    for m in u["meetings"].values():
        if m.get("date") == date:
            return m["name"].replace(":", " ")          # D1 form: "Workshop 6 00 PM"
    raise SystemExit(f"no meeting name for {date} in D1 or boarddocs_unids.json")


def utts_local(transcript, speakers):
    t = json.load(open(transcript))
    spec_path = Path(speakers) if speakers else Path(transcript).with_suffix("").with_suffix(".speakers.json")
    mapping, splits = {}, []
    if spec_path.exists():
        spec = json.load(open(spec_path))
        mapping, splits = spec.get("mapping", {}), spec.get("splits", [])
        for k, v in (spec.get("overrides") or {}).items():
            mapping[k] = v

    def name(x):
        for s in splits:
            if x["speaker"] == s["cluster"]:
                return s["before"] if x["start"] < s["at_ms"] else s["after"]
        return mapping.get(x["speaker"], x["speaker"])
    return [{"start_ms": x["start"], "end_ms": x["end"], "speaker": name(x), "text": x["text"]}
            for x in t["utterances"]]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("date")
    ap.add_argument("--transcript", help="local AssemblyAI transcript JSON (else read D1)")
    ap.add_argument("--speakers", help="speakers spec for --transcript (default: sibling .speakers.json)")
    a = ap.parse_args()
    date = a.date
    DATA.mkdir(parents=True, exist_ok=True)
    name = meeting_name(date)

    rows = fetch_agenda.outline(date)
    # The workdir copy is what the tools read; the copy committed next to them is
    # the fallback on a fresh checkout (qa_numbers._outlines), so keep both current.
    for p in (DATA / "agenda_outlines.json", HERE / "agenda_outlines.json"):
        ao = json.load(open(p)) if p.exists() else {}
        ao[date] = rows
        json.dump(ao, open(p, "w"), indent=1)
    p = DATA / "agendas.json"
    ag = json.load(open(p)) if p.exists() else {}
    ag[date] = {"name": name, "agenda": [{"item": r["item"], "title": f"{r['item']}. {r['title']}"} for r in rows]}
    json.dump(ag, open(p, "w"), indent=1)
    for p in (DATA / "meetings.tsv", HERE / "meetings.tsv"):
        known = {l.split("\t")[0] for l in open(p)} if p.exists() else set()
        if date not in known:
            with open(p, "a") as f:
                f.write(f"{date}\t{name}\n")

    if a.transcript:
        utts = utts_local(a.transcript, a.speakers)
        src = "local transcript"
    else:
        utts = d1(f"SELECT start_ms, end_ms, speaker, text FROM transcript_utts "
                  f"WHERE meeting_date='{date}' ORDER BY start_ms")
        src = "D1 transcript_utts"
    json.dump(utts, open(DATA / f"utts_{date}.json", "w"))
    cur = d1(f"SELECT start_ms, label FROM transcript_anchors WHERE meeting_date='{date}' ORDER BY start_ms")
    json.dump([{"start_ms": r["start_ms"], "label": r["label"], "items": []} for r in cur],
              open(DATA / f"cur_{date}.json", "w"))
    print(f"{date}  {name}\n  outline {len(rows)} rows · utts {len(utts)} ({src}) · anchors in D1 {len(cur)}")
    if not utts:
        print("  NOTE: no utterances — run upload_transcript.py first, or pass --transcript")


if __name__ == "__main__":
    sys.exit(main())
