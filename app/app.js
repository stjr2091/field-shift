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
     "?api=https://example.org/advice" posts to the live service instead.
     The sample itself follows the request: a planting date shows the
     dated sample, a blank date shows the default second-season sample. */
  var API_PARAM = new URLSearchParams(window.location.search).get("api");
  var USE_MOCK = !API_PARAM || API_PARAM === "mock" || API_PARAM === "mock-nolg";
  var STRIP_LG = API_PARAM === "mock-nolg";
  var MOCK_DEFAULT_FILE = "mock_response.json";
  var MOCK_DATED_FILE = "mock_response_dated.json";
  var API_URL = USE_MOCK ? "" : API_PARAM;
  /* The advice base: the POST URL without its endpoint, e.g. the ?api= URL
     minus a trailing /recommend. The pre-submit assumption reads from here. */
  var API_BASE = API_URL.replace(/\/recommend\/?$/, "");

  var state = { crops: [], district: "" };

  var form = document.getElementById("advice-form");
  var cropSelect = document.getElementById("crop-select");
  var addButton = document.getElementById("add-crop");
  var cropList = document.getElementById("crop-list");
  var cropEmpty = document.getElementById("crop-empty");
  var soilPh = document.getElementById("soil-ph");
  var moisture = document.getElementById("moisture");
  var plantingDate = document.getElementById("planting-date");
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
        districtEl.textContent = "Not available";
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
    submitButton.textContent = on ? "Getting advice…" : "Get advice";
    statusEl.textContent = on ? "Reading the field and the season." : "";
  }

  function buildRequest() {
    var body = { previous_crops: state.crops.slice() };

    var rawPh = soilPh.value.trim();
    if (rawPh !== "") {
      var ph = Number(rawPh);
      if (!isFinite(ph) || ph < 0 || ph > 14) {
        showError("Enter a soil pH between 0 and 14, or leave it blank.");
        soilPh.focus();
        return null;
      }
      body.soil_ph = ph;
    }

    var rawMoisture = moisture.value.trim();
    if (rawMoisture !== "") body.moisture = rawMoisture;

    /* A date is sent only when given. The type=date input already limits
       the value to ISO YYYY-MM-DD or empty; further checks are the
       server's business. */
    if (plantingDate.value) body.planting_date = plantingDate.value;

    if (state.district) body.district = state.district;

    return body;
  }

  function mockFileFor(body) {
    return body && body.planting_date ? MOCK_DATED_FILE : MOCK_DEFAULT_FILE;
  }

  function getAdvice(body) {
    if (USE_MOCK) {
      var file = mockFileFor(body);
      return new Promise(function (resolve) { setTimeout(resolve, 450); })
        .then(function () { return fetch(file, { cache: "no-store" }); })
        .then(function (response) {
          if (!response.ok) throw new Error("HTTP " + response.status);
          return response.json();
        })
        .then(function (data) {
          if (STRIP_LG) delete data.card_lg;
          return data;
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
     asking for advice. In mock mode the sample for the current date choice
     fills it, and a date change refreshes it. With the live service it
     fills from GET <api-base>/assumption on load, and stays empty until
     the first response if that fetch fails. */
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
    fetch(MOCK_DEFAULT_FILE, { cache: "no-store" })
      .then(function (response) { return response.ok ? response.json() : null; })
      .then(function (data) {
        if (data && data.season_assumption) showSeasonNote(data.season_assumption);
      })
      .catch(function () { /* the card still shows the assumption after submit */ });
  }

  plantingDate.addEventListener("change", function () {
    if (!USE_MOCK) return;
    fetch(mockFileFor({ planting_date: plantingDate.value || null }), { cache: "no-store" })
      .then(function (response) { return response.ok ? response.json() : null; })
      .then(function (data) {
        if (data && data.season_assumption) showSeasonNote(data.season_assumption);
      })
      .catch(function () { /* the note keeps its last text */ });
  });

  function renderCard(data) {
    setText(resultTitle, data.recommended_crop || "Advice");
    setText(whenEl, data.when || "No supported timing in this response.");
    setText(cardEn, data.card_en || data.why || "No advice text was returned.");
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

    setText(cardLg, data.card_lg || "");
    lugandaBlock.hidden = false;
    if (data.card_lg) {
      cardLg.hidden = false;
      lugandaMissing.hidden = true;
      lugandaBlock.setAttribute("lang", "lg");
    } else {
      cardLg.hidden = true;
      lugandaMissing.hidden = false;
      lugandaBlock.setAttribute("lang", "en");
    }

    setText(seasonEl, data.season_assumption || SEASON_MISSING);
    seasonBlock.hidden = false;
    showSeasonNote(data.season_assumption);

    badge.hidden = !USE_MOCK;

    result.hidden = false;
    resultTitle.setAttribute("tabindex", "-1");
    resultTitle.focus({ preventScroll: true });
    result.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  form.addEventListener("submit", function (event) {
    event.preventDefault();
    clearError();

    var body = buildRequest();
    if (!body) return;

    setLoading(true);
    getAdvice(body)
      .then(function (data) {
        /* The server owns date checks. If it reports a problem, show its
           message in the form error line instead of the card. */
        if (data && data.error) {
          showError(String(data.error));
          return;
        }
        renderCard(data);
      })
      .catch(function () {
        showError("The advice service did not answer. Check the connection and try again.");
      })
      .then(function () { setLoading(false); });
  });

  drawCrops();
  loadDistrict();
  loadSampleSeason();
})();
