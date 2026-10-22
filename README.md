# KisanSaathi — किसान साथी

KisanSaathi is a mobile-first farmer-assistance prototype for the Agriculture & Rural Development hackathon track. The app is bilingual (Hindi/English) and keeps data provenance visible instead of presenting demo or historical data as live facts. When Hindi is selected, the whole interface switches, including state, district, mandi, crop, variety and season names (see [Hindi names](#hindi-names-for-places-and-crops)).

**What changed in the master update** is listed in [`IMPLEMENTATION_CHANGELOG.md`](IMPLEMENTATION_CHANGELOG.md); the judge-facing evidence is in [`VERIFICATION_REPORT.md`](VERIFICATION_REPORT.md).

## What is included

| Feature | What it does | Important limitation |
| --- | --- | --- |
| **Crop Doctor** | Predicts a class from a leaf photo and returns general Hindi/English advice. Photos that do not look like a leaf, "Invalid" results, low-confidence and close-call results are shown as "not sure" with the reason. | Uses a downloaded pretrained model covering maize, potato, rice and wheat. Its accuracy on Indian field photos is not yet measured; `scripts/evaluate_model.py` measures it on your own labelled photos. |
| **Mandi Bhav** | Displays dated mandi modal prices and a short history. The trader-offer box shows the full money calculation: trader total, mandi total, minus transport, commission and other costs, and what the farmer actually gets. | Defaults to the keyless community Mandi Price API for five states; record dates are checked and may be stale. Official data.gov.in import remains optional. Costs are what the farmer enters; the app does not know local freight rates. |
| **Crop Insights** | Explores historical area and production by state, district, crop, year and season. Cotton/jute bales are converted to tonnes, coconut (counted in nuts) is kept out of tonne totals, and impossible yields are left out. | The default community dataset ends around 2012-13 and the app says how old it is. Import the newer DES / India Data Portal district APY file (1997–2023) with `--file` for recent years. |
| **Next Season Planner** | Compares the farmer's recorded yield, sale price and itemised costs with local yield history, current dated mandi observations and imported state-level historical price aggregates (harvest-month prices when there is enough history). Crops are ranked only when net returns exist for at least two crops; otherwise they are listed by recent area with a clear "not a recommendation" note. | Returns are indicative only, not a trained profitability predictor. Every data gap is shown in Hindi or English. Saved records need a private farm record key. |
| **Live Weather** | Fetches current conditions and a 1–7 day forecast on request, including rain, temperatures, wind and reference ET₀. | Open-Meteo model forecast, not an official IMD warning; data needs internet and results can change. |
| **Irrigation Planner** | Runs a daily FAO-56 root-zone water balance for seven days (soil water-holding capacity × root depth, readily available water, effective rain, crop use) and says on which day to irrigate and how many litres. | Soil values are typical FAO-56 figures for the soil type, not a field measurement; it does not model percolation, capillary rise or paddy ponding, so no rice volume is given. |
| **Direct Market** | Lets farmers list produce and lets buyers register interest. Strong farmer PIN (weak and phone-number PINs refused), PIN lockout after 5 wrong tries, rate limits, one interest per buyer, 30-day expiry, withdraw button, shortened public names and optional OTP phone verification. | OTP ships with a demo "console" provider only; connect a real SMS gateway before a public launch. Use demo identities only. |

## Frontend design and usability

The interface uses a task-based homepage (field care, evidence-led planning, and market access), a green/sage/warm-white palette, a locally bundled original SVG illustration, bilingual copy and responsive navigation. The redesign retains the existing front-end scripts and API integration; it does not add a JS framework or third-party visual dependency. See [`FRONTEND_DESIGN_NOTES.md`](FRONTEND_DESIGN_NOTES.md) for UX research references, accessibility targets, implementation notes and a manual QA checklist.

## Quick setup (Windows / PowerShell)

Requirements: Python 3.11–3.13, internet for first-time downloads, and enough disk space for PyTorch plus the model. SQLite is the default, so PostgreSQL is not required for a local demo.

```powershell
cd kisansaathi\backend
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip

# Install CPU PyTorch first, then the remaining pinned dependencies.
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt

# Create your local environment file. Keep backend/.env private and never commit it.
Copy-Item .env.example .env

# Download the exact pinned ViT weights and verify every class has advice mapping.
python -m scripts.download_model

# Optional: verify the downloaded pipeline against a real local leaf image.
# python -m scripts.download_model --test "C:\path\to\leaf.jpg"

# Optional: download and import historical crop statistics.
python -m scripts.setup_crop_data

# Fetch real mandi prices from the keyless Mandi Price API (five supported states).
python -m scripts.fetch_prices
# Or fetch a single state/crop for a faster demo check.
python -m scripts.fetch_prices --state Punjab --commodity Wheat

# If the API key/portal is unavailable, load only synthetic demo values for a presentation.
# The UI will label these as sample data; do not use them for buying/selling decisions.
python -m scripts.load_prices_csv --sample

# Optional: add clearly fake demo listings for a non-empty market page.
# Demo login for "My listings": phone 9000000001, PIN kisan-demo-2026
python -m scripts.seed_listings

# Or do all the demo data in one command (crop history, prices, price history, demo listings):
# python -m scripts.prepare_demo_data --state Punjab

# Start the app; keep this terminal open.
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open `http://localhost:8000`. API docs are at `http://localhost:8000/docs`; health/model status is at `http://localhost:8000/health`. If testing from a phone on the same Wi-Fi, open `http://<laptop-IP>:8000` and allow the local server through the firewall if prompted.

For macOS/Linux, use `python3 -m venv .venv`, `source .venv/bin/activate`, and `cp .env.example .env`. Run **all Python commands from the `backend` folder** so the example SQLite URL (`sqlite:///./kisansaathi.db`) and scripts resolve predictably.

## Data setup and provenance

### 1. Mandi prices — keyless provider for a five-state hackathon demo

The default provider is the community-run **Mandi Price API**: <https://mandi-api.vercel.app/docs>. It does not require an API key and documents support for Maharashtra, Uttar Pradesh, Punjab, Madhya Pradesh and Karnataka. It sources upstream data from data.gov.in, so it can still be stale when upstream collection fails. KisanSaathi stores each record's original `arrival_date`; a recent API fetch timestamp must never be treated as proof that a market price is from today.

**Daily refresh is now built into the FastAPI lifespan.** By default, when the backend starts it begins an asynchronous refresh in the background, then repeats the refresh every 24 hours while that backend process remains running. It does not block the homepage from loading. The last attempt, last successful run, state-level outcome and saved row count are stored in the database and exposed through `/api/prices/status`; the Mandi Prices page shows the auto-refresh state and warns after a failed/empty refresh.

- Configure `MANDI_AUTO_REFRESH_ENABLED=true`, `MANDI_REFRESH_ON_STARTUP=true`, and `MANDI_REFRESH_INTERVAL_HOURS=24` in `backend/.env` (these are defaults in `.env.example`). To disable the in-process job, set `MANDI_AUTO_REFRESH_ENABLED=false`.
- Manual run remains available: `python -m scripts.fetch_prices` from `backend/`.
- The scheduler intentionally needs only the Python standard library; no new scheduler dependency is added.
- **Use one Uvicorn worker** with this in-process scheduler. Multiple workers/processes would each run a daily job. For horizontally scaled hosts, serverless services, or deployments that sleep/stop, disable the in-process scheduler and configure a single external cron/scheduled job using the same command and production database. A job cannot run while your laptop is switched off.
- The scheduler attempts a refresh on backend startup and every configured number of hours after each run completes. `arrival_date`, not the sync timestamp, is the date shown for the price. A successful API response can still contain old market reports.

- `python -m scripts.fetch_prices` requests all five supported states.
- `python -m scripts.fetch_prices --state Punjab --commodity Wheat` fetches a smaller test set.
- Provider can be checked at <https://mandi-api.vercel.app/status>; schema/reference at <https://mandi-api.vercel.app/docs>.
- Default data source is stored as `mandi-api` and shown with community-source attribution. No key is required.
- Optional official-source fallback: set a valid `DATA_GOV_API_KEY` in `backend/.env` and run `python -m scripts.fetch_prices --provider data.gov.in --state Punjab`.
- `data/sample_mandi_prices.csv` contains **synthetic demo rows**, not observed prices. Only use them for offline UI testing; the UI marks sample data.
- `/api/prices/status` exposes the newest record date, source and stale/sample indicators, plus `auto_refresh` configuration and `last_sync` outcome.

The provider is not operated by the Government of India, has no production SLA established by this project, and documents a rate limit of 100 requests per 15 minutes per IP. It covers only five states. If it returns an empty response, a 429, or stale arrival dates, show that honestly rather than inventing current rates.

### 2. Historical crop production — publicly mirrored CSV

The optional crop-history pipeline downloads `agridata.csv` from the community repository <https://github.com/k0rn/India_Agri_Data>. The repository declares CC0-1.0 and documents fields for state, district, crop, year, season, area (hectares) and production (tonnes). This is a historical, community-hosted mirror of Indian agricultural statistics, not a live government API or a guarantee of the latest year. KisanSaathi recalculates yield as production divided by area and marks the page as historical. Read `data/CROP_DATA_SOURCE.md` before relying on the results.

Run `python -m scripts.setup_crop_data` while online. If your network blocks the download, get the CSV from the repository's `agridata.csv` file, save it as `data/crop_production.csv`, and run:

```powershell
python -m scripts.setup_crop_data --skip-download
```

Do not use historical area/production alone as planting advice; yield units and source quality should be validated before cross-crop comparisons.

**Units and data age.** The community file stores cotton in bales of 170 kg lint and jute, mesta and sunn hemp in bales of 180 kg; the importer converts these to tonnes and reports how many rows it converted. Coconut is counted in nuts, so it is stored but kept out of tonne totals and yield. Years with physically impossible yields are left out and counted on screen. Crop Insights and the planner show the last year in the data and how many years old it is.

**Newer data (recommended before judging).** The DES district Area-Production-Yield series (also published on the India Data Portal, about 1997–2023) has a `production_unit` column. Download the district APY CSV and import it with:

```powershell
python -m scripts.setup_crop_data --file "C:\path\to\district_apy.csv"
```

The importer recognises `state_name`, `district_name`, `crop_name`, `year`, `season`, `area`, `area_unit`, `production` and `production_unit`, and converts bales to tonnes using the unit column.

### 3. Historical price-series backfill and Next Season Planner

The farmer-facing **Next Season Planner** is available from the home page. It asks for location, current crop and season, planned season, field area, primary issue, water availability and optional soil pH/type. Farmers can also save an observed harvest record (yield, sale price, total costs and itemised costs). Records are tied to a **private farm record key**: the server issues a random 32-character key (`POST /api/planning/farm-ref`), stores only its SHA-256 hash, and returns records only to someone who presents the key. The key is kept in the browser and shown on the page so the farmer can write it down and open the same records on another phone. It is a bearer key, not a verified account: anyone with the key can read the records, so do not store sensitive personal data.

The planner deliberately separates two data shapes:

- **Mandi quotations** (`MandiPrice`) are individual market/commodity/variety/grade/date records. They are appropriate for asking what a specific mandi reported.
- **Historical price observations** (`MandiPriceHistory`) are state + commodity + date aggregate observations from the community API. They are appropriate only for broad trend context and must not be described as a quote from one mandi.

Run a targeted history backfill for the current crop and likely alternatives before demoing the planner:

```powershell
# Run from backend/.venv, from the backend directory.
python -m scripts.fetch_mandi_history --state Punjab --commodity Wheat --years 5
python -m scripts.fetch_mandi_history --state Punjab --commodity Mustard --years 5
python -m scripts.fetch_mandi_history --state Punjab --commodity Chickpea --years 5
```

Select state, current crop and alternatives relevant to the pilot area. The endpoint is community-run; the script imports only observations returned by the provider, does not fabricate missing years, and may receive a limited or empty response. Check `/api/prices/status` for recorded history coverage. If dates/observations are insufficient, the planner must show that limitation rather than present an unsupported forecast.

The recommendation method is transparent and uses imported district crop yields, farmer-entered outcomes/costs, current dated mandi prices and available historical state-level aggregate prices. It is **not a trained or independently validated profit predictor**. Expected revenue/return must be treated as indicative; missing candidate crop costs, local agronomic suitability, market access and yield data can prevent a meaningful net-return comparison. Local KVK/extension advice and official district contingency plans should be consulted before switching crops.

Reference sources for the intended workflow:
- DES area/production/yield query: <https://data.desagri.gov.in/website/apy-query-report-web>
- Crop cost studies: <https://desagri.gov.in/divisions-cell/cost-studies-cs/>
- ICAR-CRIDA district contingency plans: <https://icar-crida.res.in/ccp.html>
- Soil Health Card portal: <https://soilhealth.dac.gov.in/>
- IMD district agrometeorological advisories: <https://mausam.imd.gov.in/responsive/agromet_adv_ser_district_current_en.php>

These links provide data/context or reference guidance; they do not mean KisanSaathi has automatically ingested all of those official datasets.

### 4. Live weather and irrigation methodology

`GET /api/weather/forecast?location=Ludhiana&state=Punjab&days=7` geocodes the requested location and fetches current conditions plus a daily forecast from Open-Meteo at request time. No API key is needed for non-commercial prototype use. Attribute Open-Meteo and check the current terms if the app is commercialised. Forecast output identifies its source and retrieval timestamp. A forecast response is not an IMD-issued warning.

`POST /api/irrigation/estimate` takes location, crop, growth stage, area, irrigation efficiency, soil texture and a simple field-moisture observation, and runs a daily FAO-56 root-zone water balance:

- crop use each day: `ETc = Kc × ET0` (FAO-56 Kc for the stage);
- water the root zone can hold: `TAW = available water per metre (from the soil type, FAO-56 Table 19) × root depth (FAO-56 Table 22, scaled by stage)`;
- readily available water: `RAW = p × TAW`, with `p` from FAO-56 Table 22 adjusted for the day's ETc (`p + 0.04 × (5 − ETc)`);
- starting dryness from the farmer's moisture answer (wet = full, normal/unknown = half of RAW used, dry = all of RAW used);
- effective rain added each day (soil-dependent fraction); when depletion passes RAW, one irrigation refills the root zone and the gross amount is divided by the system efficiency.

The response lists the irrigation days and litres, the root-zone numbers, the simple deficit for comparison and bilingual advice. Weather warnings use IMD rain categories (moderate 15.6–64.4 mm, heavy 64.5–115.5, very heavy 115.6–204.4, extremely heavy ≥ 204.5) and heat thresholds of 40/45 °C. Drainage, capillary rise and paddy ponding are not modelled, so rice gets no volume. Use local agronomic advice before making field decisions.

- Open-Meteo forecast API and license/attribution details: <https://open-meteo.com/en/docs>
- FAO crop-water relationships and crop coefficients: <https://www.fao.org/4/X0490E/x0490e0a.htm> and <https://www.fao.org/4/X0490E/x0490e0b.htm>

### 5. Crop Doctor management guidance

The remedy guide maps each supported model class to bilingual sections (immediate steps, prevention, monitoring, crop-care tips, escalation and chemical safety). It gives non-prescriptive cultural/monitoring guidance and does not provide a pesticide product or dose. Classifier output may be wrong, especially on field images; do not spray solely because of one photo. Check multiple plants and consult a local KVK/agricultural officer before chemical treatment. Healthy labels provide preventive-care guidance; they do not certify that a whole field is disease-free.

### 6. Disease-classification model — weights are not bundled

The app uses `wambugu71/crop_leaf_diseases_vit` at immutable revision `2b77473a26a2974a9bfb7f0c7880ed84f9b302df`. The Hugging Face metadata lists MIT, but the model-card prose also states Apache 2.0; treat this as a licence inconsistency and verify permission with the model author before public or commercial deployment. The pinned configuration has 15 labels spanning maize, potato, rice and wheat, including an `Invalid` label. See the [pinned config](https://huggingface.co/wambugu71/crop_leaf_diseases_vit/blob/2b77473a26a2974a9bfb7f0c7880ed84f9b302df/config.json) and [model card](https://huggingface.co/wambugu71/crop_leaf_diseases_vit/blob/2b77473a26a2974a9bfb7f0c7880ed84f9b302df/README.md).

**Important upstream issue handled by the downloader:** the `preprocessor_config.json` shown at this exact pinned revision is missing the final closing brace for the outer JSON object. The download script detects and repairs only that known defect, only for this exact model ID/revision, and only when adding one brace produces valid JSON with the expected ViT preprocessing schema. It repairs a staged local copy, then loads the model, checks all class-to-advice mappings, serializes the processor and weights locally, smoke-loads the saved pipeline, writes a manifest with ordered labels and SHA-256 checksums, and only then replaces the installed local model. A failed download leaves the previous installation untouched. It does not edit the shared Hugging Face cache. See the [pinned processor config](https://huggingface.co/wambugu71/crop_leaf_diseases_vit/blob/2b77473a26a2974a9bfb7f0c7880ed84f9b302df/preprocessor_config.json).

Weights are not included in this ZIP: run `python -m scripts.download_model` on an internet-connected machine from `backend/`. If the model folder exists but fails the manifest/configuration/checksum checks, prediction returns a clear 503 with the setup command rather than silently trusting incomplete files. To smoke-test a photo during model setup, use `python -m scripts.download_model --test "C:\path\to\leaf.jpg"`.

**Safety checks before a result is shown.** The app measures the share of plant-coloured pixels in the photo (HSV hue/saturation/brightness check); below 10% the photo is treated as "not a leaf". An `Invalid` top label, confidence under the threshold, or a gap of less than 15 points between the top two diseases also gives "not sure", with the reason shown in Hindi or English. A healthy result says "the app did not detect a disease on this leaf", not "healthy field".

**Measuring field accuracy.** Put your own labelled field photos in one folder per true label and run `python -m scripts.evaluate_model field_photos --report ../model_evaluation.md`. The report gives accuracy, accuracy when confident, how often the app said "not sure", and per-class precision/recall with photo counts. Quote those numbers, not the model card's lab accuracy.

A confidence score is not a calibrated probability that a disease diagnosis is correct. Use the result as preliminary screening only, particularly for Indian field conditions; consult a local agriculture officer/KVK before acting. No pesticide dosage is recommended by the app. The model's `Invalid` class is not a reliable universal detector for arbitrary photos.

If you have a separate rice/maize disease CSV, it is **not present in the ZIP supplied for this audit**, so it was not imported or used for training. Inspect it first:

```powershell
python -m scripts.inspect_disease_csv ..\data\your_disease_file.csv
```

A table containing disease names or symptoms alone cannot train an image classifier; we need accessible leaf image files and verified image-to-disease labels, plus licence/permission to use them. Do not train on CSV labels without checking the images and class definitions.

### 7. Irrigation estimate — live forecast, approximate agronomy

The calculator uses Open-Meteo daily `et0_fao_evapotranspiration` and `precipitation_sum` (which includes showers; `rain_sum` does not) and FAO-56 crop coefficients, root depths and depletion fractions. Open-Meteo describes ET₀ as reference evapotranspiration based on FAO-56 Penman–Monteith; it is not the crop's measured water requirement. The soil-water figures are typical values for each soil type, not a measurement of the farmer's field; runoff, percolation and paddy ponding/flooding are not modelled. Internet access is needed each time a forecast is requested. Attribution is required under CC BY 4.0, and Open-Meteo's free API is for non-commercial use; use an appropriate paid plan before commercial deployment. Sources are linked on the page.

## Direct Market: security and upgrade notes

- Public listing endpoints never return the farmer's phone number or PIN hash, and show only a shortened name ("Ramesh K.").
- Farmers must enter their phone number and private PIN to view buyer contacts, mark a listing sold or withdraw it. The PIN is salted and hashed (PBKDF2); it is never stored in plaintext, in browser storage or in a URL.
- Weak PINs are refused: fewer than 3 different characters, common PINs, straight runs such as 12345678/abcdefgh, and PINs containing the mobile number. A second listing from the same number must use the same PIN.
- **Lockout and rate limits:** 5 wrong PINs for a number lock it for an hour; each IP is limited (listing creation 10/hour, buyer interest 20/hour, PIN checks 30 per 10 minutes, OTP requests 3 per 15 minutes per phone). Over the limit the API answers `429` with `Retry-After`. Limits are in memory per server process; for several servers use a shared store such as Redis.
- **One interest per buyer per listing**, and listings close automatically after 30 days (`LISTING_EXPIRY_DAYS`).
- **Optional OTP phone verification:** set `OTP_PROVIDER=console` and a long random `SECRET_KEY` in `backend/.env`. The Sell and My listings forms then ask for a 6-digit code; the demo provider writes the code to the server log instead of sending an SMS. Codes are stored as salted hashes, expire after 5 minutes and allow 5 attempts. For a real launch add an SMS gateway branch in `app/services/otp.py` (key in `.env`, never in code).
- When upgrading a database created by an earlier version, startup adds missing columns. Old listings with no PIN hash cannot be managed; run `python -m scripts.seed_listings` again to give demo listings the demo PIN.
- Still needed for a public launch: real SMS OTP, a privacy and data-retention policy, and a shared rate-limit store.

## Test and validation

From `backend/`:

```powershell
python -m compileall -q app scripts tests
python -m pytest -q
```

The suite has 115 tests. They include a test on 685 real rows from the crop dataset, unit and name-table checks (all 672 dataset districts have a Hindi name), security checks (weak PINs, lockout, OTP, rate limits, expiry, withdraw), the root-zone irrigation numbers, and a check that every on-screen text exists in both English and Hindi (needs Node.js; skipped otherwise). The tests use temporary SQLite databases, a fake disease classifier, mocked weather responses, and mocked Mandi Price API responses, including automatic-sync upsert/failure-preservation checks. Model-artifact regression tests verify the narrowly scoped repair for the pinned upstream processor JSON, reject unrelated malformed JSON, test manifest checksums, and ensure a failed download cannot remove a previous local installation. They do not verify live access to the community price API, download the external model, import the complete upstream crop dataset, verify a live data.gov.in key, or perform independent agricultural validation. A green test suite proves local code paths behave as expected, not that external services or predictions are accurate in a real farm.

## API reference

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Runs `SELECT 1` on the database (503 "degraded" if it fails), model status, price-refresh scheduler state, phone-verification mode |
| `GET` | `/api/auth/config` | Whether OTP phone verification is required |
| `POST` | `/api/auth/otp/request` | Send a 6-digit code to `{"phone": "..."}` (when OTP is on) |
| `POST` | `/api/auth/otp/verify` | `{"phone","code"}` → short-lived `phone_token` |
| `POST` | `/api/disease/predict` | Multipart field `file` with a leaf photo |
| `GET` | `/api/prices/status` | Rows, latest date, source/staleness, automatic-refresh configuration and last sync result |
| `GET` | `/api/prices/states` | States with available price data |
| `GET` | `/api/prices/commodities?state=` | Commodities available in a state |
| `GET` | `/api/prices/best?state=&commodity=&limit=` | Highest modal prices for the newest day available |
| `GET` | `/api/prices/history?state=&commodity=&days=` | Daily state-level average modal price from individual stored quotes |
| `GET` | `/api/weather/forecast?location=&state=&days=` | Live current conditions and 1–7 day Open-Meteo forecast |
| `POST` | `/api/planning/recommendations` | Evidence-aware crop alternatives and data-gap notes |
| `POST` | `/api/planning/farm-ref` | Issue a new private farm record key (only its hash is stored) |
| `POST` | `/api/planning/records` | Store a farmer-entered crop-season harvest/yield/cost record under the farm key |
| `POST` | `/api/planning/records/latest` | Body `{farm_ref, state, district, crop}`; latest matching record for that key (POST so the key is never in a URL or log) |
| `GET` | `/api/crops/status` | Historical dataset presence and coverage |
| `GET` | `/api/crops/states` | Historical dataset states |
| `GET` | `/api/crops/districts?state=` | Districts for a state |
| `GET` | `/api/crops/seasons?state=&district=` | Available seasons for a district |
| `GET` | `/api/crops/history?state=&district=&season=` | Historical crop area, production and calculated yield |
| `POST` | `/api/irrigation/estimate` | Seven-day crop-water/irrigation planning estimate from live forecast and field inputs |
| `POST` | `/api/listings` | Create listing; requires a strong `owner_pin` (8+ characters) and `phone_token` when OTP is on |
| `GET` | `/api/listings?crop=&district=&state=&limit=` | Browse available listings without farmer contact details |
| `POST` | `/api/listings/mine` | Body: `{"phone":"...","owner_pin":"..."}`; shows verified-by-PIN listings and buyer contacts |
| `POST` | `/api/listings/{id}/interest` | Submit buyer name, mobile number, optional offer/message |
| `PATCH` | `/api/listings/{id}/sold` | Body contains `phone` and `owner_pin`; only the correct PIN can mark sold |
| `POST` | `/api/listings/{id}/withdraw` | Same body; removes the listing from the buyer list |

## Hindi names for places and crops

`backend/app/data/place_names.txt` holds Hindi names (with common English spelling variants) for every state and union territory and for every district in the crop dataset, plus current district lists for Punjab, Uttar Pradesh, Madhya Pradesh, Maharashtra and Karnataka. `backend/app/data/display_names.py` holds Hindi names for crops, mandi commodities, varieties, grades, seasons and mandi towns. `python -m scripts.build_name_tables` turns both into `frontend/js/names.js`, which every page loads. Run it again after editing the tables. A mandi or village not in the table is written phonetically in Devanagari, so the spelling of rare names may not match local usage; add the correct name to the table when you see one.

## Running in production

- Set `SECRET_KEY` to a long random value in the host's secret settings (never in GitHub). It signs OTP phone tokens; all server processes must share it.
- `/health` really queries the database, so a hosting health check notices a broken database.
- The automatic mandi refresh takes a database lease (`scheduler_leases` table) before it runs, so only one process refreshes even when several workers run. For a large deployment, move the refresh to the host's cron or a worker and set `MANDI_AUTO_REFRESH_ENABLED=0` on the web processes.
- Old mandi rows are removed after `PRICE_RETENTION_DAYS` (default 730).

## Before your hackathon submission

Replace the placeholder team members in **Team & contributions** with the actual names and contributions. Never commit `backend/.env`, real user data, or any real API keys. Show judges the difference between features that are locally tested and integrations that still require internet/credentials.

## Team & contributions

Replace these rows with your team's real details; the labels below are placeholders, not actual credits.

| Member | Role | Built |
| --- | --- | --- |
| NAME_A (@github_a) | Backend | API, database, marketplace, tests |
| NAME_B (@github_b) | ML | Disease model integration and advice mapping |
| NAME_C (@github_c) | Data | Mandi-price and historical crop-data importers |
| NAME_D (@github_d) | Frontend / pitch | Bilingual web UI and presentation |

## Tech stack and folder map

FastAPI, SQLAlchemy, SQLite by default (PostgreSQL optional), Hugging Face Transformers/ViT, plain HTML/CSS/JavaScript, Open-Meteo forecast API.

```text
kisansaathi/
├── backend/app/              API routers, schemas, database, security and services
├── backend/scripts/          model/data downloaders, importers, seeding and CSV inspector
├── backend/tests/            isolated API/service tests with mocked external dependencies
├── frontend/                 index, Crop Doctor, Mandi Bhav, Crop Insights, Next Season Planner, Irrigation, Direct Market
├── data/                     synthetic mandi sample plus data-source documentation
└── ml/model/                 model files downloaded on your own machine (not committed)
```

## Sources

- Mandi daily price resource, Government of India OGD: <https://www.data.gov.in/resource/current-daily-price-various-commodities-various-markets-mandi>
- Historical crop data mirror (CC0-1.0 declared by repository): <https://github.com/k0rn/India_Agri_Data>
- Disease model repository/revision (metadata says MIT, model-card prose says Apache 2.0; confirm licence with author): <https://huggingface.co/wambugu71/crop_leaf_diseases_vit/tree/2b77473a26a2974a9bfb7f0c7880ed84f9b302df>
- Open-Meteo API docs: <https://open-meteo.com/en/docs>
- FAO crop-water coefficient reference: <https://www.fao.org/4/S2022E/s2022e07.htm>
- Kisan Call Centre: 1800-180-1551 (toll-free number shown in the app; verify availability before a public release).
