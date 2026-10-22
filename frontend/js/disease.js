/* Crop Doctor page. Owner: Member D (backend endpoint by Member B)
   Sends the leaf photo to POST /api/disease/predict and shows the answer as a diagnosis slip. */

const photoInput = document.getElementById("photo");
const dropzone = document.getElementById("dropzone");
const shot = document.getElementById("shot");
const preview = document.getElementById("preview");
const scanLabel = document.getElementById("scanLabel");
const photoButton = document.getElementById("photoButton");
const statusBox = document.getElementById("status");
const resultBox = document.getElementById("result");
let lastResult = null;
let busy = false;
let previewUrl = null;

/* Phone photos are often 3-8 MB. Shrink to at most 1024 px so upload is fast on weak Wi-Fi.
   The model only looks at 224 x 224 pixels anyway. */
async function shrinkImage(file, maxSide = 1024) {
  if (!window.createImageBitmap) return file;
  try {
    const bitmap = await createImageBitmap(file, { imageOrientation: "from-image" });
    const scale = Math.min(1, maxSide / Math.max(bitmap.width, bitmap.height));
    if (scale === 1 && file.size < 1.5 * 1024 * 1024) return file;
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(bitmap.width * scale);
    canvas.height = Math.round(bitmap.height * scale);
    canvas.getContext("2d").drawImage(bitmap, 0, 0, canvas.width, canvas.height);
    const blob = await new Promise(resolve => canvas.toBlob(resolve, "image/jpeg", 0.9));
    return blob || file;
  } catch (e) {
    return file; // older browser: send the original, the server can handle it
  }
}

function speak(lines) {
  if (!("speechSynthesis" in window)) return;
  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(lines.join(". "));
  utterance.lang = getLang() === "hi" ? "hi-IN" : "en-IN";
  window.speechSynthesis.speak(utterance);
}

function renderEmpty() {
  resultBox.replaceChildren(el("div", { class: "placeholder" },
    emptyState("leaf", t("doc_empty_title"), t("doc_empty_body"))));
}

function renderResult(data, scroll = false) {
  const lang = getLang();
  const r = data.result;
  const kind = !data.confident ? "unsure" : r.healthy ? "healthy" : "danger";
  const badgeIcon = { unsure: "question", healthy: "check", danger: "alert" }[kind];
  const advice = r.advice[lang] || r.advice.en;
  const spoken = [r.crop ? r.crop[lang] : "", r.name[lang], ...advice, r.healthy ? "" : data.expert[lang]].filter(Boolean);

  const slip = el("article", { class: `slip is-${kind}` },
    el("header", { class: "slip-head" },
      el("span", { class: "slip-badge" }, icon(badgeIcon, "lg")),
      el("div", {},
        r.crop ? el("p", { class: "slip-crop" }, r.crop[lang]) : null,
        el("h2", { class: "slip-name" }, r.name[lang]),
        el("span", { class: "slip-status" }, t(`doc_status_${kind}`)),
      ),
    ),
    el("div", { class: "slip-body" },
      !data.confident && data.uncertain_reason ? el("div", { class: "slip-section" },
        el("div", { class: "notice warn", style: "margin-top:0" }, icon("alert", "sm"),
          el("span", {}, t(`doc_reason_${data.uncertain_reason}`)))) : null,
      data.confident ? el("div", { class: "slip-section" },
        el("p", { class: "slip-label" }, el("span", {}, t("doc_confidence")), el("strong", { class: "num" }, `${data.confidence}%`)),
        el("div", { class: "meter", role: "img", "aria-label": `${t("doc_confidence")}: ${data.confidence}%` },
          el("span", { style: `width:${Math.max(3, Math.min(100, data.confidence))}%` })),
      ) : null,
      el("div", { class: "slip-section" },
        el("p", { class: "slip-label" }, t("doc_advice")),
        el("ul", { class: "advice" }, advice.map(line => el("li", {}, line))),
      ),
      r.management ? el("div", { class: "slip-section" },
        el("p", { class: "slip-label" }, t("doc_immediate")),
        el("ul", { class: "advice" }, ((r.management.immediate_steps && (r.management.immediate_steps[lang] || r.management.immediate_steps.en)) || []).map(line => el("li", {}, line))),
      ) : null,
      r.management ? el("div", { class: "slip-section" },
        el("p", { class: "slip-label" }, t("doc_crop_care")),
        el("ul", { class: "advice tips" }, ((r.management.crop_care && (r.management.crop_care[lang] || r.management.crop_care.en)) || []).map(line => el("li", {}, line))),
      ) : null,
      r.management ? el("div", { class: "slip-section" },
        el("details", { class: "method" },
          el("summary", {}, t("doc_prevention")),
          el("ul", { class: "advice" }, ((r.management.prevention && (r.management.prevention[lang] || r.management.prevention.en)) || []).map(line => el("li", {}, line))),
        ),
        el("details", { class: "method", style: "margin-top:10px" },
          el("summary", {}, t("doc_monitoring")),
          el("ul", { class: "advice" }, ((r.management.monitoring && (r.management.monitoring[lang] || r.management.monitoring.en)) || []).map(line => el("li", {}, line))),
        ),
        el("details", { class: "method", style: "margin-top:10px" },
          el("summary", {}, t("doc_escalate")),
          el("ul", { class: "advice" }, ((r.management.escalate_if && (r.management.escalate_if[lang] || r.management.escalate_if.en)) || []).map(line => el("li", {}, line))),
        ),
        el("details", { class: "method", style: "margin-top:10px" },
          el("summary", {}, t("doc_chemical_safety")),
          el("ul", { class: "advice" }, ((r.management.chemical_safety && (r.management.chemical_safety[lang] || r.management.chemical_safety.en)) || []).map(line => el("li", {}, line))),
        ),
        r.sources && r.sources.length ? el("details", { class: "method", style: "margin-top:10px" },
          el("summary", {}, t("doc_sources")),
          el("ul", { class: "link-list" }, r.sources.map(source => el("li", {}, el("a", { class: "ext-link", href: source.url, target: "_blank", rel: "noopener noreferrer" }, (lang === "hi" && source.label_hi) || source.label)))),
        ) : null,
      ) : null,
      r.healthy ? null : el("div", { class: "slip-section" },
        el("p", { class: "expert" }, icon("phone"), el("span", {}, data.expert[lang], " ",
          el("a", { href: "tel:18001801551" }, t("mk_call")))),
      ),
      data.alternatives && data.alternatives.length ? el("div", { class: "slip-section" },
        el("p", { class: "slip-label" }, t("doc_other")),
        el("ul", { class: "alts" }, data.alternatives.map(a => el("li", {},
          el("span", {}, a.crop ? `${a.crop[lang]}: ${a.name[lang]}` : a.name[lang]),
          el("span", { class: "bar", "aria-hidden": "true" }, el("span", { style: `width:${Math.max(2, Math.min(100, a.confidence))}%` })),
          el("span", { class: "pct num" }, `${a.confidence}%`),
        ))),
      ) : null,
      el("p", { class: "panel-sub" }, icon("info", "sm"), " ", t("doc_model_limit")),
      el("div", { class: "btn-group" },
        "speechSynthesis" in window ? el("button", {
          class: "btn btn-ghost btn-sm", type: "button", onclick: () => speak(spoken),
        }, icon("speaker", "sm"), t("doc_listen")) : null,
        el("button", { class: "btn btn-quiet btn-sm", type: "button", onclick: () => photoInput.click() },
          icon("refresh", "sm"), t("doc_again")),
      ),
    ),
  );
  resultBox.replaceChildren(slip);
  if (scroll && window.matchMedia("(max-width: 899px)").matches) slip.scrollIntoView({ behavior: "smooth", block: "start" });
}

