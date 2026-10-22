/* Mandi Prices page. Owner: Member D (backend endpoints by Member C) */

const stateSelect = document.getElementById("state");
const cropSelect = document.getElementById("commodity");
const dataNotice = document.getElementById("dataNotice");
const statusBox = document.getElementById("status");
const resultsBox = document.getElementById("results");
const comparePanel = document.getElementById("comparePanel");
const traderPrice = document.getElementById("traderPrice");
const traderQty = document.getElementById("traderQty");
const compareOut = document.getElementById("compareOut");
const compareBasis = document.getElementById("compareBasis");
const costTransport = document.getElementById("costTransport");
const costCommission = document.getElementById("costCommission");
const costOther = document.getElementById("costOther");
const SVG_NS = "http://www.w3.org/2000/svg";

let states = [];
let crops = [];
let lastBest = null;
let lastHistory = [];
let dataStatus = null;
let tooltip = null;

function fillSelect(select, values, selected, labelFn = v => v) {
  const options = values.map(v => ({ v, label: labelFn(v) }))
    .sort((a, b) => a.label.localeCompare(b.label, getLang() === "hi" ? "hi" : "en"));
  select.replaceChildren(
    el("option", { value: "" }, t("pr_choose")),
    ...options.map(({ v, label }) => el("option", { value: v, selected: v === selected }, label)),
  );
}

function placeLine(m) {
  const state = stateSelect.value;
  return [m.district ? districtName(state, m.district) : null, m.variety ? varietyLabel(m.variety) : null].filter(Boolean).join(", ");
}

/* Same order of checks as the backend's /api/prices/status: the most serious problem wins. */
function renderNotice() {
  if (!dataStatus) return;
  const sync = dataStatus.last_sync || {};
  const sources = dataStatus.sources || [];
  if (!dataStatus.rows) showNotice(dataNotice, "warn", t("pr_nodata"));
  else if (sources.includes("sample")) showNotice(dataNotice, "warn", t("pr_sample"));
  else if (["error", "no_data"].includes(sync.status)) showNotice(dataNotice, "warn", t("pr_sync_fail"));
  else if (sync.status === "partial") showNotice(dataNotice, "warn", t("pr_sync_partial"));
  else if (dataStatus.is_stale) showNotice(dataNotice, "warn", tf("pr_stale", { date: formatDate(dataStatus.latest_date) }));
  else if (!(dataStatus.has_live_source ?? dataStatus.has_government_source)) showNotice(dataNotice, "warn", t("pr_custom_source"));
  else if (dataStatus.auto_refresh && dataStatus.auto_refresh.enabled) {
    const time = sync.last_attempt_at
      ? new Date(sync.last_attempt_at).toLocaleString(getLang() === "hi" ? "hi-IN" : "en-IN", { dateStyle: "medium", timeStyle: "short", hourCycle: "h23" })
      : t("pr_not_run");
    showNotice(dataNotice, "info", tf("pr_auto_refresh_on", { hours: dataStatus.auto_refresh.interval_hours, time }));
  } else showNotice(dataNotice, "warn", t("pr_auto_refresh_off"));
}

function daysSince(isoDate) {
  if (!isoDate) return null;
  const [y, m, d] = String(isoDate).slice(0, 10).split("-").map(Number);
  const today = new Date();
  return Math.round((new Date(today.getFullYear(), today.getMonth(), today.getDate()) - new Date(y, m - 1, d)) / 864e5);
}

/* ---------------------------------------------------------------- Trend: a line over recent days */
function svg(tag, attrs = {}, text) {
  const node = document.createElementNS(SVG_NS, tag);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
  if (text !== undefined) node.textContent = text;
  return node;
}

function showTip(event, text) {
  if (!tooltip) { tooltip = el("div", { class: "tooltip", role: "presentation" }); document.body.append(tooltip); }
  const box = event.currentTarget.getBoundingClientRect();
  tooltip.textContent = text;
  tooltip.style.left = `${box.left + box.width / 2}px`;
  tooltip.style.top = `${box.top + 8}px`;
  tooltip.hidden = false;
}
function hideTip() { if (tooltip) tooltip.hidden = true; }

