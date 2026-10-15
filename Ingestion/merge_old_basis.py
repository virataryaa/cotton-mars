"""One-off: merge the legacy spot basis history (Raw/28. Cotton Historical Upland/COTTON DATABASE.xlsx,
Aug 2011 - Oct 2024, 41-4-34 basis only) into Database/mars_3804_basis.parquet.

Legacy rows get source='legacy'; API rows keep source='api'. Safe to re-run (API rows win on any overlap).
"""
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OLD = ROOT / "Raw" / "28. Cotton Historical Upland" / "COTTON DATABASE.xlsx"
DB = ROOT / "Database" / "mars_3804_basis.parquet"
RENAME = {"Desert SW": "Desert Southwest", "SJ Valley": "San Joaquin Valley",
          "East TX-South TX": "East Texas - South Texas", "West TX-KS-OK": "West Texas - Kansas - Oklahoma",
          "East TX-OK": "East TX-OK (legacy)", "West Texas": "West Texas (legacy)"}


def main():
    o = pd.read_excel(OLD)
    o["Basis"] = pd.to_numeric(o["Basis"], errors="coerce")
    o = o.dropna(subset=["Basis", "Date"])                     # Pima rows have no basis
    o["Date"] = pd.to_datetime(o["Date"])
    leg = pd.DataFrame({
        "commodity": o["Type"], "report_Begin_Date": o["Date"], "report_End_Date": o["Date"],
        "spotMarket": o["Market"].replace(RENAME), "basis_41_4_34": o["Basis"],
        "basis_Month": pd.to_datetime(o["Basis Month"], errors="coerce").dt.strftime("%b-%y"), "source": "legacy"})
    leg = leg.drop_duplicates(["commodity", "spotMarket", "report_Begin_Date"], keep="last")

    api = pd.read_parquet(DB)
    if "source" in api.columns:
        api = api[api["source"] != "legacy"]
    api["source"] = "api"
    k = ["commodity", "spotMarket", "report_Begin_Date"]
    out = pd.concat([leg, api], ignore_index=True).drop_duplicates(k, keep="last")
    out = out.sort_values(["commodity", "spotMarket", "report_Begin_Date"]).reset_index(drop=True)
    out.to_parquet(DB, index=False)
    print(f"legacy {len(leg)} + api {len(api)} -> {len(out)} rows, {out['report_Begin_Date'].min():%Y-%m-%d} to "
          f"{out['report_Begin_Date'].max():%Y-%m-%d}")
    print(out.groupby(["source", "spotMarket"]).size().to_string())


if __name__ == "__main__":
    main()
