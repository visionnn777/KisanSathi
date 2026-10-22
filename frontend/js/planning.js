/* Next Season Planner: transparent comparison of district crop history, dated prices,
   farmer-recorded yield/costs and broad soil/water constraints. Not a profit predictor.
   Every message from the server comes with a code, so it is shown in Hindi or English. */
const planForm = document.getElementById("nextSeasonForm");
const planStatus = document.getElementById("plannerStatus");
const planResults = document.getElementById("plannerResults");
const saveRecordButton = document.getElementById("saveRecord");
const stateSelect = document.getElementById("state");
const districtSelect = document.getElementById("district");
const farmKeyValue = document.getElementById("farmKeyValue");
const farmKeyInput = document.getElementById("farmKeyInput");
const FARM_KEY_STORE = "kisansaathi_farm_reference_v1";
let lastPlan = null;
let lastCostInputs = {};
let plannerStates = [];
let plannerDistricts = [];

function optionalNumber(value) {
  if (value === undefined || value === null || String(value).trim() === "") return null;
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
}
function pnum(value, digits = 2) {
  if (value === null || value === undefined || !Number.isFinite(Number(value))) return "—";
  return Number(value).toLocaleString("en-IN", { maximumFractionDigits: digits });
}
const COST_PART_NAMES = [
  "seed_cost_rs_per_ha", "fertiliser_cost_rs_per_ha", "crop_protection_cost_rs_per_ha",
  "labour_cost_rs_per_ha", "irrigation_cost_rs_per_ha", "machinery_cost_rs_per_ha",
  "harvest_cost_rs_per_ha", "transport_cost_rs_per_ha", "other_cost_rs_per_ha",
];
function readCostParts() {
  const result = {};
  for (const name of COST_PART_NAMES) {
    const value = optionalNumber(val(name));
    if (value !== null) result[name] = value;
  }
  return result;
}
let breakdownHasCalculatedTotal = false;
function syncTotalCostFromParts() {
  const parts = readCostParts();
  if (Object.keys(parts).length) {
    const total = Object.values(parts).reduce((sum, value) => sum + value, 0);
    planForm.elements.current_cost_rs_per_ha.value = String(Math.round(total * 100) / 100);
    breakdownHasCalculatedTotal = true;
  } else if (breakdownHasCalculatedTotal) {
    planForm.elements.current_cost_rs_per_ha.value = "";
    breakdownHasCalculatedTotal = false;
  }
}

/* ---------------------------------------------------------------- Private farm record key */
function storedFarmKey() {
  try { return localStorage.getItem(FARM_KEY_STORE) || ""; } catch (_) { return ""; }
}
function showFarmKey(key) { farmKeyValue.textContent = key || "—"; }
async function farmReference() {
  let key = storedFarmKey();
  if (key && key.length >= 22) return key;
  const issued = await apiSend("POST", "/api/planning/farm-ref", {});
  key = issued.farm_ref;
  try { localStorage.setItem(FARM_KEY_STORE, key); } catch (_) { /* the key still works for this visit */ }
  showFarmKey(key);
  return key;
}
document.getElementById("farmKeyApply").addEventListener("click", () => {
  const key = farmKeyInput.value.trim();
  if (key.length < 22) { showNotice(planStatus, "error", t("planner_key_short")); return; }
  try { localStorage.setItem(FARM_KEY_STORE, key); } catch (_) { /* ignore */ }
  showFarmKey(key);
  farmKeyInput.value = "";
  showNotice(planStatus, "ok", t("planner_key_saved"));
});

