/* Talking to the backend + small helpers used by every page. Owner: Member D
   Load order on every page: i18n.js, then api.js, then the page's own script (all with "defer"). */

// Production serves the frontend and API from the same FastAPI origin, so use relative
// URLs there. For local previews (e.g. VS Code Live Server on port 5500), call port 8000.
// A double-clicked file uses localhost as a fallback; preferably open the app at :8000.
const LOCAL_PREVIEW_PORTS = new Set(["3000", "5173", "5500", "5501", "8080"]);
const API_BASE =
  location.protocol === "file:" ? "http://localhost:8000"
    : LOCAL_PREVIEW_PORTS.has(location.port) ? `${location.protocol}//${location.hostname}:8000`
      : "";

class ApiError extends Error {
  constructor(message, status) { super(message); this.status = status; }
}

const FIELD_KEYS = {
  farmer_name: "f_name", buyer_name: "f_name", phone: "f_phone", crop: "f_crop",
  quantity_kg: "f_qty", price_per_kg: "f_price", village: "f_village", district: "f_district",
  state: "f_state", offered_price_per_kg: "f_offer", message: "f_message", owner_pin: "mk_pin",
  location: "irr_location", area_ha: "irr_area", efficiency: "irr_efficiency", stage: "irr_stage",
  code: "otp_code", phone_token: "otp_title", farm_ref: "planner_key_title",
  current_crop: "planner_current_crop", current_season: "planner_current_season", target_season: "planner_target_season",
  soil_ph: "planner_ph", soil_type: "planner_soil", water_availability: "planner_water",
  actual_yield_t_per_ha: "planner_actual_yield", actual_sale_price_rs_per_qtl: "planner_sale_price",
  current_cost_rs_per_ha: "planner_current_cost", soil_texture: "irr_soil", field_moisture: "irr_moisture",
};

/* The server answers in English. Every message a farmer can meet is mapped to a text key here,
   so it is shown in Hindi when Hindi is on. Matching is on the start of the message. */
const SERVER_MESSAGES = [
  ["Phone number or farmer PIN is incorrect", "err_wrong_pin"],
  ["Too many wrong PIN attempts", "err_locked"],
  ["Too many attempts", "err_too_many"],
  ["Verify this mobile number", "otp_needed"],
  ["This mobile number already has listings", "err_same_pin"],
  ["Choose a PIN with at least 3 different characters", "err_pin_repeat"],
  ["This PIN is too easy to guess", "err_pin_easy"],
  ["Do not use your mobile number as the PIN", "err_pin_phone"],
  ["This listing is already sold", "err_sold"],
  ["This listing has expired", "err_expired"],
  ["This listing is no longer available", "err_unavailable"],
  ["You have already sent your number", "err_duplicate_interest"],
  ["Listing not found", "err_not_found"],
  ["Phone verification is not enabled", "err_otp_off"],
  ["The code is wrong or has expired", "err_otp_wrong"],
  ["Please upload a photo", "err_photo_type"],
  ["The photo is empty", "err_photo_empty"],
  ["Photo is larger than", "err_too_big"],
  ["The photo is too small", "err_photo_small"],
  ["The photo is too large in pixel", "err_photo_pixels"],
  ["This file is not a safe, readable photo", "err_photo_type"],
  ["Live weather data is temporarily unavailable", "err_weather"],
  ["Weather provider returned an unexpected", "err_weather"],
  ["The weather provider returned no", "err_weather"],
  ["The location did not match the supplied state", "err_place_state"],
  ["Location not found in India", "err_place_missing"],
  ["The location result", "err_place_missing"],
  ["The season year cannot be more than one year", "err_year_future"],
  ["Provide either yield per hectare or harvested tonnes", "err_yield_missing"],
  ["Yield × area does not match", "err_yield_mismatch"],
  ["Total cultivation cost differs", "err_cost_mismatch"],
  ["Candidate crop costs must be", "err_cost_range"],
  ["Provide costs for at most 30", "err_cost_range"],
  ["Crop comparison could not be completed", "err_planner_failed"],
];

function serverText(message) {
  const text = String(message || "").replace(/^Value error,\s*/i, "").trim();
  const hit = SERVER_MESSAGES.find(([start]) => text.startsWith(start));
  return hit ? t(hit[1]) : null;
}

