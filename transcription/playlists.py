#!/usr/bin/env python3
"""Keep the channel's year playlists ("Troy Board of Education — <year> Meetings") in
step with the meetings list.

  python3 transcription/playlists.py --add 3pJjVfmMOT4 --date 2026-09-01   # one video
  python3 transcription/playlists.py --sync                                # every MEETINGS row
  python3 transcription/playlists.py --sync --dry-run                      # report only

The four year playlists were built by hand in August 2026 and nothing in the
new-meeting chain added to them afterwards: 2026-08-18 and 2026-09-01 both went
up with transcript, captions and chapters and sat outside the 2026 playlist
until a QA pass noticed. Membership is read before writing (playlistItems.list,
1 unit a page) so a re-run is free; each insert is 50 units. A playlist that
already holds a different upload of the same meeting (same date in the title)
is reported, not added to — `--replace` swaps the old entry for the canonical id.
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import upload_captions as uc  # noqa: E402  (OAuth + http helper + MEETINGS)

API = "https://www.googleapis.com/youtube/v3"


def year_playlists(H):
    out = {}
    d = uc.http(f"{API}/playlists?part=snippet&mine=true&maxResults=50", headers=H)
    for p in d.get("items", []):
        t = p["snippet"]["title"]
        if t.startswith("Troy Board of Education") and "Meetings" in t:
            for tok in t.split():
                if tok.isdigit() and len(tok) == 4:
                    out[tok] = p["id"]
    return out


def members(H, pid):
    """{videoId: (playlistItemId, title)} for every entry in the playlist."""
    out, tok = {}, None
    while True:
        u = f"{API}/playlistItems?part=snippet&playlistId={pid}&maxResults=50" + (f"&pageToken={tok}" if tok else "")
        d = uc.http(u, headers=H)
        for i in d.get("items", []):
            out[i["snippet"]["resourceId"]["videoId"]] = (i["id"], i["snippet"]["title"])
        tok = d.get("nextPageToken")
        if not tok:
            return out


def delete_item(H, item_id):
    """playlistItems.delete answers 204 with no body; uc.http would try to parse it."""
    import urllib.request
    req = urllib.request.Request(f"{API}/playlistItems?id={item_id}", headers=H, method="DELETE")
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.status


def add(H, pid, vid):
    body = json.dumps({"snippet": {"playlistId": pid,
                                   "resourceId": {"kind": "youtube#video", "videoId": vid}}}).encode()
    uc.http(f"{API}/playlistItems?part=snippet", data=body,
            headers={**H, "content-type": "application/json"}, method="POST")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--add", metavar="VIDEO_ID")
    ap.add_argument("--date", help="YYYY-MM-DD, picks the year playlist for --add")
    ap.add_argument("--sync", action="store_true", help="add every MEETINGS video missing from its year playlist")
    ap.add_argument("--dedupe", action="store_true", help="drop other uploads of a meeting whose canonical id (MEETINGS) is already in the playlist")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--replace", action="store_true", help="swap out another upload of the same meeting already in the playlist")
    a = ap.parse_args()
    if not (a.add or a.sync or a.dedupe):
        ap.error("--add VIDEO --date DATE, --sync, or --dedupe")
    H = {"authorization": f"Bearer {uc.access_token()}"}
    lists = year_playlists(H)
    if a.dedupe:
        canon = {d: v for d, _k, v in uc.MEETINGS}
        removed = 0
        for y, pid in sorted(lists.items()):
            mem = members(H, pid)
            for vid, (iid, title) in list(mem.items()):
                date = title[:10]
                if date in canon and canon[date] != vid and canon[date] in mem:
                    print(f"{date} {vid}  other upload of a meeting whose canonical {canon[date]} is in the {y} playlist"
                          + ("  (dry run)" if a.dry_run else "  -> removed"))
                    if not a.dry_run:
                        delete_item(H, iid)
                        removed += 1
        print(f"removed {removed}")
        return 0
    jobs = [(a.date, a.add)] if a.add else [(d, v) for d, _k, v in uc.MEETINGS]
    if a.add and not a.date:
        ap.error("--add needs --date")
    have = {}
    added = 0
    for date, vid in jobs:
        y = date[:4]
        pid = lists.get(y)
        if not pid:
            print(f"{date} {vid}  NO PLAYLIST for {y} — create 'Troy Board of Education — {y} Meetings' first")
            continue
        if pid not in have:
            have[pid] = members(H, pid)
        if vid in have[pid]:
            continue
        # The playlist may already hold ANOTHER upload of the same meeting (the
        # channel had duplicate uploads before the August 2026 cleanup; the 2024
        # list carried three). Adding the canonical id then makes the meeting
        # appear twice. Report it, and only replace on request.
        twins = [(iid, ov, t) for ov, (iid, t) in have[pid].items() if t[:10] == date]
        if twins and not a.replace:
            for _iid, ov, t in twins:
                print(f"{date} {vid}  DUPLICATE: playlist already has {ov} '{t[:50]}' — pass --replace to swap")
            continue
        print(f"{date} {vid}  -> {y} playlist" + ("  (dry run)" if a.dry_run else ""))
        if not a.dry_run:
            add(H, pid, vid)
            have[pid][vid] = (None, date)
            added += 1
            for iid, ov, t in twins:
                delete_item(H, iid)
                del have[pid][ov]
                print(f"           removed the other upload {ov} '{t[:50]}'")
    print(f"added {added} · playlists: " + ", ".join(f"{y}={len(have.get(p, []))}" for y, p in sorted(lists.items()) if p in have))
    return 0


if __name__ == "__main__":
    sys.exit(main())
