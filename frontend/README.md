# KisanSaathi frontend

Plain HTML, CSS and JavaScript, with no framework and no build step. FastAPI serves this folder at `http://localhost:8000/`, so the pages and the API share one address.

## Pages

| Page | Script | API it uses |
| --- | --- | --- |
| `index.html` | `js/home.js` | `/api/prices/status`, `/states`, `/commodities`, `/best` (live "latest best price" card; hidden when there is no data) |
| `disease.html` | `js/disease.js` | `POST /api/disease/predict` (form field `file`) |
| `prices.html` | `js/prices.js` | `/api/prices/status`, `/states`, `/commodities`, `/best`, `/history` |
| `crops.html` | `js/crops.js` | `/api/crops/status`, `/states`, `/districts`, `/seasons`, `/history` |
| `planning.html` | `js/planning.js` | `POST /api/planning/farm-ref`, `/recommendations`, `/records`, `/records/latest`; `/api/crops/states`, `/districts` |
| `irrigation.html` | `js/irrigation.js` | `POST /api/irrigation/estimate` |
| `market.html` | `js/market.js` | `GET /api/auth/config`, `POST /api/auth/otp/request`, `/verify`, `POST /api/listings`, `GET /api/listings`, `POST /api/listings/mine`, `POST /api/listings/{id}/interest`, `PATCH /api/listings/{id}/sold`, `POST /api/listings/{id}/withdraw` |

Shared scripts load first on every page, all with `defer`:

- `js/names.js`: generated Hindi name tables for states, districts, crops, commodities, varieties, grades, seasons and mandi towns. Do not edit by hand; edit `backend/app/data/` and run `python -m scripts.build_name_tables` from `backend/`.
- `js/i18n.js`: all Hindi and English text, `t()` and `tf()`, the language switch, and the name helpers `stateName()`, `districtName()`, `marketName()`, `cropLabel()`, `varietyLabel()`, `seasonLabel()` and `translitHi()`. Hindi is the default.
- `js/api.js`: `apiGet`, `apiSend` and `apiUpload`, error messages (every server message is mapped to a text key in `SERVER_MESSAGES`, so it appears in Hindi), the safe `el()` DOM builder, icons and number/date formatting.

## Design system (`css/style.css`)

- **Colours:** forest green `#2b6844` for actions, harvest gold `#c18b2d` for highlights, soil red `#9b4537` for problems and costs, warm white `#f7f8f3` page background (`css/style.css` and `css/redesign.css`).
- **Wordmark:** "KisanSaathi" first, "किसान साथी" beside it; on screens up to 520 px the Hindi name sits under the English one.
- **Type:** Tiro Devanagari Hindi for headings and Mukta for text. Both are stored in `fonts/` (cut down to Hindi and English characters), so the app looks the same offline. Licence: SIL Open Font License (`fonts/OFL-*.txt`).
- **Layout:** mobile first.
  - Phones and tablets get a bottom tab bar. From 1100 px wide it becomes a top bar.
  - From 900 px wide, tool pages use two columns: inputs on the left, results on the right.
- **Motion:** only the scan line while a leaf photo is checked, plus small bar animations. People who turn off animations in their device settings don't see them.

## Rules to keep

- Insert user-typed text with `el()` or `textContent`, never `innerHTML`.
- Never store or send the farmer PIN in a URL or `localStorage`. It is kept only in page memory.
- Always show the market report date with prices. Old data is labelled with its age and never called "today".
- New text goes into both `en` and `hi` in `js/i18n.js` (the test `tests/test_frontend_text.py` fails if one is missing).
- Show place and crop names through the name helpers, never the raw database value. Put the English text inside the HTML element as a fallback (the backend tests check for it on `index.html` and `crops.html`).
