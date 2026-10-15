"""USDA MARS API - daily automator: ingest every report, push Database/ to GitHub, email a status report.

    python run_update.py              # full run
    python run_update.py --no-email   # skip the email (print only)
    python run_update.py --no-push    # skip git
Exit code 0 = everything OK, 1 = an ingest or the push failed.
"""
import argparse
import contextlib
import html
import io
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mars_ingest as m  # noqa: E402

ROOT = m.ROOT
EMAIL_TO = "virat.arya@etgworld.com"
GROUPS = [
    ("CLASSING", ["1652", "1625"]),
    ("QUALITY", ["1654_colorleaf", "1654_summary"]),
    ("SPOT", ["3804_basis", "3804_futures", "3895_monthly"]),
    ("FORWARD CONTRACTING", ["1613"]),
]
LABEL = {
    "1652": "Classing by State", "1625": "Classing by Office", "1654_colorleaf": "Colour & Leaf (weekly)",
    "1654_summary": "Tenderable / Eligible (weekly)", "3804_basis": "Spot Basis & Bales (daily)",
    "3804_futures": "ICE CT Settlements (daily)", "3895_monthly": "Spot Monthly Averages", "1613": "Forward Contracting",
}
DATECOL = {"1652": "endDate", "1625": "endDate", "3804_basis": "report_Begin_Date", "3804_futures": "report_Begin_Date",
           "1613": "report_end_date", "1654_colorleaf": "report_end_date", "1654_summary": "report_end_date",
           "3895_monthly": "report_Begin_Date"}
STALE_OK = {"1652": 3, "1625": 3, "3804_basis": 4, "3804_futures": 4, "1654_colorleaf": 10, "1654_summary": 10,
            "1613": 45, "3895_monthly": 55}


def snapshot(name):
    path = m.DB_DIR / m.REPORTS[name]["file"]
    if not path.exists():
        return dict(ok=False, note="no file")
    df = pd.read_parquet(path, columns=[DATECOL[name]])
    d = df[DATECOL[name]].dropna()
    return dict(ok=True, rows=len(df), first=d.min().date(), last=d.max().date(),
                stale=(pd.Timestamp.today().normalize() - d.max().normalize()).days)


def run_ingests():
    results = {}
    session = requests.Session()
    session.auth = (m.load_key(), "")
    for name, cfg in m.REPORTS.items():
        before = snapshot(name).get("rows", 0)
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                m.run(name, cfg, session, False, None)
            ok = True
        except Exception as e:
            buf.write(f"\nFAILED: {e}")
            ok = False
        out = buf.getvalue()
        print(out)
        results[name] = dict(ok=ok, out=out, added=snapshot(name).get("rows", 0) - before)
    return results


def git(*args, timeout=120):
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0", GCM_INTERACTIVE="never")
    try:
        r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, timeout=timeout, env=env)
        return r.returncode, (r.stdout + r.stderr).strip()
    except subprocess.TimeoutExpired:
        return 124, f"git {' '.join(args)} timed out after {timeout}s"


def publish():
    log = []
    rc, out = git("add", "Database")
    log.append(out)
    changed = git("diff", "--cached", "--quiet")[0] == 1
    if changed:
        rc, out = git("commit", "-q", "-m", f"MARS update {datetime.now():%Y-%m-%d}")
        log.append(out)
        if rc != 0:
            return dict(status="FAILED", log="\n".join(log))
    rc, out = git("push", "origin", "main")
    log.append(out)
    if rc != 0:
        return dict(status="FAILED", log="\n".join(log))
    head = git("rev-parse", "HEAD")[1]
    remote = git("ls-remote", "origin", "refs/heads/main")[1].split()
    if not remote or remote[0] != head:
        log.append(f"remote {remote[:1]} != local {head}")
        return dict(status="FAILED", log="\n".join(log))
    log.append(git("log", "-3", "--format=%h %ad %s", "--date=format:%d-%b %H:%M")[1])
    return dict(status="pushed" if changed else "nochange", log="\n".join(x for x in log if x))


# ── email (Outlook renders with Word: inline styles + plain tables only) ─────
F = "font-family:Calibri,Arial,sans-serif"
TH = "padding:6px 10px;border:1px solid #ccc;background:#0a2463;color:#fff;font-size:12px;text-align:left;white-space:nowrap;"
TD = "padding:6px 10px;border:1px solid #ccc;font-size:12px;white-space:nowrap;"
GH = ("padding:5px 10px;background:#dfe3ee;color:#0a2463;font-size:11.5px;font-weight:700;"
      "text-transform:uppercase;letter-spacing:.04em;border:1px solid #ccc;")


def status_table(results):
    rows = []
    for group, names in GROUPS:
        rows.append(f'<tr><td colspan="6" style="{GH}">{group}</td></tr>')
        for n in names:
            s, r = snapshot(n), results.get(n, {})
            if not s["ok"]:
                rows.append(f'<tr><td style="{TD}"><b>{LABEL[n]}</b></td><td style="{TD}">MARS API</td>'
                            f'<td style="{TD};color:#a3271f" colspan="4">{s["note"]}</td></tr>')
                continue
            lim = STALE_OK[n]
            if s["stale"] <= lim:
                st, sc = "OK", "#3c7a41"
            elif s["stale"] <= lim * 3:
                st, sc = f"{s['stale']}d stale", "#b4590c"
            else:
                st, sc = f"{s['stale']}d STALE", "#a3271f"
            ok = r.get("ok")
            run = ("OK" + (f" +{r['added']:,}" if r.get("added") else "")) if ok else "FAILED" if ok is False else "not run"
            rc = "#3c7a41" if ok else "#a3271f"
            rows.append(
                f'<tr><td style="{TD}"><b>{LABEL[n]}</b></td><td style="{TD}">MARS API</td><td style="{TD}">{s["rows"]:,}</td>'
                f'<td style="{TD}">{s["first"]} &ndash; {s["last"]}</td><td style="{TD};color:{sc}"><b>{st}</b></td>'
                f'<td style="{TD};color:{rc}"><b>{run}</b></td></tr>')
    head = "".join(f'<th style="{TH}">{h}</th>' for h in ["Pipeline", "Source", "Rows", "Date Range", "Status", "This Run"])
    return (f'<table style="border-collapse:collapse;{F}"><thead><tr>{head}</tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table>')