function trendChart(history, width) {
  // Drawn at the real on-screen width, so text stays readable on phones.
  const W = Math.max(260, Math.round(width)), H = 190, padL = 14, padR = 78, padT = 24, padB = 34;
  const values = history.map(h => h.avg_modal_price);
  const min = Math.min(...values), max = Math.max(...values);
  const pad = Math.max((max - min) * 0.3, max * 0.01, 1);
  const lo = min - pad, hi = max + pad;
  const x = i => padL + (history.length === 1 ? 0 : i * (W - padL - padR) / (history.length - 1));
  const y = v => padT + (hi - v) / (hi - lo) * (H - padT - padB);

  const chart = svg("svg", { viewBox: `0 0 ${W} ${H}`, role: "img",
    "aria-label": history.map(h => `${formatDate(h.date, false)}: ${rupees(h.avg_modal_price)}`).join(", ") });
  chart.append(svg("line", { class: "baseline", x1: padL, x2: W - padR + 10, y1: H - padB, y2: H - padB }));
  chart.append(svg("path", {
    d: history.map((h, i) => `${i ? "L" : "M"}${x(i).toFixed(1)} ${y(h.avg_modal_price).toFixed(1)}`).join(" "),
    class: "trend-line",
  }));
  history.forEach((h, i) => {
    const last = i === history.length - 1;
    const cx = x(i), cy = y(h.avg_modal_price);
    chart.append(svg("circle", { cx, cy, r: last ? 6 : 4.5, class: last ? "trend-dot latest" : "trend-dot" }));
    chart.append(svg("text", { class: "axis-label", x: cx, y: H - 10, "text-anchor": i === 0 ? "start" : last ? "end" : "middle" }, formatDate(h.date, false)));
    const hit = svg("rect", { class: "hit", x: cx - 22, y: padT - 10, width: 44, height: H - padT - padB + 20, tabindex: 0 });
    const label = `${formatDate(h.date, false)}: ${rupees(h.avg_modal_price)} ${t("pr_per_quintal")}`;
    hit.addEventListener("mouseenter", e => showTip(e, label));
    hit.addEventListener("focus", e => showTip(e, label));
    hit.addEventListener("mouseleave", hideTip);
    hit.addEventListener("blur", hideTip);
    chart.append(hit);
  });
  const lastIndex = history.length - 1;
  chart.append(svg("text", { class: "value-label", x: x(lastIndex) + 12, y: y(values[lastIndex]) + 4 }, rupees(values[lastIndex])));
  return chart;
}

function trendCaption(history) {
  const first = history[0], last = history[history.length - 1];
  const diff = Math.round(last.avg_modal_price - first.avg_modal_price);
  const date = formatDate(first.date, false);
  if (diff > 0) return tf("pr_trend_up", { diff: rupees(diff), date });
  if (diff < 0) return tf("pr_trend_down", { diff: rupees(-diff), date });
  return tf("pr_trend_same", { date });
}

