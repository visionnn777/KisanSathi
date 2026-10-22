/* Crop Insights: historical area, production and yield from the imported crop-production CSV.
   Owner: Member D (backend endpoints by Member C). Uses /api/crops/status, /states, /districts,
   /seasons and /history. These are past records, never a planting recommendation. */

const stateSelect = document.getElementById("state");
const districtSelect = document.getElementById("district");
const seasonSelect = document.getElementById("season");
const searchButton = document.getElementById("searchCrops");
const datasetStatus = document.getElementById("datasetStatus");
const statusBox = document.getElementById("status");
const resultsBox = document.getElementById("results");
let states = [];
let districts = [];
let seasons = [];
let metadata = null;
let lastResult = null;

function num(value, digits = 1) {
  if (value === null || value === undefined || isNaN(value)) return "—";
  return Number(value).toLocaleString("en-IN", { maximumFractionDigits: digits });
}

function fillOptions(select, values, placeholderKey, selected = "", labelFn = v => v) {
  const options = values.map(v => ({ v, label: labelFn(v) }))
    .sort((a, b) => a.label.localeCompare(b.label, getLang() === "hi" ? "hi" : "en"));
  select.replaceChildren(
    el("option", { value: "" }, t(placeholderKey)),
    ...options.map(({ v, label }) => el("option", { value: v, selected: v === selected }, label)),
  );
}
const districtLabel = d => districtName(stateSelect.value, d);

/* ---------------------------------------------------------------- Dataset status */
function renderDatasetStatus() {
  if (!metadata) return;
  if (!metadata.available) {
    datasetStatus.replaceChildren();
    resultsBox.replaceChildren(el("div", { class: "panel" },
      el("p", { class: "panel-title" }, t("crop_setup_title")),
      el("p", { class: "panel-sub" }, t("crop_setup_body")),
      el("code", { class: "code" }, metadata.setup_command || "python -m scripts.setup_crop_data"),
    ));
    return;
  }
  const line = tf(metadata.states === 1 ? "crop_status_line_one" : "crop_status_line", {
    rows: num(metadata.rows, 0), states: metadata.states,
    first: metadata.first_year ?? "—", last: metadata.latest_year ?? "—",
  });
  if (metadata.is_old) {
    showNotice(datasetStatus, "warn", `${line} ${tf("crop_data_old", { age: metadata.data_age_years })}`);
  } else {
    showNotice(datasetStatus, "info", line);
  }
  if (metadata.needs_reimport) datasetStatus.append(el("p", { class: "panel-sub" }, t("crop_needs_reimport")));
}

/* ---------------------------------------------------------------- Results */
function changeCell(pct) {
  if (pct === null || pct === undefined) return el("span", { class: "change flat" }, "—");
  const kind = pct > 0 ? "up" : pct < 0 ? "down" : "flat";
  const sign = pct > 0 ? "+" : pct < 0 ? "−" : "";
  return el("span", { class: `change ${kind}` }, `${sign}${num(Math.abs(pct), 1)}%`);
}