/* ---------------------------------------------------------------- Form helpers */
function val(name) { return planForm.elements[name] ? String(planForm.elements[name].value).trim() : ""; }
function fillPlaceSelect(select, values, labelFn, placeholderKey, selected = "") {
  const options = values.map(v => ({ v, label: labelFn(v) })).sort((a, b) => a.label.localeCompare(b.label, getLang() === "hi" ? "hi" : "en"));
  select.replaceChildren(el("option", { value: "" }, t(placeholderKey)),
    ...options.map(({ v, label }) => el("option", { value: v, selected: v === selected }, label)));
}
async function loadPlannerDistricts(selected = "") {
  plannerDistricts = [];
  fillPlaceSelect(districtSelect, [], v => v, "crop_choose_district");
  districtSelect.disabled = true;
  if (!stateSelect.value) return;
  try {
    plannerDistricts = await apiGet("/api/crops/districts", { state: stateSelect.value });
    fillPlaceSelect(districtSelect, plannerDistricts, d => districtName(stateSelect.value, d), "crop_choose_district", selected);
    districtSelect.disabled = false;
  } catch (err) { showNotice(planStatus, "error", err.message); }
}
async function loadPlannerStates() {
  try {
    const status = await apiGet("/api/crops/status");
    if (!status.available) {
      showNotice(document.getElementById("datasetStatus"), "warn", t("planner_dataset_missing"));
      return;
    }
    if (status.is_old) showNotice(document.getElementById("datasetStatus"), "warn", tf("crop_period_old", { last: `${status.latest_year}-${String(status.latest_year + 1).slice(-2)}`, age: status.data_age_years }));
    plannerStates = await apiGet("/api/crops/states");
    const saved = storageGet("plannerState");
    const preferred = plannerStates.find(s => s === saved) || plannerStates.find(s => placeKey(s) === "PUNJAB") || "";
    fillPlaceSelect(stateSelect, plannerStates, stateName, "crop_choose_state", preferred);
    await loadPlannerDistricts(storageGet("plannerDistrict"));
  } catch (err) { showNotice(planStatus, "error", err.message); }
}
stateSelect.addEventListener("change", () => { storageSet("plannerState", stateSelect.value); loadPlannerDistricts(); });
districtSelect.addEventListener("change", () => storageSet("plannerDistrict", districtSelect.value));

async function buildPayload(costs = {}) {
  return {
    farm_ref: await farmReference(),
    state: val("state"), district: val("district"), current_crop: val("current_crop"),
    current_season: val("current_season"), target_season: val("target_season"),
    area_ha: Number(val("area_ha")),
    actual_yield_t_per_ha: optionalNumber(val("actual_yield_t_per_ha")),
    actual_sale_price_rs_per_qtl: optionalNumber(val("actual_sale_price_rs_per_qtl")),
    current_cost_rs_per_ha: optionalNumber(val("current_cost_rs_per_ha")),
    candidate_costs_rs_per_ha: costs,
    primary_issue: val("primary_issue") || "unknown",
    water_availability: val("water_availability") || "unknown",
    soil_type: val("soil_type") || "unknown", soil_ph: optionalNumber(val("soil_ph")), notes: val("notes") || null,
  };
}

/* ---------------------------------------------------------------- Rendering */
function gapText(item) {
  const key = `gap_${item.code}`;
  const params = { ...item.params };
  if (params.crop) params.crop = cropLabel(params.crop);
  if (params.state) params.state = stateName(params.state);
  return t(key) === key ? item.code : tf(key, params);
}
function gapList(codes) {
  if (!codes || !codes.length) return null;
  return el("ul", { class: "advice" }, codes.map(item => el("li", {}, gapText(item))));
}
function renderEmpty() {
  planResults.replaceChildren(el("div", { class: "placeholder" }, emptyState("sprout", t("planner_results"), t("planner_history_needed"))));
}
function planMetric(label, value) {
  return el("div", { class: "metric" }, el("p", { class: "metric-label" }, label), el("p", { class: "metric-value num" }, value));
}
function kv(label, value) {
  return el("p", { class: "panel-sub" }, `${label}: `, el("strong", {}, value));
}
function waterNeedText(code) { return t(`water_need_${String(code || "unknown").replace(/-/g, "_")}`); }
function soilFitText(code) {
  return code === "likely_match" ? t("planner_fit_likely") : code === "review_soil_fit" ? t("planner_fit_review") : t("planner_fit_unknown");
}
function rotationText(code) { return t(`rotation_${code || "unknown"}`); }
function priceAgeText(days) { return days == null ? "" : ` (${tf("pr_old", { n: pnum(days, 0) })})`; }