function errorMessage(status, data) {
  const detail = data && data.detail;
  if (status === 422) {
    if (Array.isArray(detail)) {
      const known = detail.map(d => serverText(d.msg)).filter(Boolean);
      if (known.length) return [...new Set(known)].join(" ");
      const fields = [...new Set(detail.map(d => {
        const name = d.loc ? d.loc[d.loc.length - 1] : "";
        return FIELD_KEYS[name] ? t(FIELD_KEYS[name]) : (getLang() === "hi" ? "" : name);
      }))].filter(Boolean);
      return `${t("err_validation")} ${fields.join(", ")}`.trim();
    }
    return (typeof detail === "string" && serverText(detail)) || t("err_bad_request");
  }
  if (typeof detail === "string") {
    const known = serverText(detail);
    if (known) return known;
  }
  const byStatus = { 401: "otp_needed", 403: "err_forbidden", 404: "err_not_found", 409: "err_sold", 413: "err_too_big", 429: "err_too_many", 503: "err_model" };
  // An unmapped 503 detail is a setup step for the person running the server (English only).
  if (status === 503 && typeof detail === "string" && getLang() !== "hi") return detail;
  if (byStatus[status]) return t(byStatus[status]);
  if (status === 400) return t("err_bad_request");
  return t("err_server");
}

async function apiRequest(path, options = {}) {
  let res;
  try {
    res = await fetch(API_BASE + path, options);
  } catch (e) {
    throw new ApiError(t("err_network"), 0);
  }
  let data = null;
  try { data = await res.json(); } catch (e) { /* empty body */ }
  if (!res.ok) throw new ApiError(errorMessage(res.status, data), res.status);
  return data;
}

function apiGet(path, params) {
  const query = params ? "?" + new URLSearchParams(
    Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== "")
  ).toString() : "";
  return apiRequest(path + query);
}

