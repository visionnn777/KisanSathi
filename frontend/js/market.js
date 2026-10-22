/* Sell & buy page. Owner: Member D (backend endpoints by Member A)
   Farmers manage their listings with phone number + private PIN (POST /api/listings/mine). */

const TABS = ["sell", "buy", "mine"];
const sellForm = document.getElementById("sellForm");
const sellStatus = document.getElementById("sellStatus");
const cropChips = document.getElementById("cropChips");
const otherCropField = document.getElementById("otherCropField");
const cropOther = document.getElementById("s_crop_other");
const qtyInput = document.getElementById("s_qty");
const priceInput = document.getElementById("s_price");
const totalLine = document.getElementById("totalLine");
const totalValue = document.getElementById("totalValue");
const searchForm = document.getElementById("searchForm");
const buyList = document.getElementById("buyList");
const mineForm = document.getElementById("mineForm");
const minePhone = document.getElementById("m_phone");
const minePin = document.getElementById("m_pin");
const sellPin = document.getElementById("s_owner_pin");
const mineList = document.getElementById("mineList");
const sellState = document.getElementById("s_state");
let buyItems = null;
let mineItems = null;
let selectedCrop = SELL_CROPS[0];
let otpRequired = false;
const phoneTokens = {};   // phone -> short-lived verification token (memory only)

/* ---------------------------------------------------------------- Phone verification (only if the server asks for it) */
function cleanPhone(value) {
  const digits = String(value || "").replace(/\D/g, "");
  if (digits.length === 12 && digits.startsWith("91")) return digits.slice(2);
  if (digits.length === 11 && digits.startsWith("0")) return digits.slice(1);
  return digits;
}
function tokenFor(phone) { return phoneTokens[cleanPhone(phone)] || null; }
function otpBlock(slot, phoneInput) {
  const status = el("div", { "aria-live": "polite" });
  const code = el("input", { class: "input num", type: "text", inputmode: "numeric", maxlength: "6", pattern: "\\d{6}", autocomplete: "one-time-code", "aria-label": t("otp_code") });
  const send = el("button", { class: "btn btn-ghost btn-sm", type: "button" }, t("otp_send"));
  const verify = el("button", { class: "btn btn-primary btn-sm", type: "button" }, t("otp_verify"));
  send.addEventListener("click", async () => {
    const phone = cleanPhone(phoneInput.value);
    if (phone.length !== 10) { showNotice(status, "error", t("err_phone")); return; }
    send.disabled = true;
    try {
      const reply = await apiSend("POST", "/api/auth/otp/request", { phone });
      showNotice(status, "info", reply.provider === "console" ? t("otp_sent_demo") : t("otp_sent"));
      code.focus();
    } catch (err) { showNotice(status, "error", err.message); }
    finally { send.disabled = false; }
  });
  verify.addEventListener("click", async () => {
    const phone = cleanPhone(phoneInput.value);
    try {
      const reply = await apiSend("POST", "/api/auth/otp/verify", { phone, code: code.value.trim() });
      phoneTokens[phone] = reply.phone_token;
      showNotice(status, "ok", t("otp_ok"));
    } catch (err) { showNotice(status, "error", err.message); }
  });
  slot.replaceChildren(el("p", { class: "label" }, t("otp_title")), el("p", { class: "hint" }, t("otp_help")),
    el("div", { class: "inline-input" }, send, code, verify), status);
  slot.hidden = false;
}
async function loadAuthConfig() {
  try {
    otpRequired = Boolean((await apiGet("/api/auth/config")).otp_required);
  } catch (_) { otpRequired = false; }
  if (otpRequired) {
    otpBlock(document.getElementById("sellOtpSlot"), document.getElementById("s_phone"));
    otpBlock(document.getElementById("mineOtpSlot"), minePhone);
  }
}
function fillSellStates(selected) {
  const options = STATE_CHOICES.map(v => ({ v, label: stateName(v) })).sort((a, b) => a.label.localeCompare(b.label, getLang() === "hi" ? "hi" : "en"));
  sellState.replaceChildren(el("option", { value: "" }, t("crop_choose_state")),
    ...options.map(({ v, label }) => el("option", { value: v, selected: v === selected }, label)));
}