/* ---------------------------------------------------------------- Results */
function renderResults() {
  hideTip();
  if (!lastBest) {
    comparePanel.hidden = true;
    resultsBox.replaceChildren(el("div", { class: "placeholder" }, emptyState("rupee", t("pr_pick"))));
    return;
  }
  if (!lastBest.markets.length) {
    comparePanel.hidden = true;
    resultsBox.replaceChildren(el("div", { class: "placeholder" }, emptyState("rupee", t("pr_nodata"))));
    return;
  }

  const [top, ...others] = lastBest.markets;
  const best = el("section", { class: "best", "aria-labelledby": "bestMarket" },
    el("div", { class: "best-top" },
      el("p", { class: "best-kicker" }, icon("star", "sm"), t("pr_best_title")),
      el("h2", { class: "best-market", id: "bestMarket" }, marketName(top.market, stateSelect.value)),
      el("p", { class: "best-place" }, placeLine(top)),
      el("div", { class: "best-figures" },
        el("div", {}, el("p", { class: "best-price num" }, rupees(top.modal_price)), el("p", { class: "best-unit" }, t("pr_per_quintal"))),
        el("div", {}, el("p", { class: "best-kg num" }, rupees(top.modal_per_kg, 2)), el("p", { class: "best-unit" }, t("pr_per_kg"))),
      ),
      el("p", { class: "best-range num" }, tf("pr_range", { min: rupees(top.min_price), max: rupees(top.max_price) })),
      el("p", { class: "meta-line" }, el("span", {}, tf("pr_date", { date: formatDate(lastBest.date) })),
        daysSince(lastBest.date) > ((dataStatus && dataStatus.stale_after_days) || 3) ? el("span", { class: "tag old" }, tf("pr_old", { n: daysSince(lastBest.date) })) : null),
    ),
  );

  const parts = [best];
  if (others.length) {
    const maxPrice = top.modal_price;
    parts.push(el("section", { class: "panel", "aria-labelledby": "othersTitle" },
      el("h3", { class: "panel-title", id: "othersTitle", style: "margin-bottom:10px" }, t("pr_others")),
      el("ol", { class: "ranks" }, others.map((m, i) => el("li", { class: "rank" },
        el("span", { class: "rank-no num", "aria-hidden": "true" }, String(i + 2)),
        el("div", {},
          el("p", { class: "rank-name" }, marketName(m.market, stateSelect.value)),
          el("p", { class: "rank-sub" }, placeLine(m)),
        ),
        el("div", { class: "rank-price" },
          el("strong", { class: "num" }, rupees(m.modal_price)),
          el("span", { class: "num" }, `${rupees(m.modal_per_kg, 2)} ${t("pr_per_kg")}`),
        ),
        el("div", { class: "rank-bar", "aria-hidden": "true" }, el("span", { style: `width:${Math.round(m.modal_price / maxPrice * 100)}%` })),
      ))),
    ));
  }

  if (lastHistory.length > 1) {
    parts.push(el("section", { class: "panel", "aria-labelledby": "trendTitle" },
      el("h3", { class: "panel-title", id: "trendTitle" }, tf("pr_trend", { state: stateName(stateSelect.value) })),
      el("p", { class: "panel-sub", style: "margin-bottom:12px" }, t("pr_per_quintal")),
      el("figure", { class: "trend-figure" }, trendChart(lastHistory, resultsBox.clientWidth - 42), el("figcaption", {}, trendCaption(lastHistory))),
    ));
  }
  resultsBox.replaceChildren(...parts);
  compareBasis.textContent = `${t("pr_trader_hint")} ${tf("pr_compare_basis", { date: formatDate(lastBest.date) })}`;
  comparePanel.hidden = false;
  renderCompare();
}

/* ---------------------------------------------------------------- Trader offer comparison
   The highest mandi quote is not the farmer's real gain: transport, commission and loading come
   out of it. Every rupee of the comparison is shown so the farmer can check it. */
function moneyRow(label, value, kind = "") {
  return el("div", { class: `calc-row ${kind}`.trim() }, el("span", {}, label), el("strong", { class: "num" }, value));
}

function renderCompare() {
  if (!lastBest || !lastBest.markets.length) return;
  const offer = numberOrNull(traderPrice.value);
  const qty = numberOrNull(traderQty.value);
  if (offer === null || offer <= 0) {
    compareOut.replaceChildren(...(qty && qty > 0 ? [el("p", { class: "panel-sub" }, t("pr_enter_offer"))] : []));
    return;
  }
  const top = lastBest.markets[0];
  const bestKg = top.modal_per_kg;
  if (!qty || qty <= 0) {
    const diffKg = Math.round((bestKg - offer) * 100) / 100;
    showNotice(compareOut, diffKg > 0 ? "warn" : "ok", diffKg > 0 ? `${tf("pr_more", { diff: rupees(diffKg, 2) })} ${t("pr_enter_qty")}` : t("pr_fair"));
    return;
  }
  const transport = Math.max(0, numberOrNull(costTransport.value) || 0);
  const commissionPct = Math.min(20, Math.max(0, numberOrNull(costCommission.value) || 0));
  const other = Math.max(0, numberOrNull(costOther.value) || 0);
  const traderTotal = offer * qty;
  const mandiGross = bestKg * qty;
  const commission = mandiGross * commissionPct / 100;
  const costs = transport + commission + other;
  const mandiNet = mandiGross - costs;
  const diff = Math.round(mandiNet - traderTotal);
  const quantity = qty.toLocaleString("en-IN");
  const market = marketName(top.market, stateSelect.value);
  const rows = [
    el("p", { class: "calc-title" }, tf("pr_calc_for", { qty: quantity })),
    moneyRow(tf("pr_calc_trader", { price: rupees(offer, 2) }), rupees(traderTotal)),
    moneyRow(tf("pr_calc_mandi_gross", { market, price: rupees(bestKg, 2) }), rupees(mandiGross)),
    transport ? moneyRow(t("pr_cost_transport"), `− ${rupees(transport)}`, "minus") : null,
    commission ? moneyRow(tf("pr_calc_commission", { pct: commissionPct }), `− ${rupees(commission)}`, "minus") : null,
    other ? moneyRow(t("pr_cost_other"), `− ${rupees(other)}`, "minus") : null,
    moneyRow(t("pr_calc_mandi_net"), rupees(mandiNet), "total"),
    moneyRow(t("pr_calc_mandi_net_kg"), `${rupees(mandiNet / qty, 2)} ${t("pr_per_kg")}`),
  ];
  let verdict;
  if (Math.abs(diff) < Math.max(50, traderTotal * 0.005)) verdict = el("div", { class: "notice info" }, icon("info", "sm"), el("span", {}, t("pr_calc_same")));
  else if (diff > 0) verdict = el("div", { class: "notice warn" }, icon("alert", "sm"), el("span", {}, tf("pr_calc_mandi_better", { diff: rupees(diff), market })));
  else verdict = el("div", { class: "notice ok" }, icon("check", "sm"), el("span", {}, tf("pr_calc_trader_better", { diff: rupees(-diff) })));
  const note = costs ? null : el("p", { class: "panel-sub" }, t("pr_calc_add_costs"));
  compareOut.replaceChildren(...[el("div", { class: "calc", role: "group", "aria-label": t("pr_calc_label") }, ...rows.filter(Boolean)), verdict, note].filter(Boolean));
}
[traderPrice, traderQty, costTransport, costCommission, costOther].forEach(input => input.addEventListener("input", renderCompare));