function renderResults() {
  if (!metadata || !metadata.available) return;
  if (!lastResult) {
    resultsBox.replaceChildren(el("div", { class: "placeholder" }, emptyState("chart", t("crop_empty_title"), t("crop_empty_body"))));
    return;
  }
  if (!lastResult.crops || !lastResult.crops.length) {
    resultsBox.replaceChildren(el("div", { class: "placeholder" }, emptyState("search", t("crop_no_results"))));
    return;
  }

  const r = lastResult;
  const maxArea = Math.max(...r.crops.map(c => c.latest_area_ha || 0)) || 1;
  const summary = el("section", { class: "summary", "aria-labelledby": "cropSummary" },
    el("h2", { class: "summary-title", id: "cropSummary" }, tf("crop_summary", { district: districtName(r.state, r.district), state: stateName(r.state) })),
    el("p", { class: "summary-sub" }, r.season ? seasonLabel(r.season) : t("crop_all_seasons")),
    el("div", { class: "summary-chips" },
      el("span", { class: "tag" }, icon("calendar", "sm"), tf("crop_period", { first: r.first_year, last: r.latest_year })),
      el("span", { class: "tag" }, icon("leaf", "sm"), r.count === 1 ? t("crop_count_one") : tf("crop_count", { n: r.count })),
    ),
  );

  const head = el("thead", {}, el("tr", {},
    el("th", { scope: "col" }, t("crop_col_crop")),
    el("th", { scope: "col" }, t("crop_col_year")),
    el("th", { scope: "col", class: "r" }, `${t("crop_area")} (${t("unit_ha")})`),
    el("th", { scope: "col", class: "r" }, `${t("crop_production")} (${t("unit_t")})`),
    el("th", { scope: "col", class: "r" }, `${t("crop_yield")} (${t("unit_tha")})`),
    el("th", { scope: "col", class: "r" }, t("crop_col_change")),
  ));
  const body = el("tbody", {}, r.crops.map(c => el("tr", {},
    el("td", { class: "first" },
      el("p", { class: "crop-name" }, cropLabel(c.crop)),
      el("p", { class: "crop-meta" }, [c.latest_season ? seasonLabel(c.latest_season) : null, tf("crop_records", { n: c.observations })].filter(Boolean).join(", ")),
      c.production_unit_note === "converted_from_bales" ? el("p", { class: "crop-meta" }, t("crop_bales_note")) : null,
      c.implausible_years_excluded ? el("p", { class: "crop-meta" }, tf("crop_outliers_note", { n: c.implausible_years_excluded })) : null,
    ),
    el("td", { class: "year num", "data-label": t("crop_col_year") }, c.latest_year),
    el("td", { class: "r num", "data-label": `${t("crop_area")} (${t("unit_ha")})` },
      el("span", {}, num(c.latest_area_ha, 1)),
      el("div", { class: "area-bar", "aria-hidden": "true" }, el("span", { style: `width:${Math.max(2, Math.round((c.latest_area_ha || 0) / maxArea * 100))}%` })),
    ),
    el("td", { class: "r num", "data-label": `${t("crop_production")} (${t("unit_t")})` }, num(c.latest_production_tonnes, 1)),
    el("td", { class: "r num", "data-label": `${t("crop_yield")} (${t("unit_tha")})` }, num(c.latest_yield_tonnes_per_ha, 2)),
    el("td", { class: "r", "data-label": t("crop_col_change") }, changeCell(c.production_change_pct_since_first_record)),
  )));

  const notes = [];
  if (r.is_old) notes.push(el("div", { class: "notice warn" }, icon("alert", "sm"), el("span", {}, tf("crop_period_old", { last: r.latest_year, age: r.data_age_years }))));
  if (r.crops_without_tonnes && r.crops_without_tonnes.length) {
    notes.push(el("p", { class: "meta-line" }, tf("crop_nuts_note", { crops: r.crops_without_tonnes.map(cropLabel).join(", ") })));
  }
  const table = el("section", { class: "panel", "aria-labelledby": "cropSummary" },
    ...notes,
    el("table", { class: "crop-table" }, head, body),
    el("p", { class: "meta-line" }, t("crop_sorted")),
  );
  resultsBox.replaceChildren(summary, table);
}

/* ---------------------------------------------------------------- Loading */
async function loadDistricts(state) {
  districts = [];
  seasons = [];
  fillOptions(districtSelect, [], "crop_choose_district");
  fillOptions(seasonSelect, [], "crop_all_seasons");
  districtSelect.disabled = true;
  seasonSelect.disabled = true;
  searchButton.disabled = true;
  lastResult = null;
  renderResults();
  if (!state) return;
  try {
    districts = await apiGet("/api/crops/districts", { state });
    fillOptions(districtSelect, districts, "crop_choose_district", "", districtLabel);
    districtSelect.disabled = false;
  } catch (err) {
    showNotice(statusBox, "error", err.message);
  }
}

async function loadSeasons(state, district) {
  seasons = [];
  fillOptions(seasonSelect, [], "crop_all_seasons");
  seasonSelect.disabled = true;
  searchButton.disabled = !district;
  if (!state || !district) return;
  try {
    seasons = await apiGet("/api/crops/seasons", { state, district });
    fillOptions(seasonSelect, seasons, "crop_all_seasons", "", seasonLabel);
    seasonSelect.disabled = false;
  } catch (err) {
    showNotice(statusBox, "error", err.message);
  }
}

async function searchHistory() {
  const state = stateSelect.value;
  const district = districtSelect.value;
  if (!state || !district) return;
  statusBox.replaceChildren();
  showLoading(resultsBox);
  searchButton.disabled = true;
  try {
    lastResult = await apiGet("/api/crops/history", { state, district, season: seasonSelect.value || undefined, limit: 20 });
    renderResults();
    if (window.matchMedia("(max-width: 899px)").matches) resultsBox.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (err) {
    lastResult = null;
    renderResults();
    showNotice(statusBox, "error", err.message);
  } finally {
    searchButton.disabled = false;
  }
}

stateSelect.addEventListener("change", () => loadDistricts(stateSelect.value));
districtSelect.addEventListener("change", () => loadSeasons(stateSelect.value, districtSelect.value));
searchButton.addEventListener("click", searchHistory);

document.addEventListener("langchange", () => {
  fillOptions(stateSelect, states, "crop_choose_state", stateSelect.value, stateName);
  fillOptions(districtSelect, districts, "crop_choose_district", districtSelect.value, districtLabel);
  fillOptions(seasonSelect, seasons, "crop_all_seasons", seasonSelect.value, seasonLabel);
  renderDatasetStatus();
  renderResults();
});

(async function start() {
  showLoading(resultsBox);
  try {
    metadata = await apiGet("/api/crops/status");
    renderDatasetStatus();
    if (!metadata.available) {
      stateSelect.disabled = true;
      return;
    }
    states = await apiGet("/api/crops/states");
    fillOptions(stateSelect, states, "crop_choose_state", "", stateName);
    renderResults();
  } catch (err) {
    resultsBox.replaceChildren();
    showNotice(statusBox, "error", err.message);
  }
})();