/* ---------------------------------------------------------------- Tabs (with #sell / #buy / #mine in the address) */
function openTab(name, focus = false) {
  if (!TABS.includes(name)) name = "sell";
  for (const key of TABS) {
    const tab = document.getElementById(`tab-${key}`);
    const selected = key === name;
    tab.setAttribute("aria-selected", String(selected));
    tab.tabIndex = selected ? 0 : -1;
    document.getElementById(`panel-${key}`).hidden = !selected;
    if (selected && focus) tab.focus();
  }
  if (location.hash !== `#${name}`) history.replaceState(null, "", `#${name}`);
  if (name === "buy" && buyItems === null) loadBuyList();
  if (name === "mine" && minePhone.value && minePin.value && mineItems === null) loadMine();
}
TABS.forEach((key, index) => {
  const tab = document.getElementById(`tab-${key}`);
  tab.addEventListener("click", () => openTab(key));
  tab.addEventListener("keydown", (event) => {
    const step = { ArrowRight: 1, ArrowLeft: -1 }[event.key];
    if (step) { event.preventDefault(); openTab(TABS[(index + step + TABS.length) % TABS.length], true); }
  });
});
window.addEventListener("hashchange", () => openTab(location.hash.slice(1)));

/* ---------------------------------------------------------------- PIN show / hide */
function setPinButton(button, visible) {
  button.replaceChildren(t(visible ? "mk_pin_hide" : "mk_pin_show"));
  button.setAttribute("aria-pressed", String(visible));
}
document.querySelectorAll("[data-pin-toggle]").forEach(button => {
  const input = document.getElementById(button.dataset.pinToggle);
  button.addEventListener("click", () => {
    const visible = input.type === "password";
    input.type = visible ? "text" : "password";
    setPinButton(button, visible);
    input.focus();
  });
});
function pinValid(value) { return typeof value === "string" && value.length >= 8; }

/* ---------------------------------------------------------------- Shared bits */
function place(l) {
  // Known towns come from the name table; other villages are written phonetically in Hindi.
  const village = l.village ? (getLang() === "hi" ? marketName(l.village, l.state) : l.village) : null;
  return [village, l.district ? districtName(l.state, l.district) : null, l.state ? stateName(l.state) : null].filter(Boolean).join(", ");
}

function listingHead(l) {
  return el("div", { class: "listing-top" },
    el("h3", { class: "listing-crop" }, cropLabel(l.crop)),
    el("div", { class: "listing-price" },
      el("strong", { class: "num" }, rupees(l.price_per_kg, 2)),
      el("span", {}, t("per_kg")),
    ),
  );
}

function fact(iconName, text) {
  return text ? el("span", { class: "fact" }, icon(iconName, "sm"), text) : null;
}

/* Hindi crop or district names typed into search are turned into the English names stored in the database. */
/* Hindi spellings vary (गेहूँ / गेहूं, प्याज़ / प्याज), so compare without nasal marks and nukta. */
function hiKey(text) { return String(text || "").trim().replace(/\u0901/g, "\u0902").replace(/\u093C/g, ""); }
function hiMatches(hindi, typed) { const a = hiKey(hindi), b = hiKey(typed); return Boolean(b) && (a === b || a.startsWith(b)); }
function cropQuery(text) {
  const value = text.trim();
  if (!isHindiText(value)) return value;
  const legacy = Object.entries(CROP_NAMES).find(([, hindi]) => hiMatches(hindi, value));
  if (legacy) return legacy[0];
  const sellMatch = SELL_CROPS.find(c => hiMatches(cropLabel(c), value));
  if (sellMatch) return sellMatch;
  const known = Object.entries(NT.crops).find(([, hindi]) => hiMatches(hindi, value));
  return known ? known[0] : value;
}
function districtQuery(text) {
  const value = text.trim();
  if (!isHindiText(value)) return value;
  const entry = NT.districts.find(([, hindi]) => hiKey(hindi) === hiKey(value))
    || NT.districts.find(([, hindi]) => hiMatches(hindi, value));
  return entry ? entry[0].split(" (")[0] : value;
}

