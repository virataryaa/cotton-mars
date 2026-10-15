"""USDA MARS API - ingest cotton reports into Database/*.parquet.

    python mars_ingest.py                    # incremental, all reports
    python mars_ingest.py --report 1652      # one report (see REPORTS)
    python mars_ingest.py --backfill         # full history from each report's start
Key: MARS_API_KEY env var or ../.env

Reports re-publish rolling windows, so each table keeps the latest published row per KEY.
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
DB_DIR = ROOT / "Database"
BASE_URL = "https://marsapi.ams.usda.gov/services/v1.2/reports"
OVERLAP_DAYS = 14
BLANKS = {"*": None, "-": None, "": None, "N/A": None}

QUALITY = ["numberofBales", "predominateColor", "predominateColorPct", "predominateLeaf",
           "predominateLeafPct", "avgLeaf", "avgMike", "avgStaple", "avgLength", "avgStrength",
           "avgUniformity", "avgTrash", "avgLoanPD", "pctBark", "pctGrass", "pctTenderable",
           "numberofGins"]
QUALITY_KEEP = ["report_begin_date", "published_date", "office_code", "office_name", "commodity",
                "period", "startDate", "endDate"]

# name -> config. section=None means the whole report; chunk_months sets request size.
REPORTS = {
    "1652": dict(file="mars_1652.parquet", slug=1652, section=None, start=date(2018, 11, 1), chunk_months=12,
                 key=["period", "commodity", "classing_State", "startDate", "endDate"],
                 keep=QUALITY_KEEP + ["classing_State"] + QUALITY, num=QUALITY, ts="published_date",
                 sort=["period", "commodity", "classing_State", "endDate"],
                 desc="Daily Cotton Quality Summary by State"),
    "1625": dict(file="mars_1625.parquet", slug=1625, section=None, start=date(2015, 1, 1), chunk_months=12,
                 key=["period", "commodity", "classing_Office", "startDate", "endDate"],
                 keep=QUALITY_KEEP + ["classing_Office"] + QUALITY, num=QUALITY, ts="published_date",
                 sort=["period", "commodity", "classing_Office", "endDate"],
                 desc="Daily Cotton Quality Summary by Office"),
    "3804_basis": dict(file="mars_3804_basis.parquet", slug=3804, section="Basis and Bales",
                       start=date(2024, 6, 1), chunk_months=3,
                       key=["commodity", "spotMarket", "report_Begin_Date"],
                       keep=None, num=["basis_41_4_34", "41_4_34_Base_Price", "basis_31_3_36", "31_3_36_Base_Price",
                                       "bales_Reported"], ts=None, sort=["commodity", "spotMarket", "report_Begin_Date"],
                       desc="Daily Spot Cotton - basis and bales by spot market"),
    "3804_futures": dict(file="mars_3804_futures.parquet", slug=3804, section="ICE CN Futures Settlement Prices",
                         start=date(2024, 6, 1), chunk_months=3,
                         key=["report_Begin_Date", "contract"], keep=None, num=["settlement_Price"], ts=None,
                         sort=["report_Begin_Date", "contract"], desc="Daily Spot Cotton - ICE CT settlements"),
    "1613": dict(file="mars_1613.parquet", slug=1613, section=None, start=date(2015, 1, 1), chunk_months=12,
                 key=["market_location_name", "commodity", "report_begin_date", "report_end_date"],
                 keep=None, num=None, ts="published_date", sort=["market_location_name", "commodity", "report_begin_date"],
                 desc="Forward Contracting Report (monthly)"),
    "1654_colorleaf": dict(file="mars_1654_colorleaf.parquet", slug=1654, section="Color Leaf",
                           start=date(2015, 1, 1), chunk_months=12,
                           key=["commodity", "gin_State", "color_Grade", "leaf_Grade", "report_end_date"],
                           keep=None, num=["week_Percent", "season_Percent"], ts="published_date",
                           sort=["commodity", "gin_State", "report_end_date", "color_Grade", "leaf_Grade"],
                           desc="Weekly Quality by State - colour/leaf % (week and season)"),
    "1654_summary": dict(file="mars_1654_summary.parquet", slug=1654, section="Summary",
                         start=date(2015, 1, 1), chunk_months=12,
                         key=["commodity", "gin_State", "report_Period", "report_end_date"],
                         keep=None, num=["gin_Count", "tenderable_Percent", "eligible_Percent", "bales_Count"],
                         ts="published_date", sort=["commodity", "gin_State", "report_Period", "report_end_date"],
                         desc="Weekly Quality by State - tenderable/eligible %, bales, gins"),
    "3895_monthly": dict(file="mars_3895_monthly.parquet", slug=3895, section="Monthly Summary",
                         start=date(2015, 1, 1), chunk_months=12,
                         key=["commodity", "market", "report_Begin_Date"], keep=None, num=None, ts=None,
                         sort=["market", "report_Begin_Date"], desc="Monthly spot price statistics by market"),
}
DROP_META = {"report_title", "slug_name", "slug_id", "market_type", "market_type_category", "market_location_city",
             "group", "category", "final_ind", "report_section", "special_notes", "office_state", "office_city",
             "market_location_name_x", "community", "publish_volume", "publish_number", "comments"}


def load_key():
    if os.environ.get("MARS_API_KEY"):
        return os.environ["MARS_API_KEY"]
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.startswith("MARS_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    sys.exit("MARS_API_KEY not found (env var or .env)")


def fetch(session, cfg, start, end, retries=3):
    url = f"{BASE_URL}/{cfg['slug']}" + (f"/{cfg['section']}" if cfg["section"] else "")
    params = {"q": f"report_begin_date={start:%m/%d/%Y}:{end:%m/%d/%Y}"}
    if not cfg["section"]:
        params["allSections"] = "true"
    for a in range(1, retries + 1):
        try:
            r = session.get(url, params=params, timeout=180)
            r.raise_for_status()
            return r.json()
        except requests.RequestException as e:
            print(f"  attempt {a} failed: {e}")
            time.sleep(5 * a)
    raise RuntimeError(f"Failed {cfg['slug']} {start} -> {end}")


def to_frame(payload):
    secs = payload if isinstance(payload, list) else [payload]
    return pd.DataFrame([r for s in secs for r in s.get("results", [])])


def clean(df, cfg):
    if df.empty:
        return df
    if cfg["keep"]:
        df = df[[c for c in cfg["keep"] if c in df.columns]].copy()
    else:
        df = df.drop(columns=[c for c in df.columns if c in DROP_META]).copy()
        df = df.loc[:, df.notna().any()]
    df = df.replace(BLANKS)
    num = cfg["num"]
    for c in df.columns:
        low = c.lower()
        if "date" in low and "published" not in low:
            df[c] = pd.to_datetime(df[c], format="%m/%d/%Y", errors="coerce")
        elif "published" in low:
            df[c] = pd.to_datetime(df[c], errors="coerce")
        elif num is None or c in num:
            conv = pd.to_numeric(df[c], errors="coerce")
            if num is not None or conv.notna().sum() >= 0.9 * df[c].notna().sum():
                df[c] = conv
    return df


def upsert(old, new, cfg):
    df = pd.concat([old, new], ignore_index=True) if old is not None else new
    if cfg["ts"] and cfg["ts"] in df.columns:
        df = df.sort_values(cfg["ts"])
    return df.drop_duplicates(cfg["key"], keep="last").sort_values(cfg["sort"]).reset_index(drop=True)


def month_chunks(start, end, months):
    cur = start
    while cur <= end:
        m = cur.month - 1 + months
        nxt = date(cur.year + m // 12, m % 12 + 1, 1) if months < 12 or cur.day == 1 else \
            date(cur.year + 1, cur.month, cur.day)
        yield cur, min(nxt - timedelta(days=1), end)
        cur = nxt


def run(name, cfg, session, backfill, limit_days):
    path = DB_DIR / cfg["file"]
    old = pd.read_parquet(path) if path.exists() else None
    end = date.today()
    if limit_days:
        start = end - timedelta(days=limit_days)
    elif backfill or old is None:
        start = cfg["start"]
    else:
        col = "report_begin_date" if "report_begin_date" in old.columns else "report_Begin_Date"
        start = old[col].max().date() - timedelta(days=OVERLAP_DAYS)
    print(f"[{name}] {cfg['desc']}")
    frames = []
    for s, e in month_chunks(start, end, cfg["chunk_months"]):
        f = to_frame(fetch(session, cfg, s, e))
        print(f"  {s} -> {e}: {len(f)} rows")
        frames.append(f)
    new = clean(pd.concat(frames, ignore_index=True), cfg)
    if new.empty:
        print("  no data returned")
        return
    if old is not None and "source" in old.columns:       # tables merged with legacy history tag new rows
        new["source"] = "api"
    out = upsert(old, new, cfg)
    DB_DIR.mkdir(exist_ok=True)
    out.to_parquet(path, index=False)
    print(f"  saved {len(out)} rows (added {len(out) - (0 if old is None else len(old))}) -> {path.name}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", choices=list(REPORTS), help="default: all")
    ap.add_argument("--backfill", action="store_true")
    ap.add_argument("--limit-days", type=int, help="test: only fetch the last N days")
    a = ap.parse_args()
    s = requests.Session()
    s.auth = (load_key(), "")
    failed = []
    for name in ([a.report] if a.report else REPORTS):
        try:
            run(name, REPORTS[name], s, a.backfill, a.limit_days)
        except Exception as e:
            print(f"  [{name}] FAILED: {e}")
            failed.append(name)
    if failed:
        sys.exit(f"failed: {failed}")


if __name__ == "__main__":
    main()
