/* Live weather + seven-day crop-water plan. Weather is from Open-Meteo at request time;
   the plan is a simplified FAO-56 root-zone water balance, not a soil-sensor reading. */
const irrigationForm = document.getElementById("irrigationForm");
const statusBox = document.getElementById("status");
const resultsBox = document.getElementById("results");
const irrStateSelect = document.getElementById("state");
const STAGE_KEYS = { initial: "irr_initial", development: "irr_development", mid_season: "irr_mid", late_season: "irr_late" };
let lastEstimate = null;

function num(value, digits = 1) {
  if (value === null || value === undefined || !Number.isFinite(Number(value))) return "—";
  return Number(value).toLocaleString("en-IN", { maximumFractionDigits: digits });
}
function cropName(value) { return cropLabel(value.charAt(0).toUpperCase() + value.slice(1)); }
function metric(label, value, unit) {
  return el("div", { class: "metric" }, el("p", { class: "metric-label" }, label),
    el("p", { class: "metric-value num" }, value, unit ? el("small", {}, unit) : null));
}
function renderEmpty() {
  resultsBox.replaceChildren(el("div", { class: "placeholder" }, emptyState("drop", t("irr_empty_title"), t("irr_empty_body"))));
}
function localizedCondition(condition) {
  return condition && condition.label ? (condition.label[getLang()] || condition.label.en || "—") : "—";
}
function fillStates(selected) {
  const options = STATE_CHOICES.map(v => ({ v, label: stateName(v) })).sort((a, b) => a.label.localeCompare(b.label, getLang() === "hi" ? "hi" : "en"));
  irrStateSelect.replaceChildren(el("option", { value: "" }, t("crop_choose_state")),
    ...options.map(({ v, label }) => el("option", { value: v, selected: v === selected }, label)));
}
function placeLabel(location) {
  if (!location) return "";
  const state = location.state || irrStateSelect.value;
  return [location.name ? marketName(location.name, state) : null, state ? stateName(state) : null].filter(Boolean).join(", ");
}
function dateTimeLabel(iso) {
  if (!iso) return "—";
  const when = new Date(iso);
  return Number.isNaN(when.getTime()) ? iso
    : when.toLocaleString(getLang() === "hi" ? "hi-IN" : "en-IN", { dateStyle: "medium", timeStyle: "short", hourCycle: "h23" });
}
function showNoticeEl(kind, message) {
  const holder = el("div");
  showNotice(holder, kind, message);
  holder.firstChild.style.marginTop = "0";
  return holder.firstChild;
}