/* ---------------------------------------------------------------- Sell */
function renderCropChips() {
  const options = [...SELL_CROPS, "__other"];
  cropChips.replaceChildren(...options.map(c => el("label", { class: "chip" },
    el("input", { type: "radio", name: "crop", value: c, checked: c === selectedCrop }),
    el("span", {}, c === "__other" ? t("crop_other") : cropLabel(c)),
  )));
}

cropChips.addEventListener("change", (event) => {
  selectedCrop = event.target.value;
  otherCropField.hidden = selectedCrop !== "__other";
  if (selectedCrop === "__other") cropOther.focus();
});

function updateTotal() {
  const qty = numberOrNull(qtyInput.value);
  const price = numberOrNull(priceInput.value);
  const show = qty > 0 && price > 0;
  totalLine.hidden = !show;
  if (show) totalValue.textContent = rupees(qty * price);
}
qtyInput.addEventListener("input", updateTotal);
priceInput.addEventListener("input", updateTotal);

sellForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const f = sellForm.elements;
  const body = {
    farmer_name: f.farmer_name.value.trim(),
    phone: f.phone.value.trim(),
    owner_pin: sellPin.value,
    crop: selectedCrop === "__other" ? cropOther.value.trim() : selectedCrop,
    quantity_kg: numberOrNull(f.quantity_kg.value),
    price_per_kg: numberOrNull(f.price_per_kg.value),
    village: f.village.value.trim() || null,
    district: f.district.value.trim() || null,
    state: f.state.value || null,
    phone_token: tokenFor(f.phone.value),
  };
  if (!pinValid(body.owner_pin)) { showNotice(sellStatus, "error", t("mk_pin_short")); sellPin.focus(); return; }
  if (otpRequired && !body.phone_token) { showNotice(sellStatus, "error", t("otp_needed")); return; }
  const button = sellForm.querySelector("button[type=submit]");
  button.disabled = true;
  try {
    await apiSend("POST", "/api/listings", body);
    showNotice(sellStatus, "ok", t("mk_posted"));
    storageSet("myPhone", body.phone);
    minePhone.value = body.phone;
    // The PIN stays only in this page's memory so the new listing is easy to manage now.
    // It is never written to localStorage or put in a URL.
    minePin.value = body.owner_pin;
    sellPin.value = "";
    qtyInput.value = "";
    priceInput.value = "";
    updateTotal();
    buyItems = null;
    mineItems = null;
  } catch (err) {
    showNotice(sellStatus, "error", err.message);
  } finally {
    button.disabled = false;
  }
});

