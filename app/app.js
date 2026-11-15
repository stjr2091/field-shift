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
  var VOICE_API_BASE = (new URLSearchParams(window.location.search).get("voice") ||
    (USE_MOCK ? "http://127.0.0.1:8099" : API_BASE)).replace(/\/+$/, "");

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
  var voiceStart = document.getElementById("voice-start");
  var voiceRepeat = document.getElementById("voice-repeat");
  var voiceRecord = document.getElementById("voice-record");
  var voiceStop = document.getElementById("voice-stop");
  var voiceCancel = document.getElementById("voice-cancel");
  var voiceQuestion = document.getElementById("voice-question");
  var voiceTranscript = document.getElementById("voice-transcript");
  var voiceStatus = document.getElementById("voice-status");
  var voiceAssistant = document.getElementById("voice-assistant");
  var voiceProgress = document.getElementById("voice-progress");
  var voiceAnswer = document.getElementById("voice-answer");

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
    voiceAnswer.hidden = false;

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
        if (state.voiceSession) {
          setVoiceState("speaking", "Playing your advice");
          playVoice(cardEn.textContent).catch(function () {
            setVoiceState("error", "Advice playback unavailable");
            voiceStatus.textContent = "Advice is ready. Choose “Listen to this advice” to hear it.";
          }).then(function () {
            if (voiceAssistant.getAttribute("data-state") === "speaking") {
              setVoiceState("complete", "Advice playback complete");
            }
          });
        }
      })
      .catch(function () {
        showError("The advice service did not answer. Check the connection and try again.");
      })
      .then(function () { setLoading(false); });
  });

  /* ── guided voice questions ─────────────────────────────────── */

  var voiceQuestions = [
    {
      prompt: "Which crops have you grown, from oldest to most recent? Name maize, common bean, finger millet, sorghum, or groundnut. Say none if you have no crop history.",
      read: function (transcript) {
        var text = transcript.toLowerCase();
        if (/\b(none|no crops?|nothing|not grown)\b/.test(text)) {
          state.crops = [];
          drawCrops();
          return;
        }
        var matches = [
          { key: "maize", pattern: /\b(maize|corn)\b/ },
          { key: "common_bean", pattern: /\b(common\s+beans?|beans?)\b/ },
          { key: "finger_millet", pattern: /\b(finger\s+millet|millet)\b/ },
          { key: "sorghum", pattern: /\bsorghum\b/ },
          { key: "groundnut", pattern: /\b(ground\s*nuts?|peanuts?)\b/ }
        ].map(function (crop) {
          var match = crop.pattern.exec(text);
          return match ? { key: crop.key, index: match.index } : null;
        }).filter(Boolean).sort(function (a, b) { return a.index - b.index; });
        if (!matches.length) throw new Error("I could not identify a supported crop. Please answer with one or more crop names, or say none.");
        state.crops = matches.map(function (crop) { return crop.key; });
        drawCrops();
      }
    },
    {
      prompt: "What is the soil pH? Say a number from zero to fourteen, such as six point one. Say skip if you do not know.",
      read: function (transcript) {
        if (/\b(skip|unknown|do not know|don't know)\b/i.test(transcript)) {
          soilPh.value = "";
          return;
        }
        var value = spokenNumber(transcript);
        if (value === null || value < 0 || value > 14) {
          throw new Error("I could not identify a pH from zero to fourteen. Please say the number again, or say skip.");
        }
        soilPh.value = String(value);
      }
    },
    {
      prompt: "How is the soil moisture? Describe it briefly, or say skip if you do not know.",
      read: function (transcript) {
        moisture.value = /\b(skip|unknown|do not know|don't know)\b/i.test(transcript) ? "" : transcript;
      }
    }
  ];
  var voiceQuestionIndex = 0;
  var recordedStream = null;
  var recordedContext = null;
  var recordedProcessor = null;
  var recordedGain = null;
  var recordedChunks = [];
  var currentAudio = null;

  function voiceRequest(path, options) {
    return fetch(VOICE_API_BASE + path, options).then(function (response) {
      if (!response.ok) {
        return response.json().catch(function () { return {}; }).then(function (data) {
          throw new Error(data.error || "Voice service returned HTTP " + response.status + ".");
        });
      }
      return response;
    });
  }

  function playVoice(text) {
    return voiceRequest("/voice/speak", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: text })
    }).then(function (response) { return response.blob(); })
      .then(function (blob) {
        if (currentAudio) {
          currentAudio.pause();
          URL.revokeObjectURL(currentAudio.src);
        }
        currentAudio = new Audio(URL.createObjectURL(blob));
        return currentAudio.play();
      });
  }

  function currentVoicePrompt() {
    return voiceQuestions[voiceQuestionIndex].prompt;
  }

  function setVoiceState(stateName, progress) {
    voiceAssistant.setAttribute("data-state", stateName);
    voiceProgress.textContent = progress || "";
    voiceProgress.hidden = !progress;
  }

  function askCurrentVoiceQuestion() {
    voiceQuestion.textContent = currentVoicePrompt();
    setVoiceState("speaking", "Question " + (voiceQuestionIndex + 1) + " of " + voiceQuestions.length);
    voiceRecord.hidden = true;
    voiceRepeat.hidden = false;
    voiceCancel.hidden = false;
    voiceStatus.textContent = "Playing the question…";
    playVoice(currentVoicePrompt()).then(function () {
      setVoiceState("ready", "Question " + (voiceQuestionIndex + 1) + " of " + voiceQuestions.length);
      voiceStatus.textContent = "Press Record answer when you are ready.";
      voiceRecord.hidden = false;
    }).catch(function (error) {
      setVoiceState("error", "Question " + (voiceQuestionIndex + 1) + " of " + voiceQuestions.length);
      voiceStatus.textContent = "Voice question could not be played: " + error.message;
      voiceRecord.hidden = false;
    });
  }

  function beginVoiceRecording() {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia || !window.AudioContext) {
      voiceStatus.textContent = "This browser cannot record audio. Use a current browser on HTTPS or localhost.";
      return;
    }
    navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1 } }).then(function (stream) {
      recordedStream = stream;
      recordedContext = new AudioContext();
      recordedChunks = [];
      var source = recordedContext.createMediaStreamSource(stream);
      recordedProcessor = recordedContext.createScriptProcessor(4096, 1, 1);
      recordedGain = recordedContext.createGain();
      recordedGain.gain.value = 0;
      recordedProcessor.onaudioprocess = function (event) {
        recordedChunks.push(new Float32Array(event.inputBuffer.getChannelData(0)));
      };
      source.connect(recordedProcessor);
      recordedProcessor.connect(recordedGain);
      recordedGain.connect(recordedContext.destination);
      setVoiceState("listening", "Listening · question " + (voiceQuestionIndex + 1) + " of " + voiceQuestions.length);
      voiceRecord.hidden = true;
      voiceStop.hidden = false;
      voiceStatus.textContent = "Listening… Press Finish answer when you are done.";
    }).catch(function () {
      setVoiceState("error", "Question " + (voiceQuestionIndex + 1) + " of " + voiceQuestions.length);
      voiceStatus.textContent = "Microphone access was not available. Allow microphone access and try again.";
      voiceRecord.hidden = false;
    });
  }

  function wavFromRecording(chunks, sampleRate) {
    var totalLength = chunks.reduce(function (sum, chunk) { return sum + chunk.length; }, 0);
    var source = new Float32Array(totalLength);
    var offset = 0;
    chunks.forEach(function (chunk) {
      source.set(chunk, offset);
      offset += chunk.length;
    });
    var targetRate = 16000;
    var targetLength = Math.floor(source.length * targetRate / sampleRate);
    var samples = new DataView(new ArrayBuffer(44 + targetLength * 2));
    var writeText = function (position, text) {
      for (var i = 0; i < text.length; i += 1) samples.setUint8(position + i, text.charCodeAt(i));
    };
    writeText(0, "RIFF");
    samples.setUint32(4, 36 + targetLength * 2, true);
    writeText(8, "WAVE");
    writeText(12, "fmt ");
    samples.setUint32(16, 16, true);
    samples.setUint16(20, 1, true);
    samples.setUint16(22, 1, true);
    samples.setUint32(24, targetRate, true);
    samples.setUint32(28, targetRate * 2, true);
    samples.setUint16(32, 2, true);
    samples.setUint16(34, 16, true);
    writeText(36, "data");
    samples.setUint32(40, targetLength * 2, true);
    var ratio = sampleRate / targetRate;
    for (var j = 0; j < targetLength; j += 1) {
      var position = j * ratio;
      var left = Math.floor(position);
      var fraction = position - left;
      var value = source[left] * (1 - fraction) + (source[left + 1] || 0) * fraction;
      value = Math.max(-1, Math.min(1, value));
      samples.setInt16(44 + j * 2, value < 0 ? value * 32768 : value * 32767, true);
    }
    return new Blob([samples.buffer], { type: "audio/wav" });
  }

  function spokenNumber(text) {
    var normalized = text.toLowerCase().replace(/-/g, " ");
    var digits = normalized.match(/\b\d+(?:\.\d+)?\b/);
    if (digits) return Number(digits[0]);
    var words = {
      zero: 0, oh: 0, one: 1, two: 2, three: 3, four: 4, five: 5,
      six: 6, seven: 7, eight: 8, nine: 9, ten: 10, eleven: 11,
      twelve: 12, thirteen: 13, fourteen: 14
    };
    var decimal = normalized.match(/\b(zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen)\s+point\s+(zero|one|two|three|four|five|six|seven|eight|nine)\b/);
    if (decimal) return words[decimal[1]] + words[decimal[2]] / 10;
    var match = normalized.match(/\b(zero|oh|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen)\b/);
    return match ? words[match[1]] : null;
  }

  function stopVoiceRecording() {
    if (!recordedContext) return;
    var sampleRate = recordedContext.sampleRate;
    recordedProcessor.disconnect();
    recordedGain.disconnect();
    recordedStream.getTracks().forEach(function (track) { track.stop(); });
    var context = recordedContext;
    recordedProcessor = null;
    recordedGain = null;
    recordedStream = null;
    recordedContext = null;
    voiceStop.hidden = true;
    setVoiceState("transcribing", "Transcribing your answer");
    voiceStatus.textContent = "Transcribing your answer…";
    context.close().then(function () {
      return voiceRequest("/voice/transcribe", {
        method: "POST",
        headers: { "Content-Type": "audio/wav" },
        body: wavFromRecording(recordedChunks, sampleRate)
      });
    }).then(function (response) { return response.json(); })
      .then(function (data) {
        var transcript = String(data.transcript || "").trim();
        if (!transcript) throw new Error("No speech was recognized. Please try again.");
        voiceTranscript.textContent = "Heard: “" + transcript + "”";
        voiceTranscript.hidden = false;
        voiceQuestions[voiceQuestionIndex].read(transcript);
        voiceQuestionIndex += 1;
        if (voiceQuestionIndex < voiceQuestions.length) {
          askCurrentVoiceQuestion();
        } else {
          state.voiceSession = true;
          voiceStart.hidden = false;
          voiceStart.textContent = "Start over";
          voiceRepeat.hidden = true;
          voiceRecord.hidden = true;
          voiceCancel.hidden = true;
          setVoiceState("complete", "All " + voiceQuestions.length + " questions complete");
          voiceQuestion.textContent = "Your answers are in the form. Review them, then choose Get advice.";
          voiceStatus.textContent = "Check the crop history, pH, and moisture above. Your planting date stays optional.";
          playVoice(voiceQuestion.textContent).catch(function () {});
        }
      }).catch(function (error) {
        setVoiceState("ready", "Question " + (voiceQuestionIndex + 1) + " of " + voiceQuestions.length);
        voiceStatus.textContent = error.message;
        voiceRecord.hidden = false;
      });
  }

  voiceStart.addEventListener("click", function () {
    state.voiceSession = false;
    voiceQuestionIndex = 0;
    voiceStart.textContent = "Start voice questions";
    voiceTranscript.hidden = true;
    voiceStart.hidden = true;
    askCurrentVoiceQuestion();
  });
  voiceRepeat.addEventListener("click", askCurrentVoiceQuestion);
  voiceRecord.addEventListener("click", beginVoiceRecording);
  voiceStop.addEventListener("click", stopVoiceRecording);
  voiceCancel.addEventListener("click", function () {
    if (recordedStream) recordedStream.getTracks().forEach(function (track) { track.stop(); });
    if (recordedContext) recordedContext.close();
    recordedStream = null;
    recordedContext = null;
    recordedProcessor = null;
    recordedGain = null;
    voiceStart.hidden = false;
    voiceRepeat.hidden = true;
    voiceRecord.hidden = true;
    voiceStop.hidden = true;
    voiceCancel.hidden = true;
    voiceQuestion.textContent = "";
    voiceStatus.textContent = "Voice questions cancelled.";
    voiceStart.textContent = "Start voice questions";
    setVoiceState("idle", "");
    state.voiceSession = false;
  });
  voiceAnswer.addEventListener("click", function () {
    setVoiceState("speaking", "Playing the advice");
    voiceStatus.textContent = "Playing the advice…";
    playVoice(cardEn.textContent).then(function () {
      setVoiceState("complete", "Advice playback complete");
      voiceStatus.textContent = "Advice playback finished.";
    }).catch(function (error) {
      setVoiceState("error", "Advice playback unavailable");
      voiceStatus.textContent = "Advice could not be played: " + error.message;
    });
  });

  drawCrops();
  loadDistrict();
  loadSampleSeason();
})();