function candidateCard(c, idx, ranked) {
  const gross = c.estimated_gross_revenue_rs_per_ha;
  const net = c.estimated_net_return_rs_per_ha;
  const costId = `candidate-cost-${idx}`;
  const harvestWin = c.harvest_month_price;
  return el("article", { class: "panel candidate-card" },
    el("div", { class: "rank" },
      ranked ? el("span", { class: "rank-no" }, String(idx + 1)) : el("span", { class: "rank-no plain" }, icon("sprout", "sm")),
      el("div", {},
        el("h3", { class: "rank-name" }, cropLabel(c.crop)),
        el("p", { class: "rank-sub" }, `${t("planner_water_need")}: ${waterNeedText(c.water_need)} · ${soilFitText(c.soil_fit)}`),
        c.rotation && c.rotation !== "unknown" ? el("p", { class: "rank-sub" }, rotationText(c.rotation)) : null),
      el("div", { class: "rank-price" },
        el("strong", {}, net != null ? rupees(net) : gross != null ? rupees(gross) : "—"),
        el("span", {}, net != null ? t("planner_net") : t("planner_gross"))),
    ),
    el("div", { class: "metrics", style: "margin-top:12px" },
      planMetric(t("planner_yield"), `${pnum(c.historical_yield_t_per_ha_median)} ${t("unit_tha")}`),
      planMetric(t("planner_recent_area"), `${pnum(c.latest_area_ha, 0)} ${t("unit_ha")}`),
      planMetric(t("planner_years"), `${c.yield_observations || 0}`),
    ),
    el("details", { class: "method", style: "margin-top:12px" },
      el("summary", {}, t("planner_details")),
      kv(t("planner_yield_range"), `${(c.historical_yield_t_per_ha_range || []).map(v => pnum(v)).join(" – ") || "—"} ${t("unit_tha")}`),
      kv(t("planner_years"), `${(c.yield_years || []).join(", ") || "—"}`),
      kv(t("planner_price"), c.latest_mandi_price_rs_per_qtl == null ? "—" : `${rupees(c.latest_mandi_price_rs_per_qtl)} ${t("pr_per_quintal")}`),
      kv(t("planner_price_date"), `${c.mandi_price_date ? formatDate(c.mandi_price_date) : "—"}${priceAgeText(c.mandi_price_age_days)}`),
      kv(t("planner_history_price"), c.historical_price_median_rs_per_qtl == null ? t("planner_history_missing") : `${rupees(c.historical_price_median_rs_per_qtl)} ${t("pr_per_quintal")}`),
      harvestWin && harvestWin.median != null ? kv(t("planner_harvest_price"), `${rupees(harvestWin.median)} ${t("pr_per_quintal")} · ${tf("planner_obs", { n: harvestWin.observations })}`) : null,
      kv(t("planner_history_period"), `${c.historical_price_first_date ? formatDate(c.historical_price_first_date) : "—"} – ${c.historical_price_last_date ? formatDate(c.historical_price_last_date) : "—"} · ${tf("planner_obs", { n: pnum(c.historical_price_observations || 0, 0) })}`),
      c.historical_price_trend_pct == null ? null : kv(t("planner_history_trend"), `${pnum(c.historical_price_trend_pct, 1)}%`),
      el("div", { class: "metrics", style: "margin-top:12px" },
        planMetric(t("planner_gross"), gross == null ? "—" : rupees(gross)),
        planMetric(t("planner_net"), net == null ? "—" : rupees(net)),
        planMetric(t("planner_net_area"), c.estimated_net_return_for_area_rs == null ? "—" : rupees(c.estimated_net_return_for_area_rs)),
      ),
      el("p", { class: "panel-sub", style: "margin-top:10px" }, t(c.calculation_code === "net_from_history" ? "planner_calc_net" : "planner_calc_none")),
      (c.data_gap_codes || []).length ? el("div", {}, el("p", { class: "slip-label" }, t("planner_data_gaps")), gapList(c.data_gap_codes)) : null,
    ),
    el("div", { class: "field", style: "margin-top:12px" },
      el("label", { class: "label", for: costId }, t("planner_cost")),
      el("div", { class: "input-unit" }, el("input", { class: "input num", id: costId, type: "number", min: "0", max: "10000000", step: "any", "data-crop-cost": c.crop, value: c.user_entered_cost_rs_per_ha == null ? "" : String(c.user_entered_cost_rs_per_ha), placeholder: "45000" }), el("span", { class: "unit" }, t("unit_rs_ha"))),
      el("p", { class: "panel-sub" }, t("planner_cost_prompt")),
    ),
  );
}

