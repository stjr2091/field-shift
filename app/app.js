/* What to plant — one form, one advice card.
   No analysis here. The page sends the field details and shows the answer. */

(function () {
  "use strict";

  var CROP_LABELS = {
    maize: "Maize",
    common_bean: "Common bean",
    finger_millet: "Finger millet",
    sorghum: "Sorghum",
    groundnut: "Groundnut",
    other: "Other"
  };

  /* The API flag. No flag, or "?api=mock", uses the local sample response.
     "?api=mock-nolg" uses the sample without a Luganda card.
     "?api=https://example.org/advice" posts to the live service instead. */
  var API_PARAM = new URLSearchParams(window.location.search).get("api");
  var MOCK_FILES = { "mock": "mock_response.json", "mock-nolg": "mock_response_nolg.json" };
  var USE_MOCK = !API_PARAM || MOCK_FILES.hasOwnProperty(API_PARAM);
  var MOCK_FILE = USE_MOCK ? (MOCK_FILES[API_PARAM] || MOCK_FILES.mock) : "";
  var API_URL = USE_MOCK ? "" : API_PARAM;
  /* The advice base: the POST URL without its endpoint, e.g. the ?api= URL
     minus a trailing /recommend. The pre-submit assumption reads from here. */
  var API_BASE = API_URL.replace(/\/recommend\/?$/, "");

  var state = { crops: [], district: "" };

  /* ── language: one toggle, whole page ───────────────────────── */

  /* English defaults for text the page writes itself. The Luganda strings
     live in translations_lg.js; a missing key keeps the English text. */
  var EN = {
    "district-checking": "Checking the site…",
    "district-none": "Not available",
    "submit-idle": "Get advice",
    "submit-loading": "Getting advice…",
    "status-loading": "Reading the field and the season.",
    "error-service": "The advice service did not answer. Check the connection and try again.",
    "error-ph": "Enter a soil pH between 0 and 14, or leave it blank.",
    "when-fallback": "No supported timing in this response.",
    "card-fallback": "No advice text was returned.",
    "lg-missing": "Luganda card unavailable for this advice"
  };

  var lang = "en";
  var lastData = null;

  function t(key) {
    if (lang === "lg" && window.LG_STRINGS && window.LG_STRINGS[key]) {
      return window.LG_STRINGS[key];
    }
    return EN[key] || null;
  }

  /* Static page text carries data-i18n. The English text is captured once
     from the markup, then the table replaces it key by key. */
  var i18nNodes = Array.prototype.slice.call(document.querySelectorAll("[data-i18n]"));
  i18nNodes.forEach(function (node) {
    node.dataset.en = node.textContent;
  });

  function applyStaticLang() {
    i18nNodes.forEach(function (node) {
      var key = node.getAttribute("data-i18n");
      var text = (lang === "lg" && window.LG_STRINGS && window.LG_STRINGS[key]) || node.dataset.en;
      node.textContent = text;
    });
  }

  function setLang(next) {
    lang = next;
    document.documentElement.lang = lang === "lg" ? "lg" : "en";
    document.getElementById("lang-en").setAttribute("aria-pressed", lang === "en" ? "true" : "false");
    document.getElementById("lang-lg").setAttribute("aria-pressed", lang === "lg" ? "true" : "false");
    applyStaticLang();
    drawCrops();
    if (lastData) renderCard(lastData, { moveFocus: false });
  }

  var form = document.getElementById("advice-form");
  var cropSelect = document.getElementById("crop-select");
  var addButton = document.getElementById("add-crop");
  var cropList = document.getElementById("crop-list");
  var cropEmpty = document.getElementById("crop-empty");
  var soilPh = document.getElementById("soil-ph");
  var moisture = document.getElementById("moisture");
  var districtEl = document.getElementById("district");
  var submitButton = document.getElementById("submit");
  var statusEl = document.getElementById("status");
  var errorEl = document.getElementById("form-error");

  var result = document.getElementById("result");
  var resultTitle = document.getElementById("result-title");
  var whenEl = document.getElementById("when");
  var badge = document.getElementById("mock-badge");
  var cardEn = document.getElementById("card-en");
  var whyBlock = document.getElementById("why-block");
  var whyEl = document.getElementById("why");
  var reasonsEl = document.getElementById("reasons");
  var alternativeEl = document.getElementById("alternative");
  var alternativeBlock = document.querySelector(".alternative");
  var lugandaBlock = document.getElementById("luganda-block");
  var cardLg = document.getElementById("card-lg");
  var lugandaMissing = document.getElementById("luganda-missing");
  var seasonBlock = document.getElementById("season-block");
  var seasonEl = document.getElementById("season");
  var seasonNote = document.getElementById("season-note");
  var seasonNoteText = document.getElementById("season-note-text");

  /* ── previous crops ─────────────────────────────────────────── */

  function label(key) {
    if (lang === "lg" && window.LG_STRINGS && window.LG_STRINGS["crop-" + key]) {
      return window.LG_STRINGS["crop-" + key];
    }
    return CROP_LABELS[key] || key;
  }

  function drawCrops() {
    cropList.innerHTML = "";
    state.crops.forEach(function (key, index) {
      var item = document.createElement("li");
      item.className = "chip";

      var number = document.createElement("span");
      number.className = "chip-num";
      number.textContent = index + 1;
      item.appendChild(number);

      var name = document.createElement("span");
      name.textContent = label(key);
      item.appendChild(name);

      var remove = document.createElement("button");
      remove.type = "button";
      remove.textContent = "×";
      remove.setAttribute("aria-label", "Remove " + label(key));
      remove.addEventListener("click", function () {
        state.crops.splice(index, 1);
        drawCrops();
      });
      item.appendChild(remove);

      cropList.appendChild(item);
    });
    cropEmpty.hidden = state.crops.length > 0;
  }

  addButton.addEventListener("click", function () {
    var key = cropSelect.value;
    if (!key) {
      cropSelect.focus();
      return;
    }
    state.crops.push(key);
    cropSelect.value = "";
    drawCrops();
    addButton.focus();
  });

  /* ── district: read from the site, never chosen ─────────────── */

  function loadDistrict() {
    var urls = ["../results/app_data.json", "app_data.json"];
    var index = 0;

    function next() {
      if (index >= urls.length) {
        districtEl.textContent = t("district-none");
        return;
      }
      fetch(urls[index], { cache: "no-store" })
        .then(function (response) {
          if (!response.ok) throw new Error("HTTP " + response.status);
          return response.json();
        })
        .then(function (data) {
          var name = data && data.site && data.site.name;
          if (!name) throw new Error("no site name");
          state.district = name;
          districtEl.textContent = name;
        })
        .catch(function () {
          index += 1;
          next();
        });
    }

    next();
  }

  /* ── form ───────────────────────────────────────────────────── */

  function showError(message) {
    errorEl.textContent = message;
    errorEl.hidden = false;
  }

  function clearError() {
    errorEl.textContent = "";
    errorEl.hidden = true;
  }

  function setLoading(on) {
    submitButton.disabled = on;
    submitButton.textContent = on ? t("submit-loading") : t("submit-idle");
    statusEl.textContent = on ? t("status-loading") : "";
  }

  function buildRequest() {
    var body = { previous_crops: state.crops.slice() };

    var rawPh = soilPh.value.trim();
    if (rawPh !== "") {
      var ph = Number(rawPh);
      if (!isFinite(ph) || ph < 0 || ph > 14) {
        showError(t("error-ph"));
        soilPh.focus();
        return null;
      }
      body.soil_ph = ph;
    }

    var rawMoisture = moisture.value.trim();
    if (rawMoisture !== "") body.moisture = rawMoisture;
    if (state.district) body.district = state.district;

    return body;
  }

  function getAdvice(body) {
    if (USE_MOCK) {
      return new Promise(function (resolve) { setTimeout(resolve, 450); })
        .then(function () { return fetch(MOCK_FILE, { cache: "no-store" }); })
        .then(function (response) {
          if (!response.ok) throw new Error("HTTP " + response.status);
          return response.json();
        });
    }

    return fetch(API_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    }).then(function (response) {
      if (!response.ok) throw new Error("HTTP " + response.status);
      return response.json();
    });
  }

  /* ── result card ────────────────────────────────────────────── */

  function setText(node, value) {
    node.textContent = value == null ? "" : String(value);
  }

  var SEASON_MISSING = "The service did not state the season this advice assumes.";

  /* The assumption sits by the submit control, so the user reads it before
     asking for advice. In mock mode the sample fills it on load. With the
     live service it fills from GET <api-base>/assumption on load, and stays
     empty until the first response if that fetch fails. */
  function showSeasonNote(text) {
    setText(seasonNoteText, text || SEASON_MISSING);
    seasonNote.hidden = false;
  }

  function loadSampleSeason() {
    if (!USE_MOCK) {
      fetch(API_BASE + "/assumption", { cache: "no-store" })
        .then(function (response) {
          if (!response.ok) throw new Error("HTTP " + response.status);
          return response.json();
        })
        .then(function (data) {
          if (data && data.season_assumption) showSeasonNote(data.season_assumption);
        })
        .catch(function () { /* the note stays empty until the first response */ });
      return;
    }
    fetch(MOCK_FILE, { cache: "no-store" })
      .then(function (response) { return response.ok ? response.json() : null; })
      .then(function (data) {
        if (data && data.season_assumption) showSeasonNote(data.season_assumption);
      })
      .catch(function () { /* the card still shows the assumption after submit */ });
  }

  function renderCard(data, opts) {
    lastData = data;
    var lg = lang === "lg";

    setText(resultTitle, data.recommended_crop || "Advice");
    setText(whenEl, data.when || t("when-fallback"));

    /* LG mode shows the checked Luganda card when the service returned one;
       otherwise it keeps the English text and the honest fallback line. */
    if (lg && data.card_lg) {
      setText(cardEn, data.card_lg);
      cardEn.setAttribute("lang", "lg");
    } else {
      setText(cardEn, data.card_en || data.why || t("card-fallback"));
      cardEn.removeAttribute("lang");
    }
    setText(whyEl, data.why || "");

    reasonsEl.innerHTML = "";
    (data.reasons || []).forEach(function (reason) {
      var item = document.createElement("li");
      item.textContent = reason;
      reasonsEl.appendChild(item);
    });
    whyBlock.hidden = !data.why && !(data.reasons && data.reasons.length);

    setText(alternativeEl, data.alternative || "");
    alternativeBlock.hidden = !data.alternative;

    if (lg) {
      /* The whole card already reads in Luganda or carries the fallback
         line, so the separate Luganda block has nothing left to add. */
      lugandaBlock.hidden = true;
      document.getElementById("card-lg-fallback").hidden = !!data.card_lg;
    } else {
      lugandaBlock.hidden = false;
      document.getElementById("card-lg-fallback").hidden = true;
      setText(cardLg, data.card_lg || "");
      if (data.card_lg) {
        cardLg.hidden = false;
        lugandaMissing.hidden = true;
        lugandaBlock.setAttribute("lang", "lg");
      } else {
        cardLg.hidden = true;
        lugandaMissing.hidden = false;
        lugandaBlock.setAttribute("lang", "en");
      }
    }

    setText(seasonEl, data.season_assumption || SEASON_MISSING);
    seasonBlock.hidden = false;
    showSeasonNote(data.season_assumption);

    badge.hidden = !USE_MOCK;

    if (!opts || opts.moveFocus !== false) {
      result.hidden = false;
      resultTitle.setAttribute("tabindex", "-1");
      resultTitle.focus({ preventScroll: true });
      result.scrollIntoView({ behavior: "smooth", block: "start" });
    } else {
      result.hidden = false;
    }
  }

  document.getElementById("lang-en").addEventListener("click", function () { setLang("en"); });
  document.getElementById("lang-lg").addEventListener("click", function () { setLang("lg"); });

  form.addEventListener("submit", function (event) {
    event.preventDefault();
    clearError();

    var body = buildRequest();
    if (!body) return;

    setLoading(true);
    getAdvice(body)
      .then(renderCard)
      .catch(function () {
        showError(t("error-service"));
      })
      .then(function () { setLoading(false); });
  });

  drawCrops();
  loadDistrict();
  loadSampleSeason();
})();
