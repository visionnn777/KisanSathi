/* Home page: shows a live "today's best price" card from the price API. Owner: Member D
   Uses only existing endpoints: /api/prices/status, /states, /commodities, /best.
   It always shows the market report date, so old data is never presented as today's price.
   If there is no price data (or the server is off), the card simply stays hidden. */

const liveCard = document.getElementById("live");
const hero = document.getElementById("hero");
const PREFERRED_CROPS = ["Wheat", "Paddy(Dhan)(Common)", "Potato", "Tomato", "Onion", "Maize", "Mustard"];
let live = null; // { state, commodity, best, sample, daysOld }

function renderLive() {
  if (!live) return;
  const markets = live.best.markets.slice(0, 2);
  liveCard.classList.toggle("is-sample", live.sample);
  liveCard.replaceChildren(
    el("div", { class: "live-head" },
      el("span", { class: "live-dot", id: "liveTitle" }, t("home_live")),
      el("span", { class: "live-sample" }, t("home_live_sample")),
      !live.sample && live.daysOld > 3 ? el("span", { class: "live-old" }, tf("home_live_old", { n: live.daysOld })) : null,
    ),
    el("p", { class: "live-crop" }, tf("home_live_line", { crop: cropLabel(live.commodity), state: stateName(live.state) })),
    el("div", { class: "live-rows" }, markets.map((m, i) => el("div", { class: `live-row${i === 0 ? " top" : ""}` },
      el("span", { class: "live-market" }, marketName(m.market, live.state)),
      el("span", { class: "live-price num" }, rupees(m.modal_price)),
    ))),
    el("div", { class: "live-foot" },
      el("span", {}, `${tf("home_live_date", { date: formatDate(live.best.date) })}, ₹ ${t("pr_per_quintal")}`),
      el("a", { href: "prices.html" }, t("home_live_more")),
    ),
  );
  liveCard.hidden = false;
  hero.classList.remove("no-live");
}

function daysSince(isoDate) {
  if (!isoDate) return null;
  const [y, m, d] = String(isoDate).slice(0, 10).split("-").map(Number);
  const today = new Date();
  return Math.round((new Date(today.getFullYear(), today.getMonth(), today.getDate()) - new Date(y, m - 1, d)) / 864e5);
}

async function pickCrop(state) {
  const crops = await apiGet("/api/prices/commodities", { state });
  return PREFERRED_CROPS.find(c => crops.includes(c)) || crops[0];
}

(async function loadLive() {
  hero.classList.add("no-live");
  try {
    const status = await apiGet("/api/prices/status");
    if (!status.rows) return;
    const states = await apiGet("/api/prices/states");
    const saved = storageGet("priceState");
    const order = states.includes(saved) ? [saved, ...states.filter(s => s !== saved)] : states;
    for (const state of order.slice(0, 3)) {
      const commodity = await pickCrop(state);
      if (!commodity) continue;
      const best = await apiGet("/api/prices/best", { state, commodity, limit: 3 });
      if (best.markets.length) {
        live = { state, commodity, best, sample: best.source === "sample", daysOld: daysSince(best.date) };
        renderLive();
        return;
      }
    }
  } catch (err) {
    /* No server or no data: the home page works without the live card. */
  }
})();

document.addEventListener("langchange", renderLive);