/* ---------------------------------------------------------------- Loading */
async function loadCrops(state) {
  crops = [];
  lastBest = null;
  renderResults();
  cropSelect.disabled = true;
  fillSelect(cropSelect, []);
  if (!state) return;
  try {
    crops = await apiGet("/api/prices/commodities", { state });
    fillSelect(cropSelect, crops, storageGet("priceCrop"), cropLabel);
    cropSelect.disabled = false;
    if (crops.includes(cropSelect.value)) loadBest();
  } catch (err) {
    showNotice(statusBox, "error", err.message);
  }
}

async function loadBest() {
  const state = stateSelect.value;
  const commodity = cropSelect.value;
  if (!state || !commodity) { lastBest = null; renderResults(); return; }
  storageSet("priceCrop", commodity);
  showLoading(resultsBox);
  statusBox.replaceChildren();
  try {
    [lastBest, lastHistory] = await Promise.all([
      apiGet("/api/prices/best", { state, commodity, limit: 5 }),
      apiGet("/api/prices/history", { state, commodity, days: 7 }),
    ]);
    renderResults();
  } catch (err) {
    lastBest = null;
    renderResults();
    showNotice(statusBox, "error", err.message);
  }
}

stateSelect.addEventListener("change", () => {
  storageSet("priceState", stateSelect.value);
  loadCrops(stateSelect.value);
});
cropSelect.addEventListener("change", loadBest);
window.addEventListener("scroll", hideTip, { passive: true });
let resizeTimer = null;
let lastWidth = window.innerWidth;
window.addEventListener("resize", () => {
  if (window.innerWidth === lastWidth) return; // ignore phone address-bar height changes
  lastWidth = window.innerWidth;
  clearTimeout(resizeTimer);
  resizeTimer = setTimeout(() => { if (lastBest) renderResults(); }, 200);
});

document.addEventListener("langchange", () => {
  fillSelect(stateSelect, states, stateSelect.value, stateName);
  fillSelect(cropSelect, crops, cropSelect.value, cropLabel);
  renderNotice();
  renderResults();
});

(async function start() {
  fillSelect(stateSelect, []);
  fillSelect(cropSelect, []);
  showLoading(resultsBox);
  try {
    dataStatus = await apiGet("/api/prices/status");
    renderNotice();
    states = await apiGet("/api/prices/states");
    const saved = storageGet("priceState");
    fillSelect(stateSelect, states, states.includes(saved) ? saved : "", stateName);
    renderResults();
    if (stateSelect.value) loadCrops(stateSelect.value);
  } catch (err) {
    resultsBox.replaceChildren();
    showNotice(statusBox, "error", err.message);
  }
})();
