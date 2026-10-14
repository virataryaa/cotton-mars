# USDA MARS API

Daily US cotton classing (AMS MARS report 1652, Daily Cotton Quality Summary by State).

- `Ingestion/mars_ingest.py` - incremental fetch of all reports below (`--report X`, `--backfill`), upserts parquets in `Database/`
- `Database/` - parquet (latest published row per period/commodity/state/start/end)
- `Dashboard/app.py` - Streamlit (seasonal + time series)
- `Automator/run_update.bat` - daily ingest + git push (schedule ~08:30)
- Key: `MARS_API_KEY` in `.env` (git-ignored) or as Streamlit secret/env var

## Reports (Database/)
- `mars_1652` - Daily Cotton Quality Summary by State (2018-)
- `mars_1625` - Daily Cotton Quality Summary by Office (2015-)
- `mars_3804_basis` - Daily Spot Cotton: basis and bales by spot market (Dec 2024-)
- `mars_3804_futures` - Daily Spot Cotton: ICE CT settlements by contract (Dec 2024-)
- `mars_1613` - Forward Contracting Report, monthly (2018-)
Not ingested (large): 3804 spot differences / tenderable differences (~3k rows per day).
Other cotton slugs: 1646/1654 weekly quality, 1658/1659 annual and monthly quality, 3895/3896 price stats.