def headline():
    """One line: latest US Upland classing day and season to date vs prior-4 average."""
    try:
        d = pd.read_parquet(m.DB_DIR / "mars_1625.parquet")
        d = d[d["classing_Office"].isin(["United States", "United States All Cotton"]) & (d["period"] == "Daily")
              & (d["commodity"] == "Upland")].sort_values("published_date").drop_duplicates("endDate", keep="last")
        s = d.set_index("endDate")["numberofBales"].dropna().sort_index()
        share = (s.groupby(s.index.month).sum() / s.sum()).reindex(range(1, 13), fill_value=0)
        sm = int(share.idxmin())
        while share[sm % 12 + 1] < 0.01:
            sm = sm % 12 + 1
        sm = sm % 12 + 1
        last = s.index.max()
        cy = last.year if last.month >= sm else last.year - 1
        off = (last - pd.Timestamp(cy, sm, 1)).days

        def ytd(c):
            a = pd.Timestamp(c, sm, 1)
            return s[(s.index >= a) & (s.index <= a + pd.Timedelta(days=off))].sum()
        cur = ytd(cy)
        pr = [ytd(c) for c in range(cy - 4, cy)]
        vs = f" ({cur / (sum(pr) / len(pr)) - 1:+.1%} vs prior-4 avg)" if sum(pr) else ""
        return (f"<b>US Upland</b> : {s.iloc[-1]:,.0f} bales classed on {last:%a %d-%b} &nbsp;|&nbsp; "
                f"<b>Season {cy}/{str(cy + 1)[2:]} to date</b> : {cur:,.0f}{vs}")
    except Exception as e:
        return f"Headline unavailable: {html.escape(str(e))}"


def build_email(results, pub):
    pc = {"pushed": "#3c7a41", "nochange": "#3c7a41"}.get(pub["status"], "#a3271f")
    plabel = {"pushed": "Pushed to GitHub", "nochange": "No new data to push"}.get(pub["status"], "PUSH FAILED")
    fails = [f'<p style="{F};font-size:13px;margin:14px 0 4px"><b>{LABEL[n]}</b> <span style="color:#a3271f">(FAILED)</span></p>'
             f'<pre style="background:#f5f5f5;border:1px solid #ddd;padding:8px;font-size:11px;white-space:pre-wrap;'
             f'font-family:Consolas,monospace">{html.escape(r["out"].strip()[-3000:])}</pre>'
             for n, r in results.items() if not r["ok"]]
    return f"""
    <div style="{F};font-size:14px;color:#1a1a1a">
      <h2 style="{F};font-size:16px;margin:0 0 4px;color:#0a2463">USDA MARS API &mdash; Daily Update</h2>
      <p style="{F};font-size:12px;color:#666;margin:0 0 12px">Run {datetime.now():%d %b %Y %H:%M}</p>
      <p style="{F};font-size:13px;margin:0 0 14px">{headline()}</p>
      <p style="{F};font-size:13px;margin:0 0 14px"><b>GitHub</b> : <span style="color:{pc}"><b>{plabel}</b></span></p>
      {status_table(results)}
      <p style="{F};font-size:13px;margin:16px 0 4px"><b>Git log</b></p>
      <pre style="background:#f5f5f5;border:1px solid #ddd;padding:8px;font-size:11px;white-space:pre-wrap;
        font-family:Consolas,monospace">{html.escape(pub["log"].strip()[-3000:])}</pre>
      {'<h3 style="' + F + ';font-size:13px;margin:20px 0 4px">Failures</h3>' + ''.join(fails) if fails else ''}
    </div>"""


def send_email(subject, body):
    import win32com.client
    ol = win32com.client.Dispatch("Outlook.Application")
    mail = ol.CreateItem(0)
    mail.To = EMAIL_TO
    mail.Subject = subject
    mail.HTMLBody = body
    mail.Send()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-email", action="store_true")
    ap.add_argument("--no-push", action="store_true")
    a = ap.parse_args()
    results = run_ingests()
    pub = dict(status="nochange", log="push skipped") if a.no_push else publish()
    failed = [n for n, r in results.items() if not r["ok"]]
    status = ("PARTIAL FAIL" if failed else "OK") if pub["status"] != "FAILED" else "PUSH FAILED"
    subject = f"USDA MARS API - {status} - {datetime.now():%d %b %Y}"
    body = build_email(results, pub)
    print(subject)
    if not a.no_email:
        try:
            send_email(subject, body)
            print("email sent")
        except Exception as e:
            print(f"email failed: {e}")
    else:
        (ROOT / "logs").mkdir(exist_ok=True)
        (ROOT / "logs" / "last_email.html").write_text(body, encoding="utf-8")
    sys.exit(1 if status != "OK" else 0)


if __name__ == "__main__":
    main()
