# KisanSaathi implementation changelog

## Master update (October 2026): every review point fixed

This update answers every point in the in-depth review (C1–C5, M1–M15, m1–m15), the ten judge questions, and three requests: full Hindi, English name first beside the logo, and the trader-offer total.

### Requests

- **Everything switches to Hindi.** New name tables give Hindi names for all states/UTs, all 672 districts in the crop dataset (plus the current district lists of Punjab, UP, MP, Maharashtra and Karnataka), crops, mandi commodities, varieties, grades, seasons and mandi towns (`backend/app/data/`, built into `frontend/js/names.js`). State and district boxes on Crop insights, Next season, Irrigation and Sell & buy are now dropdowns with Hindi names. Every planner message, data gap, irrigation and weather text, Crop Doctor reason and server error now has a Hindi text (566 keys in each language, checked by a test). Unknown villages and mandis are written phonetically in Devanagari; typing a crop or district in Hindi in the buyer search works.
- **Logo:** "KisanSaathi" now comes first beside the logo, with "किसान साथी" beside it on laptops and under it on phones (both always visible).
- **Trader offer total:** the "What is the trader offering?" box now shows the full calculation for the quantity entered: trader total, mandi total, minus transport, commission and other costs, the amount after costs (total and per kg) and which is better by how much.

### Judge questions (image list)

1. Farm records: private farm record key issued by the server, stored as a hash, sent only in POST bodies; the GET route with the key in the URL is gone.
2. Direct Market: rate limits, PIN lockout, strong-PIN rules, one interest per buyer, 30-day expiry, withdraw, shortened public names and optional OTP phone verification.
3. Crop Doctor field validation: `scripts/evaluate_model.py` measures accuracy on your own labelled field photos; the page says the model was trained on clear leaf photos.
4. "Invalid" is not universal: plant-pixel check, Invalid/low-confidence/close-call checks, each with a reason in both languages.
5. Mandi coverage: the page and docs say which five states and that it is a community provider; data.gov.in import is still supported; prices older than 3 days are labelled.
6. Highest quote is not best sale: transport, commission and other costs are subtracted in the trader comparison.
7. Old/inconsistent crop data: bale and nut units handled, impossible yields removed, data age shown, crop name aliases unified, `--file` import of the newer DES/India Data Portal APY series.
8. Planning returns indicative: ranking only with ≥2 net returns, harvest-month price medians, "not a recommendation" list otherwise, rotation used, all gaps shown.
9. Irrigation root zone: daily FAO-56 root-zone balance with TAW/RAW, irrigation days and litres.
10. `/health` and scheduler: `/health` runs `SELECT 1` (503 when the database fails) and reports the scheduler; the scheduler takes a database lease so only one process refreshes.

### Other fixes

- IMD rain/heat/wind thresholds for alerts; `precipitation_sum` (includes showers) instead of `rain_sum`.
- Indian time (IST) for "today", data age and staleness.
- Old mandi rows removed after 730 days; LIKE wildcards in search are treated as text.
- Rainfed Kharif rice is no longer excluded; it gets a caution.
- Gzip compression; demo PIN for seeded listings (`kisan-demo-2026`); `scripts/prepare_demo_data.py` for one-command demo data.
- 33 new tests (115 in total), including real-data rows, name tables, security and the English/Hindi text check.

## Earlier feature work

## Feature work included in this build

- Added a Next Season Planner UI and bilingual labels that connect farmer-entered crop outcomes with historical district yield, current dated mandi observations and separate state/commodity historical price aggregates.
- Added farmer-season records with harvested quantity/yield, sale price, total cultivation cost and itemised seed, fertiliser, crop protection, labour, irrigation, machinery, harvest, transport and other costs.
- Added candidate-crop screening for target season, broad water availability, indicative soil type/pH and crop-rotation group; the API returns rationale/data gaps rather than treating incomplete data as certainty.
- Added a separate `MandiPriceHistory` database table, historical-series normalization/upsert and a targeted backfill command: `python -m scripts.fetch_mandi_history --state Punjab --commodity Wheat --years 5`.
- Extended mandi price status to show state/commodity historical-series coverage separately from individual market quotes.
- Added request-time Open-Meteo current-weather + 1–7 day forecast endpoint, including timestamped source attribution, rainfall/temperature/wind/ET0 fields and conservative condition alerts.
- Upgraded irrigation estimates to a seven-day reference ET0 / representative crop-stage Kc calculation, expected rainfall handling, irrigation efficiency, soil-texture heuristic, field-moisture input, and warnings. Paddy ponding/percolation remains deliberately outside the generic volume estimate.
- Expanded Crop Doctor remedies in Hindi/English for supported healthy/disease labels, with immediate steps, prevention, monitoring, crop-care tips, escalation guidance and pesticide-safety caveats.
- Fixed Next Season Planner front-end form/total-cost interaction and displayed the historic price aggregate's date range and notes separately from individual mandi quotes.
- Added model downloader validation/repair for only the known missing outer brace in the pinned upstream processor JSON, staged install, smoke-load, hash manifest and preservation of an existing installation on failure.
- Added regression coverage for planner APIs and validation, live-weather response parsing (mocked), history normalization/upserts, and safe handling of malformed model artifacts.
- Updated README/API references and added `DECISION_SUPPORT_METHODOLOGY.md` documenting calculations, sources and limitations.

## Important boundaries

- The public community mandi provider is limited to its documented five states and may return stale or incomplete data. This project cannot guarantee its freshness or availability.
- Weather requests are made to Open-Meteo at request time; no API key is required for non-commercial prototype use according to its published terms. Forecasts are not official IMD warnings and need an internet connection.
- Historical crop data and model weights are not included in the ZIP; they must be downloaded/imported on the target computer.
- Historical price backfill contains only the observations actually returned by the provider, not a guaranteed five-year complete series.
- Alternative crop recommendations are transparent rules-based decision support, not a trained/validated profit prediction. Missing data should stay visible.
- (Earlier build) The harvest-record API used a local-browser reference; replaced by the private farm record key in the master update.
- Crop-water values are estimates from a typical-soil root-zone balance, not measured soil moisture. Rice paddy flooding/percolation demand is not modelled.
- The disease classifier is not independently validated on a representative Indian field-image test set. Remedy content is general guidance; get local expert review before production use.

## Frontend visual refresh

- Rebuilt the homepage information architecture around three farmer tasks instead of six repetitive feature cards.
- Added a locally bundled, original farming-landscape SVG with distinct workflow illustrations; no new external JS/CSS dependency is introduced.
- Replaced the blue/indigo palette with forest green, sage, warm white and restrained harvest-gold accents across all pages.
- Kept the existing features and route links, and retained the Hindi/English language switch with all new homepage copy translated.
- Added active-page states to top and mobile navigation, larger practical control targets, better focus visibility and responsive layout refinements.
- See `FRONTEND_DESIGN_NOTES.md` for research references, design rationale, validation, limitations and final manual QA steps.
