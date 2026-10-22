# KisanSaathi: Crop Planning, Weather and Agronomy Method

This note documents what the current code actually computes, the data-source boundaries, and what a hackathon demonstration must not claim.

## 1. Next Season Planner

### Inputs

The planner accepts state, district, current crop/season, target season, area, primary issue, water availability, broad soil type, optional pH, optional measured yield, optional farmer-reported sale price, optional total cost, itemised candidate costs, and notes. Harvest records may include harvested tonnes, yield per hectare, sale price and per-hectare input/cultivation costs.

Harvest records are tied to a private farm record key issued by the server (`POST /api/planning/farm-ref`, 32 random characters). Only its SHA-256 hash is stored, and records are returned only when the key is presented in a POST body (never in a URL). The key is a bearer secret, not a verified identity: anyone holding it can read those records. Records are checked before saving: the season year can be at most one year ahead, and yield × area must agree with harvested tonnes within 5%.

### Evidence used

1. **District/crop/season production history:** imported crop area and production records. Yield may be derived as production divided by area where units are valid. It is a regional historical benchmark; it does not represent a forecast for the specific farm.
2. **Current mandi quotes:** `MandiPrice` stores dated records by state, district, market, commodity, variety, grade and arrival date. This helps display current available market reports but can be stale.
3. **Historical market trend:** `MandiPriceHistory` is a separate table for state + commodity + observation-date aggregated price data returned by the community Mandi Price API. These values are not a single mandi's price. `python -m scripts.fetch_mandi_history --state Punjab --commodity Wheat --years 5` imports only the dates actually returned by the provider; it does not generate missing dates or fill unobserved years.
4. **Farmer-reported outcomes and costs:** farm-season records supply personal observed yield, sale price and entered costs. Itemised cost categories include seed, fertiliser, crop protection, labour, irrigation, machinery, harvest, transport and other expenses.
5. **Suitability checks:** the planner applies broad candidate crop metadata for water demand, indicative soil preference, soil pH ranges, crop group/rotation, and a target season. These are screening rules, not a validated agro-climatic crop model. They should not override ICAR/KVK/state extension recommendations.
   - Rainfed fields exclude high-water crops; limited water excludes them with a caution. Rainfed or limited-water **Kharif rice is not excluded** (about half of India's rice area is rainfed) but carries a warning about monsoon dependence.
   - **Rotation is used:** each candidate shows whether it is in the same crop family as the current crop (pests and diseases carry over), a pulse after a non-pulse (soil nitrogen), or a different family.
   - Zaid is treated as the summer season; seasons are matched across spelling variants.

### Crop data quality

- Crop names are matched through one alias table (`crop_catalog.py`), so "Paddy", "Rice", "Dhan" and "Paddy(Dhan)(Common)" are one crop.
- Cotton bales (170 kg lint) and jute/mesta/sunn hemp bales (180 kg) are converted to tonnes; coconut is counted in nuts and is kept out of tonne totals and yield.
- Years with physically impossible yields (above a crop-specific ceiling) are left out and counted.
- Each answer reports the last year in the data and its age. The default community file ends around 2012-13, so the planner warns that yields are a historical pattern. Importing the DES / India Data Portal district APY series (to about 2022-23) removes that warning for recent years.

### Price used for revenue

1. If the state has at least 12 history observations across at least 2 years in the target season's usual **harvest months** (Kharif: Oct–Jan; Rabi: Mar–Jun; Zaid/summer: May–Jul), the harvest-month median is used.
2. Otherwise, if there are at least 12 observations spanning at least 180 days, the all-date median is used and labelled as such.
3. Otherwise no revenue or net return is calculated. A single current quote is never used as a next-season price.

A current quote older than 30 days (`PLANNER_PRICE_MAX_AGE_DAYS`) is shown for context only.

### Ranking

Crops are **ranked by estimated net return only when at least two crops have a net return** (which needs yield history, a usable price and the farmer's cost for that crop). Otherwise they are listed by area sown in the latest year, with the note "this order is not a recommendation" and no rank numbers. Every data gap comes with a code so the screen can show it in Hindi or English.

### Economics and limitations

The app separates yield, sale-price and cost issues. It should not recommend a crop because its current quote is higher alone. A net-return estimate only makes sense where a candidate crop has an evidence-supported yield/price and an appropriate cultivation-cost estimate. Missing candidate costs must remain marked as missing; do not silently borrow another crop's costs or create synthetic profits.

Historical aggregate data can be sparse, inconsistent in naming/units, not area-specific, and subject to provider limitations. The planner is a transparent decision-support MVP, not a trained profit predictor. A median/range of observed historic price points is descriptive—not a guaranteed future price forecast. “Insufficient data” is an acceptable and often safer answer.

### Intended authoritative context sources

- Directorate of Economics & Statistics agricultural production/yield query: https://data.desagri.gov.in/website/apy-query-report-web
- DES cost-of-cultivation studies: https://desagri.gov.in/divisions-cell/cost-studies-cs/
- ICAR–CRIDA district contingency plans: https://icar-crida.res.in/ccp.html
- Soil Health Card portal: https://soilhealth.dac.gov.in/
- IMD district agrometeorological advisories: https://mausam.imd.gov.in/responsive/agromet_adv_ser_district_current_en.php
- e-NAM historical dashboard: https://www.enam.gov.in/web/dashboard/Historical

These sources are linked as references; they are not all programmatically ingested by this prototype. Any use of official downloads should record licence, source URL, retrieval time, unit definitions, and coverage dates.

## 2. Live weather

`GET /api/weather/forecast?location=Ludhiana&state=Punjab&days=7` makes a request to Open-Meteo when called. It uses the geocoding service to resolve an Indian location, then returns current conditions, daily precipitation/rain probability, min/max temperatures, wind and reference ET0 where provided. The response includes a provider label, source URL and retrieval timestamp.

This is **live retrieval of current conditions and a model forecast**, not a continuous sensor feed and not an official IMD-issued warning. Forecast values can change. The free Open-Meteo API is intended for non-commercial use under its published terms and attribution/licensing conditions; check the latest terms before a public/commercial release: https://open-meteo.com/en/docs

## 3. Irrigation estimate

The estimate is a daily FAO-56 root-zone water balance over the seven forecast days:

| Step | Formula / value |
| --- | --- |
| Crop use | `ETc = Kc × ET0` (FAO-56 Kc for crop and stage) |
| Water held per metre of soil | sandy 80, red 130, unknown 140, loamy 155, alluvial/clayey/black 160 mm/m (mid-range of FAO-56 Table 19: θFC − θWP) |
| Root depth `Zr` | FAO-56 Table 22 (lower values), scaled by stage (initial 0.30, development 0.65, mid and late 1.0 of full depth) |
| Total available water | `TAW = water per metre × Zr` |
| Readily available water | `RAW = p × TAW`, `p` from FAO-56 Table 22 adjusted by `+0.04 × (5 − ETc)`, kept within 0.1–0.8 |
| Start | wet = 0 depletion; normal/unknown = 50% of RAW used; dry = all RAW used |
| Each day | depletion += ETc − effective rain (soil-dependent share of `precipitation_sum`) |
| Irrigation | when depletion > RAW: net = depletion (refill), gross = net ÷ efficiency; litres = gross mm × area ha × 10,000 |

The farmer reports field moisture as dry/normal/wet/unknown; it is not instrument-measured moisture. With "unknown" the app assumes half of RAW is used, says so, and often finds no irrigation is needed within seven days — which is the honest answer when moisture is not known. The response also gives the old simple deficit (`Σ ETc − effective rain`) for comparison.

Weather alerts follow IMD categories: moderate rain 15.6–64.4 mm, heavy 64.5–115.5, very heavy 115.6–204.4, extremely heavy ≥ 204.5 mm/day; heat 40 °C, severe heat 45 °C; spraying is discouraged above 15 km/h wind and a strong-wind alert is given at 40 km/h.

References:
- FAO-56 crop-water methodology and crop coefficients: https://www.fao.org/4/X0490E/x0490e0a.htm and https://www.fao.org/4/X0490E/x0490e0b.htm
- Open-Meteo API documentation: https://open-meteo.com/en/docs

Known omissions: no measured field capacity/wilting point for the actual field, groundwater contribution, irrigation schedule constraints, runoff/percolation model, crop-specific rice puddling/ponding demand, or verified farm sensors. The rice calculator therefore does not prescribe a generic paddy irrigation volume. Outputs are planning estimates and should be checked against actual field conditions and local advice.

## 4. Crop Doctor remedies

Every supported model class has bilingual management information grouped into immediate steps, prevention, monitoring, crop-care, escalation and chemical safety. The app does not prescribe pesticide products or doses. An image-level classifier is not a field diagnosis; users should inspect several plants, check the diagnosis locally and consult a KVK/agriculture officer before chemical intervention. A “healthy” leaf prediction does not certify that the whole field is healthy. An “Invalid” class is not a reliable universal detector for arbitrary non-leaf images, so the app adds its own checks: the share of plant-coloured pixels must be at least 10%, the top label must not be Invalid, confidence must reach the threshold (default 0.60), and the top two diseases must be at least 15 points apart. Otherwise the result is "not sure" with the reason. Field accuracy must be measured with `python -m scripts.evaluate_model <folder>` on labelled local photos before quoting any accuracy figure.

## 5. Mandi prices and historical series

- Current quotes are imported into `MandiPrice`, retaining the original market `arrival_date` and source.
- Historical aggregate data is imported into `MandiPriceHistory`; do not mix those aggregate rows into individual-market quote displays.
- The community provider documents a five-state scope and can experience stale or incomplete ingestion. It is not operated by the Government of India and this project has no provider SLA. See its API docs/status: https://mandi-api.vercel.app/docs and https://mandi-api.vercel.app/status.
- Store/inspect actual market dates, source attribution and retrieval status. A recent fetch timestamp does not mean the market observation is recent.
- The automatic updater runs inside the FastAPI process, but it first takes a database lease (`scheduler_leases`), so with several workers only one refreshes at a time. For large deployments, disable it on web processes and run one external scheduled job.
- Mandi rows older than `PRICE_RETENTION_DAYS` (730) are removed after each sync; a price older than `PRICE_STALE_DAYS` (3, Indian time) is labelled with its age.

### Trader offer versus the mandi

The highest mandi quote is not what the farmer takes home. The Mandi prices page asks for the trader's price, the quantity and (optionally) transport, commission/mandi fee (%) and loading/other costs, then shows: trader total; mandi total at the best modal price; each cost subtracted; the mandi amount after costs (total and per kg); and which option gives more, by how much. The modal price is from the latest report and is not a promise of the price on the day of sale.

## 6. Validation before real farmer use

- Inspect source date ranges, units, crop aliases, geography and missingness after every import.
- Backtest crop comparison by time: recommendations for a past season must use only data that would have existed before that season.
- Validate crop suitability and remedy content with local KVK/extension expertise.
- Test model precision/recall by supported class on held-out, field-like images. A few successfully classified examples do not establish real-world accuracy.
- Before storing sensitive real-farmer records publicly: connect a real SMS gateway for OTP, move rate limits to a shared store, add backups, monitoring and a privacy policy. (PIN hashing, lockout, rate limits, expiry and optional OTP are already in place.)