function setScanning(on) {
  busy = on;
  dropzone.classList.toggle("is-scanning", on);
  scanLabel.hidden = !on;
  resultBox.setAttribute("aria-busy", String(on));
  photoButton.setAttribute("aria-disabled", String(on));
}

async function checkPhoto(file) {
  if (!file || busy) return;
  if (file.type && !file.type.startsWith("image/")) { showNotice(statusBox, "error", t("err_not_image")); return; }
  statusBox.replaceChildren();
  if (previewUrl) URL.revokeObjectURL(previewUrl);
  previewUrl = URL.createObjectURL(file);
  preview.src = previewUrl;
  shot.hidden = false;
  dropzone.classList.add("has-photo");
  setScanning(true);

  try {
    const image = await shrinkImage(file);
    const form = new FormData();
    form.append("file", image, "leaf.jpg"); // the name "file" must match the FastAPI parameter
    lastResult = await apiUpload("/api/disease/predict", form);
    renderResult(lastResult, true);
  } catch (err) {
    lastResult = null;
    renderEmpty();
    showNotice(statusBox, "error", err.message);
  } finally {
    setScanning(false);
    photoInput.value = ""; // lets the same photo be chosen again
  }
}

photoInput.addEventListener("change", () => checkPhoto(photoInput.files && photoInput.files[0]));
photoButton.addEventListener("click", (event) => { if (busy) event.preventDefault(); });
dropzone.addEventListener("click", (event) => { if (busy) event.preventDefault(); });

/* Drag and drop a photo (laptop) */
["dragenter", "dragover"].forEach(type => dropzone.addEventListener(type, (event) => {
  event.preventDefault();
  dropzone.classList.add("is-over");
}));
["dragleave", "drop"].forEach(type => dropzone.addEventListener(type, () => dropzone.classList.remove("is-over")));
dropzone.addEventListener("drop", (event) => {
  event.preventDefault();
  checkPhoto(event.dataTransfer.files && event.dataTransfer.files[0]);
});

document.addEventListener("langchange", () => { if (lastResult) renderResult(lastResult); else renderEmpty(); });
renderEmpty();
