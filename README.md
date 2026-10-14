# USDA MARS API

Daily US cotton classing (AMS MARS report 1652, Daily Cotton Quality Summary by State).

- `Ingestion/mars_ingest.py` - incremental fetch (`--backfill` for full history), upserts `Database/mars_1652.parquet`
- `Database/` - parquet (latest published row per period/commodity/state/start/end)
- `Dashboard/app.py` - Streamlit (seasonal + time series)
- `Automator/run_update.bat` - daily ingest + git push (schedule ~08:30)
- Key: `MARS_API_KEY` in `.env` (git-ignored) or as Streamlit secret/env var