function renderPlan(data) {
  if (!data) { renderEmpty(); return; }
  const cards = [];
  const place = `${districtName(data.state, data.district)}, ${stateName(data.state)}`;
  if (data.status === "data_missing" || data.status === "season_data_missing") {
    cards.push(el("section", { class: "panel" }, emptyState("sprout", t("planner_no_candidates"), (data.data_gap_codes || []).map(gapText).join(" "))));
    planResults.replaceChildren(...cards);
    return;
  }
  // 1. One-line answer first.
  const ranked = Boolean(data.ranked);
  const top = (data.candidates || [])[0];
  cards.push(el("section", { class: "panel plan-summary" },
    el("p", { class: "water-kicker" }, icon("sprout", "sm"), t("planner_summary_title")),
    el("h2", { class: "panel-title" }, place),
    el("p", { class: "panel-sub" }, ranked && top
      ? tf("planner_summary_ranked", { crop: cropLabel(top.crop), net: rupees(top.estimated_net_return_rs_per_ha) })
      : tf("planner_summary_list", { n: data.candidate_count || 0, season: seasonLabel(data.target_season) })),
    data.crop_data_age_years != null && data.crop_data_age_years > 5
      ? el("div", { class: "notice warn" }, icon("alert", "sm"), el("span", {}, tf("planner_data_age", { year: `${data.crop_data_latest_year}-${String(data.crop_data_latest_year + 1).slice(-2)}`, age: data.crop_data_age_years })))
      : null,
  ));
  // 2. The farmer's own season.
  if (data.current_crop_assessment) {
    const d = data.current_crop_assessment;
    const econ = d.actual_season_economics || {};
    cards.push(el("section", { class: "panel" },
      el("h2", { class: "panel-title" }, t("planner_current_result")),
      el("p", { class: "panel-sub" }, `${cropLabel(data.current_crop)} · ${place}`),
      el("div", { class: "summary-chips" },
        el("span", { class: "tag" }, `${t("planner_yield")}: ${pnum(d.local_median_yield_t_per_ha)} ${t("unit_tha")}`),
        el("span", { class: "tag" }, `${t("planner_years")}: ${(d.benchmark_years || []).join(", ") || "—"}`),
        el("span", { class: "tag" }, `${t("planner_gap")}: ${d.yield_gap_pct_vs_local_median == null ? "—" : `${pnum(d.yield_gap_pct_vs_local_median, 1)}%`}`),
      ),
      el("p", { class: "panel-sub", style: "margin-top:12px" }, t(`planner_interp_${d.interpretation || "insufficient_yield_data"}`)),
      el("div", { class: "metrics", style: "margin-top:12px" },
        planMetric(t("planner_gross"), econ.gross_revenue_rs_per_ha == null ? "—" : rupees(econ.gross_revenue_rs_per_ha)),
        planMetric(t("planner_net"), econ.net_return_rs_per_ha == null ? "—" : rupees(econ.net_return_rs_per_ha)),
        planMetric(t("planner_break_even"), econ.break_even_price_rs_per_qtl == null ? "—" : `${rupees(econ.break_even_price_rs_per_qtl)} ${t("pr_per_quintal")}`),
      ),
    ));
  }
  if (data.productivity_actions) {
    const tips = data.productivity_actions[getLang()] || data.productivity_actions.en || [];
    cards.push(el("section", { class: "panel" }, el("h2", { class: "panel-title" }, t("planner_issue")), el("ul", { class: "advice" }, tips.map(x => el("li", {}, x)))));
  }
  // 3. Crops: ranked only when net returns exist for at least two crops.
  cards.push(el("section", { class: "panel" },
    el("h2", { class: "panel-title" }, ranked ? t("planner_candidates_ranked") : t("planner_candidates_list")),
    el("p", { class: "panel-sub" }, t(ranked ? "planner_rank_net" : "planner_rank_area")),
    el("p", { class: "notice warn" }, icon("info", "sm"), el("span", {}, t("planner_disclaimer"))),
  ));
  if (!data.candidates || !data.candidates.length) {
    cards.push(el("section", { class: "panel" }, emptyState("sprout", t("planner_no_candidates"), t("planner_dataset_missing"))));
  } else {
    data.candidates.forEach((c, idx) => cards.push(candidateCard(c, idx, ranked)));
    cards.push(el("section", { class: "panel" },
      el("button", { class: "btn btn-primary btn-block", type: "button", id: "compareCandidateCosts" }, t("planner_compare_costs")),
      el("p", { class: "panel-sub", style: "margin-top:10px" }, t("planner_data_quality")),
    ));
  }
  if (data.data_gap_codes && data.data_gap_codes.length) {
    cards.push(el("details", { class: "panel" }, el("summary", {}, t("planner_data_gaps")), gapList(data.data_gap_codes)));
  }
  if (data.excluded_candidates && data.excluded_candidates.length) {
    cards.push(el("details", { class: "panel" }, el("summary", {}, tf("planner_excluded", { n: data.excluded_candidates.length })),
      el("ul", { class: "advice" }, data.excluded_candidates.map(c => el("li", {}, `${cropLabel(c.crop)}: ${t(`excluded_${String(c.reason_code || "water_constraint").replace(/^excluded_/, "")}`)}`)))));
  }
  cards.push(el("section", { class: "panel" }, el("p", { class: "notice warn" }, icon("info", "sm"), el("span", {}, t("planner_expert")))));
  planResults.replaceChildren(...cards);
  const costButton = document.getElementById("compareCandidateCosts");
  if (costButton) costButton.addEventListener("click", () => {
    lastCostInputs = {};
    planResults.querySelectorAll("[data-crop-cost]").forEach(input => {
      if (input.value.trim() !== "") lastCostInputs[input.dataset.cropCost] = Number(input.value);
    });
    submitPlan(lastCostInputs);
  });
}

