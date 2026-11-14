/* Late Rains, Next Crop — app logic.
   Reads precomputed results only. No analysis, no fetch of anything but the
   data file, no number that is not in it. */

(function () {
  "use strict";

  var DATA_URLS = [
    "../results/app_data.json",
    "app_data.json"
  ];

  var MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

  var state = { data: null, pinned: null };

  /* ── helpers ─────────────────────────────────────────────────── */

  function $(sel, root) { return (root || document).querySelector(sel); }

  function el(tag, attrs, text) {
    var node = document.createElementNS(
      tag === "svg" || attrs && attrs.__svg ? "http://www.w3.org/2000/svg" : "http://www.w3.org/1999/xhtml",
      tag
    );
    if (attrs) {
      Object.keys(attrs).forEach(function (k) {
        if (k === "__svg") return;
        node.setAttribute(k, attrs[k]);
      });
    }
    if (text != null) node.textContent = text;
    return node;
  }

  function svgEl(tag, attrs) {
    var node = document.createElementNS("http://www.w3.org/2000/svg", tag);
    if (attrs) Object.keys(attrs).forEach(function (k) { node.setAttribute(k, attrs[k]); });
    return node;
  }

  function num(value, digits) {
    if (value == null || isNaN(value)) return "—";
    return Number(value).toLocaleString("en-GB", {
      minimumFractionDigits: digits == null ? 0 : digits,
      maximumFractionDigits: digits == null ? 0 : digits
    });
  }

  /* DOY is counted on a common year. Never turn it into a full date: the app
     shows a month and day only, as docs/app_data_schema.md requires. */
  function doyLabel(doy) {
    if (doy == null || isNaN(doy)) return "—";
    var d = Math.round(doy);
    var date = new Date(Date.UTC(2026, 0, 1));
    date.setUTCDate(d);
    return date.getUTCDate() + " " + MONTHS[date.getUTCMonth()];
  }

  function pct(part, whole) {
    if (!whole) return "—";
    return Math.round((part / whole) * 100) + "%";
  }

  /* ── nav ─────────────────────────────────────────────────────── */

  var VIEWS = { answer: "The answer", rain: "The rain record", crops: "Crops and rules" };

  function showView(name) {
    if (!VIEWS[name]) name = "answer";
    Object.keys(VIEWS).forEach(function (key) {
      var view = document.getElementById("view-" + key);
      var button = $('.step[data-view="' + key + '"]');
      var on = key === name;
      if (view) view.hidden = !on;
      if (button) {
        if (on) button.setAttribute("aria-current", "page");
        else button.removeAttribute("aria-current");
      }
    });
    if (location.hash !== "#" + name) history.replaceState(null, "", "#" + name);
    window.scrollTo({ top: 0, behavior: "instant" in window ? "instant" : "auto" });
  }

  document.addEventListener("click", function (event) {
    var step = event.target.closest(".step");
    if (step) { showView(step.dataset.view); return; }
    var jump = event.target.closest("[data-goto]");
    if (jump) showView(jump.dataset.goto);
  });

  /* ── screen 1: answer ────────────────────────────────────────── */

  function renderAnswer(data) {
    var first = season(data, "first_rains");
    var annual = data.annual || {};

    $("#fact-site").textContent = data.site.name + " · " +
      Math.abs(data.site.lat) + "° N, " + Math.abs(data.site.lon) + "° E";
    $("#fact-period").textContent = data.period.start_date.slice(0, 4) + "–" +
      data.period.end_date.slice(0, 4) + " (" + data.period.n_years + " years)";
    $("#fact-scale").textContent = data.site.scale_note || "district scale";

    if (first) {
      $("#answer-when").innerHTML =
        "The 10-day rain threshold is first met around <strong>" +
        doyLabel(first.onset_doy_median) + "</strong> in a typical year. " +
        "In the middle half of years it lands between <strong>" +
        doyLabel(first.onset_doy_p25) + "</strong> and <strong>" +
        doyLabel(first.onset_doy_p75) + "</strong>.";

      var dry = first.years_with_dry_spell_ge_7d_in_next_30d;
      $("#answer-when-note").textContent =
        "That is " + first.years_found + " of " + first.years_evaluated +
        " years. In " + dry + " of those " + first.years_found +
        " (" + pct(dry, first.years_found) +
        "), a dry spell of 7 days or more followed within 30 days. " +
        "This is the day the threshold is met, not the first rain day.";

      var sens = first.threshold_sensitivity || [];
      var low = sens.filter(function (s) { return s.rain_10d_threshold_mm === 15; })[0];
      var high = sens.filter(function (s) { return s.rain_10d_threshold_mm === 25; })[0];
      var spread = low && high ? Math.round(high.onset_doy_median - low.onset_doy_median) : null;

      $("#answer-oneline").innerHTML =
        "In " + data.site.name + ", the rains arrive in a known range, and " +
        "that range is the useful part: " + doyLabel(first.onset_doy_p25) +
        " to " + doyLabel(first.onset_doy_p75) + " in half of years. " +
        "Which crop to plant is <strong>not yet</strong> answerable, because no " +
        "crop requirement in this build has a source.";

      $("#answer-caveat").innerHTML =
        "The trigger that defines the date is still unsourced, and it matters: " +
        "at a 15&nbsp;mm trigger the median moves to " + doyLabel(low.onset_doy_median) +
        ", at 25&nbsp;mm to " + doyLabel(high.onset_doy_median) +
        (spread != null ? " — a " + spread + "-day swing on a value nobody has sourced. " : ". ") +
        "The annual total for comparison is " + num(annual.rain_mm_mean, 0) +
        "&nbsp;mm mean over " + annual.n_years_complete + " complete years.";
    }

    var totalRules = (data.crop_rule_coverage || []).reduce(function (sum, c) {
      return sum + (c.n_rules_sourced || 0);
    }, 0);
    var expected = (data.crop_rule_coverage || []).reduce(function (sum, c) {
      return sum + (c.n_rules_expected || 0);
    }, 0);
    var rulesText = totalRules === 0
      ? "no sourced rows yet"
      : totalRules + " of " + expected + " sourced rows";
    $("#answer-rules").textContent = rulesText;
    var cropsSourced = $("#crops-sourced");
    if (cropsSourced) cropsSourced.textContent = rulesText;
  }

  function season(data, name) {
    return (data.onset.summary || []).filter(function (s) { return s.season === name; })[0];
  }

  /* ── screen 2: charts ────────────────────────────────────────── */

  function renderMonthly(data) {
    var rows = data.monthly_climatology || [];
    if (!rows.length) return;

    var W = 720, H = 250, padL = 34, padB = 26, padT = 16;
    var plotW = W - padL - 8, plotH = H - padB - padT;
    var max = 0;
    rows.forEach(function (r) { max = Math.max(max, r.rain_mm_p75 || 0, r.rain_mm_mean || 0); });
    max = Math.ceil(max / 20) * 20;

    var svg = svgEl("svg", {
      viewBox: "0 0 " + W + " " + H,
      role: "img",
      "aria-label": "Monthly rainfall mean with the middle half of years, " +
        data.site.name + ", " + data.period.n_years + " years"
    });

    [0, 0.5, 1].forEach(function (t) {
      var y = padT + plotH - t * plotH;
      svg.appendChild(svgEl("line", {
        x1: padL, x2: W - 8, y1: y, y2: y, class: "axis-line"
      }));
      var label = svgEl("text", { x: padL - 6, y: y + 3, class: "axis-label", "text-anchor": "end" });
      label.textContent = Math.round(t * max);
      svg.appendChild(label);
    });

    var slot = plotW / rows.length;
    var barW = Math.min(30, slot * 0.52);

    rows.forEach(function (r, i) {
      var cx = padL + slot * (i + 0.5);
      var h = (r.rain_mm_mean / max) * plotH;
      var y = padT + plotH - h;

      var bar = svgEl("rect", {
        x: cx - barW / 2, y: y, width: barW, height: Math.max(h, 1),
        class: "bar-total"
      });
      var title = svgEl("title");
      title.textContent = MONTHS[i] + ": mean " + num(r.rain_mm_mean, 0) +
        " mm, middle half " + num(r.rain_mm_p25, 0) + "–" + num(r.rain_mm_p75, 0) +
        " mm over " + r.n_years + " years";
      bar.appendChild(title);
      svg.appendChild(bar);

      var qy1 = padT + plotH - (r.rain_mm_p25 / max) * plotH;
      var qy2 = padT + plotH - (r.rain_mm_p75 / max) * plotH;
      svg.appendChild(svgEl("line", {
        x1: cx, x2: cx, y1: qy2, y2: qy1, class: "iqr-line"
      }));
      svg.appendChild(svgEl("line", { x1: cx - 4, x2: cx + 4, y1: qy1, y2: qy1, class: "iqr-cap" }));

      var month = svgEl("text", { x: cx, y: H - 8, class: "axis-label", "text-anchor": "middle" });
      month.textContent = MONTHS[i];
      svg.appendChild(month);
    });

    var fig = $("#fig-monthly");
    fig.innerHTML = "";
    fig.appendChild(svg);
    $("#cap-monthly").textContent =
      "Mean monthly rainfall, " + data.site.name + ", NASA POWER " +
      data.period.start_date.slice(0, 4) + "–" + data.period.end_date.slice(0, 4) +
      ". " + data.annual.rain_mm_mean + " mm mean a year. " +
      data.annual.n_years_complete + " complete years, " + rows[0].n_years +
      " contributing to each month.";
  }

  function renderStrip(data) {
    var rows = (data.onset.by_year || []).filter(function (r) {
      return r.season === "first_rains" && r.onset_found;
    }).sort(function (a, b) { return a.year - b.year; });
    if (!rows.length) return;

    var first = season(data, "first_rains");

    // The x-range comes from the data, not from a guess: the earliest and
    // latest onset in the record, with a little air. No empty half-panel.
    var doys = rows.map(function (r) { return r.onset_doy; });
    var lo = Math.min.apply(null, doys) - 8;
    var hi = Math.max.apply(null, doys) + 8;

    var rowH = 12, padT = 14, padL = 46, padR = 16;
    var W = 880, plotW = W - padL - padR;
    var H = padT + rows.length * rowH + 18;

    function x(doy) { return padL + ((doy - lo) / (hi - lo)) * plotW; }

    var svg = svgEl("svg", {
      viewBox: "0 0 " + W + " " + H,
      role: "img",
      "aria-label": "First-rains onset by year, " + rows.length + " years"
    });

    // middle half band
    if (first) {
      svg.appendChild(svgEl("rect", {
        x: x(first.onset_doy_p25), y: padT,
        width: Math.max(1, x(first.onset_doy_p75) - x(first.onset_doy_p25)),
        height: rows.length * rowH, class: "strip-band"
      }));
      svg.appendChild(svgEl("line", {
        x1: x(first.onset_doy_median), x2: x(first.onset_doy_median),
        y1: padT, y2: padT + rows.length * rowH, class: "strip-median"
      }));
    }

    // Month ticks, only the months this record actually spans.
    [1, 32, 60, 91, 121, 152].forEach(function (doy) {
      if (doy < lo || doy > hi) return;
      var t = svgEl("text", {
        x: x(doy), y: H - 4, class: "axis-label", "text-anchor": "middle"
      });
      t.textContent = doyLabel(doy);
      svg.appendChild(t);
    });

    rows.forEach(function (row, i) {
      var y = padT + i * rowH + rowH / 2;
      var g = svgEl("g", {
        class: "strip-row", tabindex: "0", role: "button",
        "aria-label": row.year + ": onset " + doyLabel(row.onset_doy) +
          ", longest dry spell after " + row.longest_dry_spell_next_30d + " days"
      });

      var yearText = svgEl("text", {
        x: padL - 9, y: y + 3.4, class: "strip-year", "text-anchor": "end"
      });
      yearText.textContent = row.year;
      g.appendChild(yearText);

      var wet = (row.longest_dry_spell_next_30d || 0) < 7;
      g.appendChild(svgEl("circle", {
        cx: x(row.onset_doy), cy: y, r: 5.2,
        class: "strip-mark " + (wet ? "strip-mark--wet" : "strip-mark--dry")
      }));

      g.addEventListener("mouseenter", function () { paint(row.year); });
      g.addEventListener("focus", function () { paint(row.year); });
      g.addEventListener("click", function () { state.pinned = row.year; paint(row.year); });
      g.addEventListener("keydown", function (event) {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          state.pinned = row.year;
          paint(row.year);
        }
      });

      svg.appendChild(g);
    });

    var fig = $("#fig-strip");
    fig.innerHTML = "";
    fig.appendChild(svg);

    function paint(year) {
      Array.prototype.forEach.call(svg.querySelectorAll(".strip-year"), function (t) {
        t.classList.toggle("strip-year--hit", t.textContent === String(year));
      });
      var row = rows.filter(function (r) { return r.year === year; })[0];
      if (!row) return;
      var wet = (row.longest_dry_spell_next_30d || 0) < 7;
      $("#strip-readout").innerHTML =
        "<strong>" + row.year + "</strong> — threshold met on <strong>" +
        doyLabel(row.onset_doy) + "</strong>. " + num(row.rain_next_30d_mm, 1) +
        " mm in the next 30 days, longest dry spell " +
        row.longest_dry_spell_next_30d + " days" +
        (wet ? " (no long dry spell)." : " (7 days or more — a real risk to a seedling).");
    }

    paint(state.pinned || rows[rows.length - 1].year);
  }

  function renderSensitivity(data) {
    var first = season(data, "first_rains");
    var body = $("#table-sensitivity tbody");
    body.innerHTML = "";
    if (!first || !first.threshold_sensitivity) return;
    var working = (data.onset.definition || {}).rain_10d_threshold_mm;

    first.threshold_sensitivity.forEach(function (row) {
      var tr = document.createElement("tr");
      var unsourced = row.rain_10d_threshold_mm !== working;
      if (unsourced) tr.className = "is-open";
      tr.innerHTML =
        "<td class=\"num\">" + num(row.rain_10d_threshold_mm, 0) + " mm</td>" +
        "<td class=\"num\">" + doyLabel(row.onset_doy_median) + "</td>" +
        "<td class=\"num\">" + row.years_found + " of " + first.years_evaluated + "</td>";
      body.appendChild(tr);
    });

    var s = first.threshold_sensitivity;
    var spread = Math.round(s[s.length - 1].onset_doy_median - s[0].onset_doy_median);
    $("#sensitivity-note").innerHTML =
      "The " + num(working, 0) + "&nbsp;mm row is the working value, and it is an <strong>assumption</strong>, " +
      "not a sourced agronomic rule. The band moves the median " + spread +
      " days. Any finding that vanishes between " + num(s[0].rain_10d_threshold_mm, 0) +
      " and " + num(s[s.length - 1].rain_10d_threshold_mm, 0) + "&nbsp;mm is not a finding.";
  }

  function renderDry(data) {
    var first = season(data, "first_rains");
    if (!first) return;
    var dry = first.years_with_dry_spell_ge_7d_in_next_30d;
    var total = first.years_found;
    $("#dryfig").innerHTML = pct(dry, total) +
      " <small>of years — " + dry + " of " + total + "</small>";
    var meter = $("#drymeter");
    meter.innerHTML = "";
    var fill = document.createElement("i");
    fill.style.width = Math.round((dry / total) * 100) + "%";
    meter.appendChild(fill);
    meter.setAttribute("aria-label",
      dry + " of " + total + " years had a dry spell of 7 days or more within 30 days of onset");
  }

  function renderSecond(data) {
    var second = season(data, "second_rains");
    var body = $("#table-second tbody");
    body.innerHTML = "";
    if (!second) return;
    var heading = $("#h-second");
    if (heading && second.label) heading.textContent = second.label;
    var tr = document.createElement("tr");
    tr.innerHTML =
      "<td class=\"num\">" + doyLabel(second.onset_doy_median) + "</td>" +
      "<td class=\"num\">" + doyLabel(second.onset_doy_p25) + " – " + doyLabel(second.onset_doy_p75) + "</td>" +
      "<td class=\"num\">" + second.years_found + " of " + second.years_evaluated + "</td>" +
      "<td class=\"num\">" + second.years_with_dry_spell_ge_7d_in_next_30d + " of " + second.years_found + "</td>";
    body.appendChild(tr);
  }

  /* ── screen 3: crops ─────────────────────────────────────────── */

  function renderCoverage(data) {
    var body = $("#table-coverage tbody");
    body.innerHTML = "";
    (data.crop_rule_coverage || []).forEach(function (c) {
      var sourced = c.n_rules_sourced || 0;
      var expected = c.n_rules_expected || 4;
      var tr = document.createElement("tr");
      if (sourced < expected) tr.className = "is-open";
      tr.innerHTML =
        "<td>" + c.crop_label + "</td>" +
        "<td class=\"num\">" + sourced + " of " + expected + "</td>" +
        "<td class=\"" + (sourced >= 3 ? "" : "unknown") + "\">" +
        (sourced >= 3 ? "can be shown" : "cut — under three sourced rules") + "</td>";
      body.appendChild(tr);
    });
  }

  function renderWindows(data) {
    var body = $("#table-windows tbody");
    body.innerHTML = "";

    var crops = data.crops || [];
    var panel = $("#panel-windows");

    // No sourced crop row, no comparison table. The waiting state on the
    // screen above already says why, so this panel stays out of sight.
    if (!crops.length) {
      if (panel) panel.hidden = true;
      return;
    }
    if (panel) panel.hidden = false;

    crops.forEach(function (crop) {
      var tr = document.createElement("tr");
      var documented = crop.documented_window_start_doy != null
        ? doyLabel(crop.documented_window_start_doy) +
          (crop.documented_window_end_doy != null ? " – " + doyLabel(crop.documented_window_end_doy) : "")
        : null;
      var computed = crop.supported_window_start_doy != null
        ? doyLabel(crop.supported_window_start_doy)
        : null;
      var gap = crop.gap_days;
      var unknown = crop.unknown_rules || [];
      if (unknown.length) tr.className = "is-open";

      var holds;
      if (crop.holds_across_band === true) holds = "yes";
      else if (crop.holds_across_band === false) holds = "<span class=\"unknown\">no — trigger artefact</span>";
      else holds = "<span class=\"unknown\">unknown</span>";

      tr.innerHTML =
        "<td>" + crop.crop_label + "</td>" +
        "<td>" + (documented || "<span class=\"unknown\">unknown</span>") + "</td>" +
        "<td>" + (computed || "<span class=\"unknown\">no data</span>") + "</td>" +
        "<td class=\"num\">" + (gap == null ? "—" : (gap > 0 ? "+" + gap : gap) + " d") + "</td>" +
        "<td>" + holds + "</td>" +
        "<td>" + (crop.source_label || (unknown.length ? unknown.length + " of 4 rules unknown" : "sourced")) + "</td>";
      body.appendChild(tr);
    });

    $("#windows-note").innerHTML =
      "Positive gap means the rainfall-supported start is later than documented practice. " +
      "A gap that disappears when the trigger moves from 20 to 25&nbsp;mm is not a finding.";
  }

  function renderSoil(data) {
    var list = $("#soil");
    var soil = data.soil;
    if (!list || !soil) return;
    var rows = [
      ["pH in water, 0–30 cm", soil.ph_h2o == null ? "unknown" : num(soil.ph_h2o, 2)],
      ["Clay", soil.clay_pct == null ? "unknown" : num(soil.clay_pct, 0) + "%"],
      ["Sand", soil.sand_pct == null ? "unknown" : num(soil.sand_pct, 0) + "%"],
      ["Silt", soil.silt_pct == null ? "unknown" : num(soil.silt_pct, 0) + "%"],
      ["Texture adds up to", soil.texture_sum_pct == null ? "unknown" : num(soil.texture_sum_pct, 0) + "%"]
    ];
    list.innerHTML = "";
    rows.forEach(function (row) {
      var wrap = document.createElement("div");
      var dt = document.createElement("dt");
      var dd = document.createElement("dd");
      dt.textContent = row[0];
      dd.textContent = row[1];
      wrap.appendChild(dt);
      wrap.appendChild(dd);
      list.appendChild(wrap);
    });
  }

  /* ── provenance ─────────────────────────────────────────────── */

  function renderProvenance(data) {
    var list = $("#sources");
    list.innerHTML = "";
    (data.meta.sources || []).forEach(function (source) {
      var li = document.createElement("li");
      li.innerHTML = source.name + " — <a href=\"" + source.url + "\">" + source.url + "</a> (read " + source.accessed + ")";
      list.appendChild(li);
    });
    var rulesSource = document.createElement("li");
    rulesSource.textContent = "Crop rules — rules/rules.csv, one source per row; unknown where none.";
    list.appendChild(rulesSource);

    $("#prov-line").textContent =
      "Pipeline: " + data.meta.pipeline + ". Raw cache SHA-256 " +
      (data.meta.raw_cache_sha256 || "").slice(0, 16) + "… . File built " +
      data.generated_utc + ". Schema " + data.schema_version + ".";
  }

  /* ── boot ───────────────────────────────────────────────────── */

  function boot(data) {
    state.data = data;
    document.body.classList.add("has-data");
    renderAnswer(data);
    renderMonthly(data);
    renderStrip(data);
    renderSensitivity(data);
    renderDry(data);
    renderSecond(data);
    renderCoverage(data);
    renderWindows(data);
    renderSoil(data);
    renderProvenance(data);
  }

  function fail(message) {
    var main = $("#main");
    main.insertAdjacentHTML("afterbegin",
      "<div class=\"panel panel--blocked\"><h3>Data file not read</h3>" +
      "<p class=\"lede\">" + message + "</p>" +
      "<p class=\"note\">The app reads <code>results/app_data.json</code> and computes nothing, " +
      "so with no file there is nothing honest to show.</p></div>");
  }

  function tryLoad(index) {
    if (index >= DATA_URLS.length) {
      fail("No app data file was found next to the page.");
      return;
    }
    fetch(DATA_URLS[index], { cache: "no-store" })
      .then(function (response) {
        if (!response.ok) throw new Error("HTTP " + response.status);
        return response.json();
      })
      .then(boot)
      .catch(function () { tryLoad(index + 1); });
  }

  showView((location.hash || "#answer").slice(1));
  window.addEventListener("hashchange", function () {
    showView(location.hash.slice(1));
  });
  tryLoad(0);
})();