function apiSend(method, path, body) {
  return apiRequest(path, {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

function apiUpload(path, formData) {
  // No Content-Type header here: the browser adds the correct multipart boundary itself.
  return apiRequest(path, { method: "POST", body: formData });
}

/* ---------------------------------------------------------------- Safe DOM building
   Text is always inserted as text, never as HTML, so a farmer typing <script> in their
   name cannot break the page. */
function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs || {})) {
    if (value === undefined || value === null || value === false) continue;
    if (key === "class") node.className = value;
    else if (key === "text") node.textContent = value;
    else if (key.startsWith("on") && typeof value === "function") node.addEventListener(key.slice(2), value);
    else node.setAttribute(key, value === true ? "" : value);
  }
  for (const child of children.flat()) {
    if (child === undefined || child === null || child === false) continue;
    node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return node;
}

/* ---------------------------------------------------------------- Icons (24 x 24 line icons)
   In HTML: <span data-icon="leaf"></span> is replaced by the SVG when the page loads. */
const ICONS = {
  home: ["M3 11l9-7 9 7", "M5 10v10h14V10", "M10 20v-6h4v6"],
  leaf: ["M5 19c0-8.5 5.5-14 15-15-1 9.5-6.5 15-15 15z", "M5 19l7.5-7.5"],
  sprout: ["M12 21v-9", "M12 14C5 14 4 8 4 5c5 0 8 3 8 9", "M12 12c0-5 3-8 8-8 0 5-2 10-8 10"],
  rupee: ["M7 4h10", "M7 9h10", "M7 4c6.5 0 6.5 9.5 0 9.5L15 20"],
  market: ["M3.5 9l2-5h13l2 5", "M4.5 9v11h15V9", "M3.5 9h17", "M9.5 20v-6h5v6"],
  camera: ["M4 8h3.2l1.8-3h6l1.8 3H20v11H4z", "circle:12,13,3.6"],
  phone: ["M5 4h3.5l2 5-2.4 1.5a11 11 0 0 0 5.4 5.4L15 13.5l5 2V19a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2z"],
  check: ["M5 12.5l4.5 4.5L19 7.5"],
  alert: ["M12 3.5l9.5 16.5h-19z", "M12 10v4.5", "M12 17.4v.2"],
  question: ["circle:12,12,9", "M9.6 9.3a2.5 2.5 0 1 1 3.4 2.3c-.7.3-1 .8-1 1.5v.4", "M12 16.6v.2"],
  info: ["circle:12,12,9", "M12 11v5", "M12 7.8v.2"],
  speaker: ["M4 9.5v5h3.5L12 18.5v-13L7.5 9.5z", "M15.5 9.5a3.5 3.5 0 0 1 0 5", "M18 7a7 7 0 0 1 0 10"],
  refresh: ["M4.5 12a7.5 7.5 0 0 1 13-5.1L19.5 9", "M19.5 4.5V9H15", "M19.5 12a7.5 7.5 0 0 1-13 5.1L4.5 15", "M4.5 19.5V15H9"],
  pin: ["M12 21s-6.5-5.8-6.5-10.5a6.5 6.5 0 0 1 13 0C18.5 15.2 12 21 12 21z", "circle:12,10.5,2.3"],
  weight: ["M6.5 8h11l2.5 12H4z", "M9.5 8a2.5 2.5 0 0 1 5 0"],
  user: ["circle:12,8,3.8", "M4.5 20.5a7.5 7.5 0 0 1 15 0"],
  chevron: ["M9.5 6l6 6-6 6"],
  search: ["circle:11,11,6.5", "M20 20l-4.3-4.3"],
  star: ["M12 3.5l2.6 5.4 5.9.8-4.3 4.1 1 5.9L12 16.9l-5.2 2.8 1-5.9-4.3-4.1 5.9-.8z"],
  image: ["M4 5h16v14H4z", "circle:9,10,1.8", "M4 17l5-4.5 3.5 3 3-2.5L20 17"],
  close: ["M6 6l12 12", "M18 6L6 18"],
  calendar: ["M4 6h16v14H4z", "M4 10h16", "M8.5 3.5v4", "M15.5 3.5v4"],
  chart: ["M4 20h16", "M6.5 20v-6", "M11 20V9", "M15.5 20v-8", "M20 20V5"],
  drop: ["M12 3.5s6 6.6 6 11a6 6 0 0 1-12 0c0-4.4 6-11 6-11z", "M9.2 15a2.8 2.8 0 0 0 2.8 2.8"],
  sun: ["circle:12,12,4", "M12 2.5v2", "M12 19.5v2", "M2.5 12h2", "M19.5 12h2", "M5.3 5.3l1.4 1.4", "M17.3 17.3l1.4 1.4", "M5.3 18.7l1.4-1.4", "M17.3 6.7l1.4-1.4"],
  cloud: ["M7 18h10a4 4 0 0 0 .6-8A5.5 5.5 0 0 0 7 9.5 4.3 4.3 0 0 0 7 18z"],
  lock: ["M6 11h12v9H6z", "M8.5 11V8a3.5 3.5 0 0 1 7 0v3"],
  eye: ["M2.5 12s3.5-6.5 9.5-6.5 9.5 6.5 9.5 6.5-3.5 6.5-9.5 6.5S2.5 12 2.5 12z", "circle:12,12,2.8"],
  external: ["M14 4h6v6", "M20 4l-9 9", "M18 14v6H4V6h6"],
};

function icon(name, extraClass = "") {
  const ns = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(ns, "svg");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("class", `icon ${extraClass}`.trim());
  svg.setAttribute("aria-hidden", "true");
  svg.setAttribute("focusable", "false");
  for (const part of ICONS[name] || []) {
    if (part.startsWith("circle:")) {
      const [cx, cy, r] = part.slice(7).split(",");
      const c = document.createElementNS(ns, "circle");
      c.setAttribute("cx", cx); c.setAttribute("cy", cy); c.setAttribute("r", r);
      svg.append(c);
    } else {
      const p = document.createElementNS(ns, "path");
      p.setAttribute("d", part);
      svg.append(p);
    }
  }
  return svg;
}

function fillIcons(root = document) {
  root.querySelectorAll("[data-icon]").forEach(slot => {
    slot.replaceWith(icon(slot.dataset.icon, slot.className));
  });
}
document.addEventListener("DOMContentLoaded", () => fillIcons());

/* ---------------------------------------------------------------- Messages */
function showNotice(container, kind, message) {
  const name = { error: "alert", warn: "alert", ok: "check", info: "info" }[kind] || "info";
  container.replaceChildren(el("div", { class: `notice ${kind}`, role: kind === "error" ? "alert" : "status" }, icon(name, "sm"), el("span", {}, message)));
}

function showLoading(container) {
  container.replaceChildren(el("div", { class: "loading", role: "status" }, el("span", { class: "spinner" }), t("loading")));
}

function emptyState(iconName, title, body) {
  return el("div", { class: "empty" }, icon(iconName), el("p", { class: "empty-title" }, title), body ? el("p", {}, body) : null);
}

/* ---------------------------------------------------------------- Formatting */
function rupees(value, decimals = 0) {
  if (value === null || value === undefined || isNaN(value)) return "—";
  return "₹" + Number(value).toLocaleString("en-IN", { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
}

function kg(value) {
  return `${Number(value).toLocaleString("en-IN", { maximumFractionDigits: 2 })} ${t("unit_kg")}`;
}

function formatDate(isoDate, withYear = true) {
  if (!isoDate) return "—";
  const [y, m, d] = String(isoDate).slice(0, 10).split("-").map(Number);
  const date = new Date(y, m - 1, d); // local date, avoids the "one day earlier" timezone bug
  const options = withYear ? { day: "numeric", month: "short", year: "numeric" } : { day: "numeric", month: "short" };
  return date.toLocaleDateString(getLang() === "hi" ? "hi-IN" : "en-IN", options);
}

function numberOrNull(value) {
  const n = parseFloat(String(value ?? "").replace(/,/g, "").trim());
  return isNaN(n) ? null : n;
}

/* ---------------------------------------------------------------- Small storage helpers */
function storageGet(key) {
  try { return localStorage.getItem(key) || ""; } catch (e) { return ""; }
}

function storageSet(key, value) {
  try { localStorage.setItem(key, value); } catch (e) { /* ignore */ }
}