async function submitPlan(costs = {}) {
  if (!planForm.reportValidity()) return;
  planStatus.replaceChildren();
  showLoading(planResults);
  const submitButton = planForm.querySelector('button[type="submit"]');
  if (submitButton) submitButton.disabled = true;
  try {
    lastPlan = await apiSend("POST", "/api/planning/recommendations", await buildPayload(costs));
    renderPlan(lastPlan);
    if (window.matchMedia("(max-width: 899px)").matches) planResults.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (err) {
    lastPlan = null;
    renderEmpty();
    showNotice(planStatus, "error", err.message);
  } finally {
    if (submitButton) submitButton.disabled = false;
  }
}
planForm.addEventListener("submit", (event) => { event.preventDefault(); lastCostInputs = {}; submitPlan({}); });
saveRecordButton.addEventListener("click", async () => {
  if (!planForm.reportValidity()) return;
  const y = optionalNumber(val("actual_yield_t_per_ha"));
  const harvest = optionalNumber(val("harvested_tonnes"));
  if (y === null && harvest === null) {
    showNotice(planStatus, "error", `${t("err_validation")} ${t("planner_actual_yield")} / ${t("planner_harvest")}`);
    document.getElementById("actualYield").focus();
    return;
  }
  saveRecordButton.disabled = true;
  try {
    const body = {
      farm_ref: await farmReference(), state: val("state"), district: val("district"), crop: val("current_crop"),
      season: val("current_season") || "Unknown", year_start: Number(val("year_start")), area_ha: Number(val("area_ha")),
      primary_issue: val("primary_issue") || "unknown", notes: val("notes") || null,
      sale_price_rs_per_qtl: optionalNumber(val("actual_sale_price_rs_per_qtl")),
      cultivation_cost_rs_per_ha: optionalNumber(val("current_cost_rs_per_ha")),
      ...readCostParts(),
    };
    if (y !== null) body.yield_t_per_ha = y;
    if (harvest !== null) body.harvested_tonnes = harvest;
    await apiSend("POST", "/api/planning/records", body);
    showNotice(planStatus, "ok", t("planner_saved"));
    if (lastPlan) await submitPlan(lastCostInputs);
  } catch (err) {
    showNotice(planStatus, "error", err.message);
  } finally { saveRecordButton.disabled = false; }
});

const yearInput = document.getElementById("year");
yearInput.max = String(new Date().getFullYear() + 1);
if (Number(yearInput.value) > Number(yearInput.max)) yearInput.value = String(new Date().getFullYear());
planForm.querySelectorAll(".cost-part").forEach(input => input.addEventListener("input", syncTotalCostFromParts));
document.addEventListener("langchange", () => {
  if (plannerStates.length) fillPlaceSelect(stateSelect, plannerStates, stateName, "crop_choose_state", stateSelect.value);
  if (plannerDistricts.length) fillPlaceSelect(districtSelect, plannerDistricts, d => districtName(stateSelect.value, d), "crop_choose_district", districtSelect.value);
  if (lastPlan) renderPlan(lastPlan); else renderEmpty();
});
showFarmKey(storedFarmKey());
renderEmpty();
loadPlannerStates();
