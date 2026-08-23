"""Convert local Word/PowerPoint sources to PDF and upload each as <r2-key>.pdf so
the site can preview them inline. Excel is intentionally skipped (the viewer links
those out). Resumable via a done-list; re-run to pick up new files.

  TSD_BOE_ROOT=<repo>/data/tsd-boe-data python scripts/convert_office.py
  python scripts/convert_office.py --verify [--since YYYY-MM-DD] [--repair]

The ingest-worker secret comes from tsd_secrets (env var, else the secrets file
outside the repo), the same as every other uploader. It used to be read straight
from os.environ, which meant step 6 of ingest_meeting.sh uploaded with an empty
secret and every PUT came back 403 -- silently, because the failures print per
file and the run still exits 0.
"""
import os, sys, shutil, tempfile, subprocess, urllib.request, urllib.parse
import concurrent.futures as _cf
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import tsd_secrets

ROOT = Path(os.environ.get("TSD_BOE_ROOT") or
        Path(__file__).resolve().parent.parent / "data" / "tsd-boe-data")
SOFFICE = os.environ.get("SOFFICE", "/opt/homebrew/bin/soffice")
R2PUT = "https://tsd-ingest.akarpo.workers.dev/r2put"
SECRET = tsd_secrets.require("R2PUT_SECRET")
PREFIX = "troysd-boarddocs"
EXTS = (".docx", ".doc", ".pptx", ".ppt")
DONE = ROOT / "_index" / "converted_pdf.done"
BATCH = 30


def r2key(src: Path) -> str:
    return f"{PREFIX}/{src.relative_to(ROOT).as_posix()}.pdf"   # <meeting>/<file.docx>.pdf


def upload(pdf: Path, key: str):
    u = R2PUT + "?key=" + urllib.parse.quote(key, safe="") + "&secret=" + urllib.parse.quote(SECRET)
    req = urllib.request.Request(u, data=pdf.read_bytes(), method="PUT",
                                 headers={"user-agent": "Mozilla/5.0", "content-type": "application/pdf"})
    urllib.request.urlopen(req, timeout=180).read()


R2GET = "https://media.karpowitsch.org/"


def in_r2(src: Path) -> tuple[Path, bool]:
    """HEAD the preview PDF. R2 is the only honest answer here.

    The done-list cannot answer it: on 2026-08-22 it was empty while 1,447 of
    1,452 previews were present, and it has also been *fuller* than the corpus
    after a seeding bug wrote relative paths that matched nothing. Derived state
    that can be wrong in both directions is not a coverage check.
    """
    url = R2GET + urllib.parse.quote(r2key(src))
    try:
        req = urllib.request.Request(url, method="HEAD", headers={"user-agent": "Mozilla/5.0"})
        return src, urllib.request.urlopen(req, timeout=25).status == 200
    except Exception:
        return src, False


def office_files():
    return [p for p in ROOT.rglob("*") if p.suffix.lower() in EXTS
            and not any(x.startswith("_") for x in p.relative_to(ROOT).parts)]


def verify(since="", repair=False) -> int:
    """Report every Office document with no preview PDF in R2.

    --since scopes to meeting folders on or after a date, which is what the
    ingest wrapper passes: probing the whole corpus takes about a minute and
    only the meetings just ingested can have regressed.
    """
    files = [p for p in office_files()
             if not since or p.relative_to(ROOT).parts[0][:10] >= since]
    if not files:
        print(f"preview check: no Office documents on/after {since}")
        return 0
    have, missing = [], []
    with _cf.ThreadPoolExecutor(max_workers=24) as ex:
        for src, ok in ex.map(in_r2, files):
            (have if ok else missing).append(src)
    scope = f" on/after {since}" if since else ""
    print(f"preview check{scope}: {len(have)}/{len(files)} Office documents have a preview PDF")
    if repair:
        prior = {l for l in (DONE.read_text().splitlines() if DONE.exists() else []) if l.strip()}
        merged = sorted({str(p) for p in have} | {l for l in prior if Path(l).is_absolute()})
        DONE.write_text("\n".join(merged) + "\n")
        print(f"  done-list rebuilt from R2: {len(merged)} entries")
    if missing:
        print(f"  MISSING {len(missing)} preview(s) — the viewer cannot render these inline:")
        for p in missing[:20]:
            print(f"    {p.relative_to(ROOT)}")
        if len(missing) > 20:
            print(f"    … and {len(missing)-20} more")
        print("  fix: python3 scripts/convert_office.py   (then re-run --verify)")
        return 1
    return 0


def main():
    if "--verify" in sys.argv:
        since = ""
        if "--since" in sys.argv:
            since = sys.argv[sys.argv.index("--since") + 1]
        return verify(since, repair="--repair" in sys.argv)
    # The done-list holds ABSOLUTE paths, because ROOT is resolved absolute above.
    # Seeding it with relative paths silently matches nothing and re-converts the
    # whole corpus -- 1,452 files re-rendered and re-uploaded to replace identical
    # bytes. Normalise on read so either form works.
    done = {str(Path(l) if Path(l).is_absolute() else (ROOT.parent.parent / l))
            for l in (DONE.read_text().splitlines() if DONE.exists() else []) if l.strip()}
    files = [p for p in ROOT.rglob("*") if p.suffix.lower() in EXTS
             and not any(x.startswith("_") for x in p.relative_to(ROOT).parts)]
    todo = [p for p in files if str(p) not in done]
    print(f"total {len(files)}  done {len(done)}  to convert {len(todo)}", flush=True)
    n_ok = n_fail = 0
    with DONE.open("a") as donef:
        for i in range(0, len(todo), BATCH):
            batch = todo[i:i + BATCH]
            tin, tout = Path(tempfile.mkdtemp()), Path(tempfile.mkdtemp())
            mapping = {}
            for j, f in enumerate(batch):                       # unique names to avoid same-stem collisions
                uname = f"{i+j}__{f.stem}{f.suffix}"
                try: shutil.copy(f, tin / uname); mapping[f"{i+j}__{f.stem}"] = f
                except Exception as e: print("copy fail", f.name, str(e)[:50], flush=True)
            try:
                subprocess.run([SOFFICE, "--headless", "--convert-to", "pdf", "--outdir", str(tout)]
                               + [str(p) for p in tin.iterdir()], capture_output=True, timeout=1200)
            except Exception as e:
                print("soffice batch error:", str(e)[:80], flush=True)
            for ustem, f in mapping.items():
                pdf = tout / (ustem + ".pdf")
                if pdf.exists() and pdf.stat().st_size > 0:
                    try: upload(pdf, r2key(f)); donef.write(str(f) + "\n"); donef.flush(); n_ok += 1
                    except Exception as e: print("upload fail", f.name, str(e)[:60], flush=True); n_fail += 1
                else:
                    print("no pdf produced:", f.name, flush=True); n_fail += 1
            shutil.rmtree(tin, ignore_errors=True); shutil.rmtree(tout, ignore_errors=True)
            print(f"  progress: {n_ok} ok, {n_fail} failed / {len(todo)}", flush=True)
    print(f"DONE: converted+uploaded {n_ok}, failed {n_fail}", flush=True)


if __name__ == "__main__":
    sys.exit(main() or 0)
