#!/usr/bin/env python3
"""Regenerate bd_links.js (bundled into the Worker) from boarddocs_unids.json.

Run after any crawl that records new file identifiers. Writes the file in exactly
the committed layout — a header comment and three `export const` lines with
compact JSON — so a regeneration that adds nothing produces no diff. (The inline
snippet this replaces emitted a different layout, which made an unchanged map look
like a 4-line rewrite.)

  python3 scripts/gen_bd_links.py            # writes bd_links.js, prints what changed
"""
import json, re, sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BASE = "https://go.boarddocs.com/mi/troysd/Board.nsf/goto?open&id="


def build():
    u = json.load(open(REPO / "boarddocs_unids.json"))
    files, meetings = u["files"], u["meetings"]
    by_name, by_date_name = {}, {}
    for info in files.values():
        mu, nm = info["meeting_unid"], info["name"]
        md = meetings.get(mu, {}).get("date", "")
        by_name.setdefault(nm, set()).add(mu)
        by_date_name[f"{md}|{nm}"] = mu
    by_name_u = {n: sorted(v)[0] for n, v in by_name.items() if len(v) == 1}
    return by_date_name, by_name_u


def parse(text):
    out = {}
    for line in text.splitlines():
        m = re.match(r"export const (\w+) = (\{.*\});$", line)
        if m:
            out[m.group(1)] = json.loads(m.group(2))
    return out


def main():
    p = REPO / "bd_links.js"
    old = parse(p.read_text()) if p.exists() else {}
    dn, nu = build()
    p.write_text(
        "// Generated from boarddocs_unids.json — maps a doc to its BoardDocs meeting UNID.\n"
        f'export const BD_BASE = "{BASE}";\n'
        "export const BD_BY_DATENAME = " + json.dumps(dn, separators=(",", ":")) + ";\n"
        "export const BD_BY_NAME = " + json.dumps(nu, separators=(",", ":")) + ";\n")
    for key, new in (("BD_BY_DATENAME", dn), ("BD_BY_NAME", nu)):
        o = old.get(key, {})
        added = [k for k in new if k not in o]
        removed = [k for k in o if k not in new]
        changed = [k for k in new if k in o and o[k] != new[k]]
        print(f"{key}: {len(o)} -> {len(new)}  +{len(added)} -{len(removed)} ~{len(changed)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
