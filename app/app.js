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
     "?api=https://example.org/advice" posts to the live service instead. */
  var API_PARAM = new URLSearchParams(window.location.search).get("api");
  var USE_MOCK = !API_PARAM || API_PARAM === "mock";
  var API_URL = API_PARAM || "";

  var state = { crops: [], district: "" };

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
    if (state.district) body.district = state.district;

    return body;
  }

  function getAdvice(body) {
    if (USE_MOCK) {
      return new Promise(function (resolve) { setTimeout(resolve, 450); })
        .then(function () { return fetch("mock_response.json", { cache: "no-store" }); })
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
    lugandaBlock.hidden = !data.card_lg;

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
      .then(renderCard)
      .catch(function () {
        showError("The advice service did not answer. Check the connection and try again.");
      })
      .then(function () { setLoading(false); });
  });

  drawCrops();
  loadDistrict();
})();
