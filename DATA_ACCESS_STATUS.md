# KisanSaathi — data access and remaining user-side actions

**This file records what could and could not be populated while preparing this code bundle.** No real credentials were generated, no credentials from third parties were reused, and no synthetic values are represented as official facts.

| Item | State in the submitted bundle | Why it is not fully populated here | Exact next step on your machine |
| --- | --- | --- | --- |
| Local database | Ready; SQLite is the default | No blocker | Run the server; tables are created automatically. |
| Disease model source/integration | Code ready; immutable model revision pinned; downloader now verifies label-to-advice mapping | This build environment could not resolve/download from Hugging Face, so model weights are not included | From `backend/`, install dependencies then run `python -m scripts.download_model`. If that fails, share the complete terminal error. |
| Official mandi prices | API adapter and validation are ready; bundled CSV remains synthetic demo data | A working personal data.gov.in API key is required; the build environment could not reach the portal to validate live access. We cannot create or bypass your key | Add your own key to `backend/.env` as `DATA_GOV_API_KEY`, then run `python -m scripts.fetch_prices`. If the official portal refuses it, send the HTTP/error message (never send the key). |
| Historical crop production | Downloader/importer and offline import mode are ready; full upstream CSV is not bundled | The upstream file is about 11.7 MB and external downloads/DNS are blocked in this build environment | Run `python -m scripts.setup_crop_data` online. If blocked, download `agridata.csv` from the link in `data/CROP_DATA_SOURCE.md`, put it at `data/crop_production.csv`, then run `python -m scripts.setup_crop_data --skip-download`. |
| Next Season Planner / historical market series | Code and UI are included; farmer inputs, broad crop screening and historical-price backfill are supported | Local historical crop CSV and historical price data still must be downloaded/imported. The community provider may return incomplete history; candidate costs are farmer-provided and not every recommendation can show a net return | Run `python -m scripts.setup_crop_data`, then selectively run `python -m scripts.fetch_mandi_history --state Punjab --commodity Wheat --years 5` and for alternatives. Check `/api/prices/status` and planner data-gap notes. Do not treat the rules-based ranking as a guaranteed profit forecast. |
| Rice/maize disease CSV you mentioned earlier | Not integrated or used for training | The current upload contained the project ZIP, not that separate CSV/image archive. A disease-named CSV may contain only metadata, not leaf photographs | Download that CSV and run `python -m scripts.inspect_disease_csv path/to/file.csv`. If it references image files, keep those images and label mapping alongside it. Share the CSV schema/sample rows (and the dataset's licence) to confirm whether model training is possible. Do not send API secrets. |
| Live weather/irrigation | Endpoint and UI ready; tests use mocked response data | External API calls from the build environment were not possible | Start the app on a network-enabled device and submit a town/city and state. A weather/geocoding failure appears as an explicit error; it is not replaced with fake weather. Open-Meteo requires attribution; its free API is for non-commercial usage, so confirm the appropriate plan before commercial deployment. |

## What was locally verified

- All Python source files compile with `python -m compileall -q app scripts tests`.
- The full test suite passes locally; tests use temporary SQLite and mocked weather/model responses.
- Listing APIs require an owner PIN and keep farmer contact/PIN hashes out of public listing responses.
- Synthetic mandi rows are labelled as sample data in the API/UI; stale and custom-source price states are exposed.

## What is not claimed

The complete third-party crop-history dataset has not been imported in this environment. The pretrained weights are not bundled or tested against field imagery here. No live government-price fetch was completed. The weather API was not accessed live. The test suite cannot substitute for those external checks or for agronomist validation.

## Data links

- Mandi prices (Government of India OGD): <https://www.data.gov.in/resource/current-daily-price-various-commodities-various-markets-mandi>
- Historical crop statistics mirror (repository declares CC0-1.0): <https://github.com/k0rn/India_Agri_Data>
- Model repository and pinned revision (MIT shown in repository metadata): <https://huggingface.co/wambugu71/crop_leaf_diseases_vit/tree/2b77473a26a2974a9bfb7f0c7880ed84f9b302df>
- Open-Meteo forecast API: <https://open-meteo.com/en/docs>
- FAO crop-water reference: <https://www.fao.org/4/S2022E/s2022e07.htm>


## Hackathon mandi-price provider update (18 October 2026)

KisanSaathi now defaults to the keyless community Mandi Price API at `https://mandi-api.onrender.com/v1`. It documents five supported states: Maharashtra, Uttar Pradesh, Punjab, Madhya Pradesh, and Karnataka. No API key is required for this provider. Use `python -m scripts.fetch_prices` to request all five states, or `python -m scripts.fetch_prices --state Punjab --commodity Wheat` for a smaller test.

The public docs are at `https://mandi-api.vercel.app/docs` and status at `https://mandi-api.vercel.app/status`. The provider reported automated ingestion trouble from 25 September through 12 October 2026, with a manual ingestion run on 13 October; this is why KisanSaathi must inspect the record-level `arrival_date` and never label an API response as today's rates without verifying those dates. Source attribution in the app identifies this as a community service sourcing open mandi data, not a government-operated API.

Live verification is still outstanding from this build environment because outbound DNS access to `mandi-api.onrender.com` failed. Automated client tests use mocked responses only. Run the command on a normal internet-connected laptop before the hackathon and review the latest arrival dates in its output and `/api/prices/status`.


## Daily mandi refresh in the final build

The project now starts an in-process background sync on FastAPI startup and repeats every 24 hours by default while the backend process remains running; before each run it takes a database lease, so with several workers only one refreshes. Configure with `MANDI_AUTO_REFRESH_ENABLED`, `MANDI_REFRESH_ON_STARTUP`, and `MANDI_REFRESH_INTERVAL_HOURS` in `backend/.env`. See `/api/prices/status` for the persisted last-run status. If the machine/service stops, the in-process scheduler does not run while stopped. Multi-worker or sleeping/serverless deployments should disable this scheduler and use one external scheduled job against the same persistent database. This integration was covered by mocked tests; live provider access still must be smoke-tested from the project host because this execution environment could not directly retrieve the provider's JSON endpoint.


## New planning and irrigation notes (this build)

- Current weather/1–7 day forecast is retrieved from Open-Meteo at request time; live access was not verified from this packaging environment. No API key is required for non-commercial prototype use under the published terms. Attribute the provider and review terms before commercial use.
- The Next Season Planner stores farmer-entered harvest/cost records under a private farm record key (server-issued, stored as a hash, sent only in POST bodies). It is a bearer key, not a verified account; do not store sensitive personal data.
- Historical aggregate prices are not individual mandi quotes. The planner calculates an indicative gross/net return only when a candidate has at least 12 historical price observations spanning 180 days, at least two local yield observations, and a farmer-entered candidate cost for net return. When the state has at least 12 observations across at least 2 years in the season's harvest months, the harvest-month median is used; otherwise the all-date median, labelled as such.
- Irrigation runs a daily FAO-56 root-zone water balance (typical soil water-holding capacity × root depth, readily available water, effective rain, crop use) from the forecast and the farmer's soil and moisture answers. It does not model runoff/percolation, sensors or paddy ponding.
- Remedies are bilingual management guidance and safety cues, not a diagnosis guarantee or pesticide prescription. Verify with local KVK/agricultural experts.
