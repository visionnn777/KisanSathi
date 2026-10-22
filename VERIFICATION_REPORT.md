# KisanSaathi — Verification and limitations

## Local checks completed for the master update (18 October 2026)

- Backend automated suite: **115 tests passed** (`python -m pytest -q` from `backend/`), up from 82.
- Python compilation: passed (`python -m compileall -q app scripts tests`).
- Frontend JavaScript syntax: every `frontend/js/*.js` file passed `node --check`.
- English/Hindi texts: **566 English keys and 566 Hindi keys**, identical sets; every key used by the HTML and scripts exists, and every planner gap code, irrigation reason, Crop Doctor reason, listing status and mapped server message has both texts (`tests/test_frontend_text.py`).
- Hindi place names: all **672 state–district pairs** in the crop dataset resolve to a Hindi name (`tests/test_names.py`).
- Real-data test: 685 real rows from the crop dataset (cotton bales, coconut nuts, rice, wheat) import with the right units and yields (`tests/test_real_data.py`).
- Full import of the real 173,066-row crop file: 7,248 bale rows converted to tonnes, 1,471 coconut rows kept in nuts, 0 rows with unknown units.
- Browser check with Playwright (Chromium) against the real app, the real crop file, the sample mandi prices and stand-ins for the leaf model and Open-Meteo, in Hindi and English at 390 px (phone) and 1366 px (laptop), on all seven pages:
  - no page wider than the screen;
  - in Hindi, no English words on screen except proper names (KisanSaathi, KVK, OTP, SMS, PIN, ICAR-CRIDA, FAO-56, Open-Meteo, the GitHub repository name) and units such as °C; in English, no Hindi except the logo name;
  - wordmark shows "KisanSaathi" first and "किसान साथी" beside it (laptop) or under it (phone);
  - trader offer ₹22/kg for 1,000 kg against Patiala at ₹25.30/kg, with ₹1,500 transport, 2.5% commission and ₹400 other: trader ₹22,000, mandi ₹25,300 − ₹1,500 − ₹633 − ₹400 = ₹22,768 (₹22.77/kg), "about ₹768 more at the mandi" — checked by hand;
  - Sell & buy with OTP on: posting is refused until the number is verified; weak PIN 12345678 refused; wrong PIN refused; listing posted, shown with "open until" date, withdrawn and shown as "Removed";
  - Hindi buyer search "गेहूँ" / "गेहूं" + "लुधियाना" finds the Ludhiana wheat listings; village names show as जगरांव, समराला;
  - Crop Doctor: a blue (non-leaf) photo gives "does not look like a leaf"; an Invalid result gives "could not match"; a disease result shows the field-photo caution;
  - Next Season Planner (Ludhiana, Kharif): summary first, data age warning (records end 2012-13), list by area without rank numbers because fewer than two net returns exist;
  - Irrigation (Ludhiana, maize initial, dry soil, 1 ha, 60%): one watering day, 50.7 mm gross = 5,07,000 litres, root-zone numbers shown.
- Contrast ratios for core colour tokens (from the earlier build): primary green on white 6.63:1; main text on paper 11.44:1; muted text on paper 4.58:1.

## Not verified by these local checks

- A fresh real Hugging Face model download and full model inference were not performed from the packaging environment. The actual pinned artifact is downloaded when you run `python -m scripts.download_model` on your computer.
- Live Open-Meteo geocoding/forecast requests were not executed during this packaging run; weather tests use mock responses. Verify on an internet-connected device.
- Live Mandi Price API calls/history downloads were not executed during this packaging run; provider adapter tests use mock responses. Run the relevant `scripts.fetch_prices` and `scripts.fetch_mandi_history` commands from `backend/` and inspect observed dates.
- The complete historical crop-production CSV is not bundled. Download/import it using `python -m scripts.setup_crop_data`, or import the newer DES / India Data Portal district APY file with `--file`.
- Real SMS delivery of OTP codes: only the demo console provider is included.
- Accuracy of Crop Doctor on Indian field photos: run `python -m scripts.evaluate_model` on your own labelled photos; no field accuracy figure is claimed.
- Hindi spellings for mandis and villages that are not in the name table are phonetic and may differ from local usage.
- No independent agronomic validation has been performed on the crop ranking, irrigation outputs or remedy content. Consult KVK/extension personnel before real farm decisions.

## Practical safety boundaries

- The Next Season Planner is transparent rule-based decision support, not a validated profit prediction. Returns are indicative; crops are ranked only when at least two have a net return, and every data gap is shown.
- Live weather is requested from Open-Meteo at request time; it is a model forecast, not an official IMD warning. Alert thresholds follow IMD categories. Its free API is intended for non-commercial use and requires attribution.
- Irrigation is a daily FAO-56 root-zone water balance using typical soil values for the chosen soil type, not a sensor reading; paddy ponding/percolation is not modelled, so rice gets no volume.
- Crop Doctor results are image-level screening, not confirmed diagnoses; it does not prescribe pesticide products or doses.
- Farm records are protected by a private bearer key, not a verified account. Direct Market uses hashed PINs, lockout, rate limits, expiry and optional OTP; rate limits are per server process.
- The default Mandi Price API is a community service for five states, not a government-operated service or guaranteed-SLA feed. The original market arrival date is shown and stale data is flagged.
