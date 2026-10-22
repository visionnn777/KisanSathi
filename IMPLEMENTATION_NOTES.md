# Implementation notes — October 2026

This file summarizes the main fixes made after auditing the uploaded KisanSaathi ZIP.

## Code corrections

- **Local startup:** SQLite is the default; PostgreSQL is optional. The default data directory is created automatically.
- **Marketplace privacy:** public listing endpoints do not return farmer phone numbers or owner-PIN hashes; `POST /api/listings/mine` and the mark-sold endpoint require phone + PIN. PINs are stored with random salt and PBKDF2-HMAC-SHA256, not plaintext. This is a prototype control, not a replacement for OTP-backed user identity.
- **Legacy database migration:** application startup adds the nullable `owner_pin_hash` column if missing. Old records without a hash cannot be safely assigned an owner PIN and cannot be managed through the protected API until ownership can be verified/re-created.
- **Disease model integrity:** model revision is pinned, local model use requires a matching `model_manifest.json`, ordered labels and SHA-256 weight checksum, the downloader uses Transformers model/processor APIs correctly, and the downloaded `id2label` list is checked against the advice mapping before writing a trusted manifest. Image validation checks type/size/dimensions and EXIF orientation. Hugging Face metadata lists MIT but the card's prose also states Apache 2.0; verify permission with the author before public/commercial use.
- **Mandi data provenance:** default price ingestion now uses the keyless community Mandi Price API for the five documented states (Maharashtra, Uttar Pradesh, Punjab, Madhya Pradesh, Karnataka). It normalizes the provider JSON into the app schema, handles empty data/rate limits/network errors, records source as `mandi-api`, keeps the original market arrival date, and deletes synthetic rows only after valid external rows are stored. The official data.gov.in provider remains available with `--provider data.gov.in` and its own API key. API status exposes sources and freshness; arbitrary CSV input remains tagged `custom`.
- **Historical crop insights:** CSV schema validation, safe download-to-temporary-file, unit/source display and transactional replacement import are included. Full source data must still be downloaded on a connected machine.
- **Live weather and irrigation:** added a request-time Open-Meteo current-conditions + 1–7 day forecast API and extended irrigation estimates to a seven-day reference-ET₀ / representative crop-stage Kc calculation with forecast rainfall, selected irrigation efficiency, soil-texture heuristic, moisture input and alerts. It remains an estimate, not a calibrated root-zone balance; rice ponding/percolation is not represented by a generic volume recommendation.
- **Next Season Planner and farm records:** added a bilingual screen and API to record observed yield, sale price, cost breakdown, land area and primary problem; compare candidates against district/crop/season yield history, current dated prices, and a separate historical state-level aggregate price series. Price-based expected returns are withheld until at least 12 historical observations across 180 days are present, and use a non-season-specific aggregate median with explicit caveat—not the current quote alone.
- **Historical price series:** added `MandiPriceHistory`, normalization for snake/camel-case records, ISO date/timestamp parsing, upserts and `scripts.fetch_mandi_history` for selective history backfills. This is separate from individual market quotations to prevent aggregate trends from being displayed as a single mandi price.
- **Crop Doctor advice:** extended the bilingual disease/healthy result with immediate steps, prevention, monitoring, crop-care tips, escalation and chemical-safety sections; the app does not prescribe chemical products/doses.
- **CSV diagnosis helper:** `backend/scripts/inspect_disease_csv.py` examines a user-provided disease CSV for possible image-reference and disease-label columns. It does not assume metadata is model-training data.
- **Bilingual UI/docs:** added the planner link and matching English/Hindi strings (376 keys in each locale), detailed cost breakdown, historical-price evidence display and live weather/irrigation explanation; setup/API/data provenance notes updated.

## Local verification

Run from `backend/`:

```bash
python -m compileall -q app scripts tests
python -m pytest -q
```

The Mandi Price API client is covered with mocked tests, but a live request could not be verified in this build environment because outbound DNS access to `mandi-api.onrender.com` failed. Run `python -m scripts.fetch_prices --state Punjab --commodity Wheat` on an internet-connected laptop and inspect arrival dates. The pretrained model weights and full historical CSV are not bundled; download them using the setup scripts. The government data.gov.in route remains optional and requires a working key.


## Automatic mandi refresh (added in this final build)

- `app/services/mandi_sync.py` contains the shared import/upsert and persistent run-status workflow.
- `app/services/mandi_scheduler.py` runs it in a worker thread at backend startup and every configured interval.
- `MANDI_AUTO_REFRESH_ENABLED`, `MANDI_REFRESH_ON_STARTUP`, and `MANDI_REFRESH_INTERVAL_HOURS` are configured in `backend/.env`.
- `/api/prices/status` now reports scheduler config plus the latest provider sync status, timestamps, state outcome, and rows saved.
- An empty/error response does not delete synthetic rows or existing stored prices. Sample rows are deleted only after valid external rows are written.
- Run one Uvicorn worker when using the in-process scheduler. For multi-worker/serverless or sleeping deployments, disable it and run `python -m scripts.fetch_prices` as one external daily scheduled job.
- The provider remains community-operated, and successful transport does not imply fresh market data. Every price must retain and show its own `arrival_date`.
