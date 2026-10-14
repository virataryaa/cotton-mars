"""USDA MARS API - ingest report 1652 (Daily Cotton Quality Summary by State).

Each daily report re-publishes a rolling window of Daily/Weekly/Season rows, so the
same (period, commodity, state, startDate, endDate) appears many times. We keep the
latest published version of each.

    python mars_ingest.py              # incremental (last stored report date - OVERLAP_DAYS)
    python mars_ingest.py --backfill   # full history from BACKFILL_START in 1-year chunks
Key: MARS_API_KEY env var or ../.env
"""
import argparse
import os
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "Database" / "mars_1652.parquet"
SLUG_ID = 1652
BASE_URL = "https://marsapi.ams.usda.gov/services/v1.2/reports"
BACKFILL_START = date(2018, 11, 1)
OVERLAP_DAYS = 14
KEY = ["period", "commodity", "classing_State", "startDate", "endDate"]
NUM = ["numberofBales", "predominateColor", "predominateColorPct", "predominateLeaf",
       "predominateLeafPct", "avgLeaf", "avgMike", "avgStaple", "avgLength", "avgStrength",
       "avgUniformity", "avgTrash", "avgLoanPD", "pctBark", "pctGrass", "pctTenderable",
       "numberofGins"]
KEEP = ["report_begin_date", "published_date", "office_code", "office_name", "commodity",
        "period", "startDate", "endDate", "classing_State"] + NUM


def load_key():
    if os.environ.get("MARS_API_KEY"):
        return os.environ["MARS_API_KEY"]
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.startswith("MARS_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    sys.exit("MARS_API_KEY not found (env var or .env)")


def fetch(session, start, end, retries=3):
    params = {"q": f"report_begin_date={start:%m/%d/%Y}:{end:%m/%d/%Y}", "allSections": "true"}
    for a in range(1, retries + 1):
        try:
            r = session.get(f"{BASE_URL}/{SLUG_ID}", params=params, timeout=180)
            r.raise_for_status()
            return r.json()
        except requests.RequestException as e:
            print(f"  attempt {a} failed: {e}")
            time.sleep(5 * a)
    raise RuntimeError(f"Failed {start} -> {end}")


def to_frame(payload):
    secs = payload if isinstance(payload, list) else [payload]
    rows = [r for s in secs for r in s.get("results", [])]
    return pd.DataFrame(rows)


def clean(df):
    if df.empty:
        return df
    df = df[[c for c in KEEP if c in df.columns]].copy()
    for c in NUM:
        df[c] = pd.to_numeric(df[c].replace({"*": None, "-": None, "": None}), errors="coerce")
    for c in ["report_begin_date", "startDate", "endDate"]:
        df[c] = pd.to_datetime(df[c], format="%m/%d/%Y", errors="coerce")
    df["published_date"] = pd.to_datetime(df["published_date"], errors="coerce")
    return df


def upsert(old, new):
    df = pd.concat([old, new], ignore_index=True) if old is not None else new
    df = df.sort_values("published_date").drop_duplicates(KEY, keep="last")
    return df.sort_values(["period", "commodity", "classing_State", "endDate"]).reset_index(drop=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backfill", action="store_true")
    ap.add_argument("--limit-days", type=int, help="test: only fetch the last N days")
    a = ap.parse_args()

    old = pd.read_parquet(DB_PATH) if DB_PATH.exists() else None
    end = date.today()
    if a.limit_days:
        start = end - timedelta(days=a.limit_days)
    elif a.backfill or old is None:
        start = BACKFILL_START
    else:
        start = old["report_begin_date"].max().date() - timedelta(days=OVERLAP_DAYS)

    s = requests.Session()
    s.auth = (load_key(), "")
    frames, cur = [], start
    while cur <= end:
        e = min(date(cur.year + 1, cur.month, cur.day) - timedelta(days=1), end)
        print(f"Fetching {cur} -> {e} ...")
        f = to_frame(fetch(s, cur, e))
        print(f"  {len(f)} rows")
        frames.append(f)
        cur = e + timedelta(days=1)

    new = clean(pd.concat(frames, ignore_index=True))
    if new.empty:
        sys.exit("No data returned.")
    out = upsert(old, new)
    DB_PATH.parent.mkdir(exist_ok=True)
    out.to_parquet(DB_PATH, index=False)
    print(f"Saved {len(out)} rows (added {len(out) - (0 if old is None else len(old))}) -> {DB_PATH}")
    print(f"Latest endDate: {out['endDate'].max():%Y-%m-%d}  latest report: {out['report_begin_date'].max():%Y-%m-%d}")


if __name__ == "__main__":
    main()