/* ---------------------------------------------------------------- Buy */
function interestForm(listing, onCancel) {
  const id = n => `i_${n}_${listing.id}`;
  const status = el("div", { "aria-live": "polite" });
  const name = el("input", { class: "input", id: id("name"), maxlength: "80", required: true, autocomplete: "name" });
  const phone = el("input", { class: "input num", id: id("phone"), type: "tel", inputmode: "tel", maxlength: "16", required: true, autocomplete: "tel", placeholder: "98765 43210" });
  const offer = el("input", { class: "input num", id: id("offer"), type: "number", inputmode: "decimal", step: "any", min: "0.5" });
  const message = el("textarea", { class: "textarea", id: id("msg"), maxlength: "300" });
  const optional = () => el("span", { class: "optional" }, ` ${t("optional")}`);
  const send = el("button", { class: "btn btn-primary", type: "submit" }, t("mk_send"));
  const form = el("form", { class: "interest-form form", novalidate: true },
    el("div", { class: "row two" },
      el("div", { class: "field" }, el("label", { class: "label", for: name.id }, t("f_name")), name),
      el("div", { class: "field" }, el("label", { class: "label", for: phone.id }, t("f_phone")), phone),
    ),
    el("div", { class: "field" },
      el("label", { class: "label", for: offer.id }, t("f_offer"), optional()),
      el("div", { class: "input-unit" }, offer, el("span", { class: "unit" }, t("unit_rs_kg"))),
    ),
    el("div", { class: "field" }, el("label", { class: "label", for: message.id }, t("f_message"), optional()), message),
    el("div", { class: "btn-group" }, send,
      el("button", { class: "btn btn-quiet", type: "button", onclick: onCancel }, t("mk_cancel"))),
    status,
  );
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    send.disabled = true;
    try {
      await apiSend("POST", `/api/listings/${listing.id}/interest`, {
        buyer_name: name.value.trim(),
        phone: phone.value.trim(),
        offered_price_per_kg: numberOrNull(offer.value),
        message: message.value.trim() || null,
      });
      form.querySelectorAll("input, textarea, button").forEach(n => { n.disabled = true; });
      showNotice(status, "ok", t("mk_sent"));
    } catch (err) {
      showNotice(status, "error", err.message);
      send.disabled = false;
    }
  });
  return form;
}

function buyCard(l) {
  const slot = el("div", { class: "listing-actions" });
  const card = el("article", { class: "listing" },
    listingHead(l),
    el("div", { class: "facts" },
      fact("weight", kg(l.quantity_kg)),
      fact("pin", place(l)),
      fact("user", tf("mk_by", { name: getLang() === "hi" ? translitHi(l.farmer_name) : l.farmer_name })), // names typed in English are written in Hindi letters
      l.expires_at ? fact("calendar", tf("mk_open_until", { date: formatDate(l.expires_at) })) : null,
    ),
    l.interest_count ? el("div", { class: "facts" }, el("span", { class: "pill interest" }, tf("mk_interest_count", { n: l.interest_count }))) : null,
    slot,
  );
  const openButton = () => el("button", {
    class: "btn btn-ghost btn-sm", type: "button",
    onclick: () => {
      const form = interestForm(l, () => slot.replaceChildren(openButton()));
      slot.replaceChildren(form);
      form.querySelector("input").focus();
    },
  }, t("mk_interested"));
  slot.append(openButton());
  return card;
}

function renderBuyList() {
  if (buyItems === null) return;
  if (!buyItems.length) {
    buyList.replaceChildren(el("div", { class: "placeholder", style: "margin-top:18px" }, emptyState("search", t("mk_none"), t("mk_none_body"))));
    return;
  }
  buyList.replaceChildren(
    el("p", { class: "result-count" }, buyItems.length === 1 ? t("mk_count_one") : tf("mk_count", { n: buyItems.length })),
    el("div", { class: "listings cols" }, buyItems.map(buyCard)),
  );
}

async function loadBuyList() {
  showLoading(buyList);
  try {
    buyItems = await apiGet("/api/listings", {
      crop: cropQuery(document.getElementById("b_crop").value),
      district: districtQuery(document.getElementById("b_district").value),
    });
    renderBuyList();
  } catch (err) {
    showNotice(buyList, "error", err.message);
  }
}
searchForm.addEventListener("submit", (event) => { event.preventDefault(); loadBuyList(); });