function renderEstimate(data) {
  if (!data) { renderEmpty(); return; }
  const totals = data.totals || {};
  const zone = data.root_zone || {};
  const events = data.irrigation_events || [];
  const mm = t("unit_mm");
  const rice = data.crop === "rice";
  const current = data.current_weather || {};
  const litres = totals.estimated_gross_water_litres;
  const noWater = !rice && litres === 0;

  const water = el("section", { class: "water", "aria-labelledby": "waterPlace" },
    el("div", { class: "water-top" },
      el("p", { class: "water-kicker" }, icon("drop", "sm"), t("irr_estimate_title")),
      el("h2", { class: "water-place", id: "waterPlace" }, placeLabel(data.location)),
      el("div", { class: "water-figure" },
        el("span", { class: "water-litres num" }, litres == null ? "—" : num(litres, 0)),
        el("span", { class: "water-unit" }, litres == null ? "" : t("irr_litres")),
      ),
      el("p", { class: "water-label" }, rice ? t("irr_rice_caveat") : `${t("irr_total_label")} (${num(totals.estimated_gross_irrigation_mm, 1)} ${mm})`),
      el("p", { class: "water-basis" }, tf("irr_basis", {
        area: num(data.area_ha, 3), crop: cropName(data.crop), stage: t(STAGE_KEYS[data.stage] || "irr_stage"),
        eff: Math.round(data.irrigation_efficiency * 100), kc: data.kc,
      })),
    ),
    el("div", { class: "metrics" },
      metric(t("irr_crop_use"), num(totals.estimated_crop_water_use_mm, 1), mm),
      metric(t("irr_rain"), num(totals.forecast_rain_mm, 1), mm),
      metric(t("irr_expected_rain"), num(totals.expected_rain_mm, 1), mm),
    ),
    el("div", { class: "water-advice" },
      showNoticeEl(noWater ? "ok" : "info", t(noWater ? "irr_advice_none" : "irr_advice_split")),
    ),
  );

  const schedule = rice ? null : el("section", { class: "panel", "aria-labelledby": "scheduleTitle" },
    el("h3", { class: "panel-title", id: "scheduleTitle" }, t("irr_schedule_title")),
    events.length
      ? el("ol", { class: "schedule" }, events.map(e => el("li", {},
          el("span", { class: "schedule-date" }, formatDate(e.date, false)),
          el("strong", { class: "num" }, `${num(e.litres, 0)} ${t("irr_litres")}`),
          el("span", { class: "panel-sub" }, `${num(e.gross_mm, 1)} ${mm}`))))
      : el("p", { class: "panel-sub" }, t("irr_schedule_none")),
    el("details", { class: "method", style: "margin-top:12px" },
      el("summary", {}, t("irr_root_title")),
      el("div", { class: "day-rows" },
        el("div", {}, el("span", {}, t("irr_root_depth")), el("span", { class: "num" }, `${num(zone.root_depth_m, 2)} ${t("unit_m")}`)),
        el("div", {}, el("span", {}, t("irr_taw")), el("span", { class: "num" }, `${num(zone.total_available_water_mm, 0)} ${mm}`)),
        el("div", {}, el("span", {}, t("irr_raw")), el("span", { class: "num" }, `${num(zone.readily_available_water_mm, 0)} ${mm}`)),
        el("div", {}, el("span", {}, t("irr_start")), el("span", { class: "num" }, `${num(zone.starting_depletion_mm, 0)} ${mm} · ${t(`irr_moisture_${zone.starting_assumption || "unknown"}`)}`)),
      ),
      el("p", { class: "panel-sub" }, t("irr_root_explain")),
    ),
  );

  const currentPanel = el("section", { class: "panel", "aria-labelledby": "currentWeatherTitle" },
    el("h3", { class: "panel-title", id: "currentWeatherTitle" }, t("irr_current_weather")),
    el("p", { class: "panel-sub" }, `${localizedCondition(current.condition)}${current.time ? ` · ${dateTimeLabel(current.time)}` : ""}`),
    el("div", { class: "metrics", style: "margin-top:12px" },
      metric(t("irr_daily_temp"), num(current.temperature_c, 1), "°C"),
      metric(t("irr_feels_like"), num(current.feels_like_c, 1), "°C"),
      metric(t("irr_humidity"), num(current.relative_humidity_pct, 0), "%"),
    ),
    el("div", { class: "metrics" },
      metric(t("irr_wind"), num(current.wind_speed_kmh, 1), t("unit_kmh")),
      metric(t("irr_rain_short"), num(current.rain_mm, 1), mm),
      metric(t("irr_cloud"), num(current.cloud_cover_pct, 0), "%"),
    ),
  );

  const alerts = (data.alerts || []).map(alert => el("div", { class: `notice ${alert.severity === "info" ? "info" : "warn"}` }, icon(alert.severity === "info" ? "info" : "alert", "sm"),
    el("span", {}, `${formatDate(alert.date, false)}: ${(alert.message && (alert.message[getLang()] || alert.message.en)) || t("irr_alerts")}`)));
  const alertsPanel = alerts.length ? el("section", { class: "panel" }, el("h3", { class: "panel-title" }, t("irr_alerts")), ...alerts) : null;

  const days = el("section", { class: "panel", "aria-labelledby": "daysTitle" },
    el("h3", { class: "panel-title", id: "daysTitle", style: "margin-bottom:12px" }, t("irr_daily_forecast")),
    el("div", { class: "days" }, (data.forecast_days || []).map(day => el("article", { class: "day" },
      el("div", { class: "day-head" }, el("span", {}, formatDate(day.date, false)), icon((day.rain_mm || 0) >= 1 ? "cloud" : "sun")),
      el("p", { class: "day-rain num" }, num(day.rain_mm, 1), el("small", {}, `${mm} ${t("irr_rain_short")}`)),
      el("p", { class: "day-chance" }, day.rain_probability_pct == null ? "—" : `${num(day.rain_probability_pct, 0)}% ${t("irr_rain_chance")}`),
      el("div", { class: "day-rows" },
        el("div", {}, el("span", {}, t("irr_daily_temp")), el("span", { class: "num" }, `${num(day.temperature_min_c, 0)}° / ${num(day.temperature_max_c, 0)}°C`)),
        el("div", {}, el("span", {}, t("irr_et0_short")), el("span", { class: "num" }, `${num(day.et0_mm, 1)} ${mm}`)),
        el("div", {}, el("span", {}, t("irr_use_short")), el("span", { class: "num" }, `${num(day.crop_et_mm, 1)} ${mm}`)),
        el("div", {}, el("span", {}, t("irr_wind")), el("span", { class: "num" }, `${num(day.wind_max_kmh, 0)} ${t("unit_kmh")}`)),
      ),
    ))),
    el("details", { class: "method", style: "margin-top:16px" },
      el("summary", {}, t("irr_method")),
      el("p", {}, t("irr_method_detail")),
      el("p", {}, `${t("irr_weather_source")}: Open-Meteo. ${t("irr_coefficient_source")}: FAO-56.`),
      el("p", { class: "panel-sub" }, `${t("irr_weather_retrieved")}: ${dateTimeLabel(data.weather_retrieved_at)}`),
      data.location ? el("p", { class: "panel-sub" }, `${t("irr_coordinates")}: ${data.location.latitude}, ${data.location.longitude}`) : null,
    ),
  );
  const adviceLines = (data.advice && (data.advice[getLang()] || data.advice.en)) || [];
  const advicePanel = el("section", { class: "panel" }, el("h3", { class: "panel-title" }, t("irr_advice_title")),
    el("ul", { class: "advice" }, adviceLines.map(line => el("li", {}, line))),
    el("p", { class: "panel-sub" }, t("irr_disclaimer")));
  resultsBox.replaceChildren(...[water, schedule, alertsPanel, currentPanel, days, advicePanel].filter(Boolean));
}

irrigationForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const f = irrigationForm.elements;
  const body = {
    location: f.location.value.trim(), state: f.state.value, crop: f.crop.value,
    stage: f.stage.value, area_ha: Number(f.area_ha.value), efficiency: Number(f.efficiency.value),
    soil_texture: f.soil_texture.value, field_moisture: f.field_moisture.value,
  };
  if (body.location.length < 2 || !body.state) {
    showNotice(statusBox, "error", `${t("err_validation")} ${t("irr_location")} / ${t("f_state")}`); f.location.focus(); return;
  }
  if (!(body.area_ha > 0)) { showNotice(statusBox, "error", `${t("err_validation")} ${t("irr_area")}`); f.area_ha.focus(); return; }
  storageSet("irrState", body.state);
  const button = irrigationForm.querySelector("button[type=submit]");
  button.disabled = true; statusBox.replaceChildren(); showLoading(resultsBox);
  try {
    lastEstimate = await apiSend("POST", "/api/irrigation/estimate", body);
    renderEstimate(lastEstimate);
    if (window.matchMedia("(max-width: 899px)").matches) resultsBox.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (err) {
    lastEstimate = null; renderEmpty(); showNotice(statusBox, "error", err.message);
  } finally { button.disabled = false; }
});
document.addEventListener("langchange", () => { fillStates(irrStateSelect.value || storageGet("irrState")); renderEstimate(lastEstimate); });
fillStates(storageGet("irrState") || "Punjab");
renderEmpty();