/* ---------------------------------------------------------------- My listings */
function mineCard(l) {
  const status = el("div", { "aria-live": "polite" });
  const sold = l.status === "sold";
  const open = l.status === "available";
  const buyers = el("div", { class: "buyers" },
    el("p", { class: "buyers-title" }, `${t("mk_buyers")} (${l.interests.length})`),
    ...(l.interests.length ? l.interests.map(i => el("div", { class: "buyer" },
      el("div", {},
        el("p", { class: "buyer-name" }, i.buyer_name),
        el("p", { class: "buyer-meta num" }, [i.phone, i.offered_price_per_kg ? tf("mk_offer", { price: `${rupees(i.offered_price_per_kg, 2)} ${t("per_kg")}` }) : ""].filter(Boolean).join(", ")),
      ),
      el("a", { class: "btn btn-ghost btn-sm", href: `tel:${i.phone}` }, icon("phone", "sm"), t("mk_call")),
      i.message ? el("p", { class: "buyer-msg" }, i.message) : null,
    )) : [el("p", { class: "panel-sub", style: "margin-top:6px" }, t("mk_no_buyers"))]),
  );

  const card = el("article", { class: "listing" },
    listingHead(l),
    el("div", { class: "facts" },
      el("span", { class: `pill${open ? "" : " sold"}` }, t(`st_${l.status}`)),
      fact("weight", kg(l.quantity_kg)),
      fact("calendar", tf("mk_listed", { date: formatDate(l.created_at) })),
      open && l.expires_at ? fact("calendar", tf("mk_open_until", { date: formatDate(l.expires_at) })) : null,
    ),
    buyers,
    status,
  );

  if (open) {
    const credentials = () => ({ phone: minePhone.value.trim(), owner_pin: minePin.value, phone_token: tokenFor(minePhone.value) });
    const markSold = el("button", { class: "btn btn-ghost btn-sm", type: "button" }, icon("check", "sm"), t("mk_mark_sold"));
    const withdraw = el("button", { class: "btn btn-quiet btn-sm", type: "button" }, icon("close", "sm"), t("mk_withdraw"));
    const act = async (button, confirmKey, method, path) => {
      if (!window.confirm(t(confirmKey))) return;
      button.disabled = true;
      try {
        await apiSend(method, path, credentials());
        buyItems = null;
        loadMine();
      } catch (err) {
        showNotice(status, "error", err.message);
        button.disabled = false;
      }
    };
    markSold.addEventListener("click", () => act(markSold, "mk_confirm_sold", "PATCH", `/api/listings/${l.id}/sold`));
    withdraw.addEventListener("click", () => act(withdraw, "mk_confirm_withdraw", "POST", `/api/listings/${l.id}/withdraw`));
    card.append(el("div", { class: "btn-group", style: "margin-top:12px" }, markSold, withdraw));
  }
  return card;
}

function renderMine() {
  if (mineItems === null) return;
  if (!mineItems.length) {
    mineList.replaceChildren(el("div", { class: "placeholder", style: "margin-top:18px" }, emptyState("market", t("mk_none_mine"), t("mk_none_mine_body"))));
    return;
  }
  mineList.replaceChildren(el("div", { class: "listings cols", style: "margin-top:18px" }, mineItems.map(mineCard)));
}

async function loadMine() {
  const phone = minePhone.value.trim();
  const owner_pin = minePin.value;
  if (!phone) { showNotice(mineList, "error", t("err_phone")); return; }
  if (!pinValid(owner_pin)) { showNotice(mineList, "error", t("mk_pin_short")); return; }
  showLoading(mineList);
  try {
    // POST keeps the PIN out of the address bar and server logs.
    if (otpRequired && !tokenFor(phone)) { showNotice(mineList, "error", t("otp_needed")); return; }
    mineItems = await apiSend("POST", "/api/listings/mine", { phone, owner_pin, phone_token: tokenFor(phone) });
    storageSet("myPhone", phone);
    renderMine();
  } catch (err) {
    showNotice(mineList, "error", err.message);
  }
}
mineForm.addEventListener("submit", (event) => { event.preventDefault(); loadMine(); });

/* ---------------------------------------------------------------- Start */
document.addEventListener("langchange", () => {
  document.querySelectorAll("[data-pin-toggle]").forEach(button => {
    setPinButton(button, document.getElementById(button.dataset.pinToggle).type === "text");
  });
  renderCropChips();
  fillSellStates(sellState.value);
  if (otpRequired) loadAuthConfig();
  renderBuyList();
  renderMine();
});

minePhone.value = storageGet("myPhone");
minePin.value = ""; // the PIN is never remembered between visits
renderCropChips();
fillSellStates("");
loadAuthConfig();
openTab(location.hash.slice(1) || "sell");
