// Renders every data-driven table from data/data.json. No external libraries.
(function () {
  "use strict";
  var esc = function (s) {
    return String(s === undefined || s === null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  };
  function srcLink(id) {
    var D = window.NBA3;
    var s = D.sources[id];
    if (!s) return '<span class="pill bad">missing source ' + esc(id) + "</span>";
    return '<a href="' + esc(s.url) + '" target="_blank" rel="noopener" title="' + esc(s.title) + '">' + esc(id) + " ↗</a>";
  }
  // Turns free text such as "S1, S4" into links.
  function linkify(text) {
    return esc(text).replace(/\bS(\d)\b/g, function (m) {
      return srcLink(m);
    });
  }
  function statusPill(text) {
    var t = String(text || "").toLowerCase();
    var cls = "none";
    if (/verified|available|done|implemented/.test(t) && !/not|unknown|blocked|partial/.test(t)) cls = "ok";
    if (/partial|open|proposed|awaiting|located|needs/.test(t)) cls = "warn";
    if (/unknown|blocked|not |unconfirmed|missing/.test(t)) cls = "bad";
    return '<span class="pill ' + cls + '">' + esc(text) + "</span>";
  }
  function tableHTML(cols, rows, opts) {
    opts = opts || {};
    var h = '<div class="tablewrap"><table><thead><tr>';
    cols.forEach(function (c) { h += "<th>" + esc(c) + "</th>"; });
    h += "</tr></thead><tbody>";
    rows.forEach(function (r) {
      h += "<tr>";
      r.forEach(function (cell, i) {
        var raw = cell === null || cell === undefined ? "" : String(cell);
        var cls = "";
        if (raw === "") cls = "blank";
        var html;
        if (opts.html && opts.html[i]) html = opts.html[i](cell);
        else html = esc(raw);
        if (raw === "" && !(opts.html && opts.html[i])) html = '<span class="muted">—</span>';
        h += '<td class="' + cls + '">' + html + "</td>";
      });
      h += "</tr>";
    });
    h += "</tbody></table></div>";
    return h;
  }
  function withFilter(el, html) {
    el.innerHTML =
      '<div class="tools"><input class="filter" type="search" placeholder="Filter rows…" aria-label="Filter rows"><span class="muted small rowcount"></span></div>' +
      html;
    var input = el.querySelector("input.filter");
    var trs = el.querySelectorAll("tbody tr");
    var count = el.querySelector(".rowcount");
    function apply() {
      var q = input.value.toLowerCase().trim();
      var shown = 0;
      trs.forEach(function (tr) {
        var ok = !q || tr.textContent.toLowerCase().indexOf(q) !== -1;
        tr.style.display = ok ? "" : "none";
        if (ok) shown++;
      });
      count.textContent = shown + " of " + trs.length + " rows";
    }
    input.addEventListener("input", apply);
    apply();
  }
  var views = {
    injuries: function (el, D) {
      var I = D.injury_report;
      var rows = I.rows.map(function (r) { return [r[0], r[1], r[2], r[3], r[4], r[5], r[6]]; });
      var html = tableHTML(I.columns.concat(["Source"]), rows, {
        html: { 4: function (v) { return statusPill(v); }, 6: function (v) { return srcLink(v); } }
      });
      withFilter(el, html);
    },
    slate: function (el, D) {
      var S = D.slate;
      var cols = ["Date", "Local time", "ET", "Team 1 (as printed)", "Home/away order", "Team 2 (as printed)", "National TV", "Marker", "Betting line", "Source"];
      var rows = S.rows.map(function (r) {
        return [r[0], r[1], r[2], r[3], "not confirmed", r[5], r[6], r[7], "", r[8]];
      });
      var html = tableHTML(cols, rows, {
        html: {
          4: function (v) { return '<span class="pill warn">' + esc(v) + "</span>"; },
          8: function () { return '<span class="pill bad">unverified — no source</span>'; },
          9: function (v) { return srcLink(v); }
        }
      });
      withFilter(el, html);
    },
    rules: function (el, D) {
      var R = D.rules;
      var html = tableHTML(R.columns, R.rows, { html: { 2: function (v) { return srcLink(v); } } });
      withFilter(el, html);
    },
    questions: function (el, D) {
      var rows = D.questions.map(function (q) {
        return [q.id, q.question, q.status, q.answer, q.needed, q.sources];
      });
      var html = tableHTML(["ID", "Question", "Status", "Answer (as verified)", "Still needed", "Sources"], rows, {
        html: {
          2: function (v) { return statusPill(v); },
          5: function (v) { return linkify(v); }
        }
      });
      withFilter(el, html);
    },
    gates: function (el, D) {
      var rows = D.gates.map(function (g) { return [g.id, g.gate, g.rule, g.threshold, g.status, g.note]; });
      var html = tableHTML(["ID", "Gate", "Rule", "Threshold", "Status", "Note"], rows, {
        html: { 4: function (v) { return statusPill(v); } }
      });
      withFilter(el, html);
    },
    suggestions: function (el, D) {
      var html = '<div class="cards sugg">';
      D.suggestions.forEach(function (s) {
        html += '<div class="card"><div class="small muted">' + esc(s.id) + " · " + esc(s.area) + "</div>";
        html += "<h3>" + esc(s.suggestion) + "</h3>";
        html += '<p class="small"><b>Current state:</b> ' + esc(s.current) + "</p>";
        html += '<p class="small"><b>Options:</b></p><ul class="small">';
        s.options.forEach(function (o) { html += "<li>" + esc(o) + "</li>"; });
        html += "</ul>";
        html += '<p class="small"><b>Recommendation:</b> ' + esc(s.recommendation) + "</p>";
        html += "<p>" + statusPill(s.status) + "</p></div>";
      });
      el.innerHTML = html + "</div>";
    },
    sources: function (el, D) {
      var rows = Object.keys(D.sources).map(function (id) {
        var s = D.sources[id];
        return [id, s.title, s.org, s.url, s.method, s.verified_on, s.status];
      });
      var html = tableHTML(["ID", "Title", "Publisher", "Link", "How it was read", "Checked", "Verification status"], rows, {
        html: {
          3: function (v) { return '<a href="' + esc(v) + '" target="_blank" rel="noopener">open ↗</a>'; },
          6: function (v) { return statusPill(v); }
        }
      });
      withFilter(el, html);
    },
    flags: function (el, D) {
      var rows = D.flags.map(function (f) { return [f.id, f.type, f.item, f.action, f.source]; });
      var html = tableHTML(["ID", "Type", "Irregularity / unverified item", "Action for review", "Source"], rows, {
        html: { 4: function (v) { return linkify(v); } }
      });
      withFilter(el, html);
    }
  };

  function counts(D) {
    var map = {
      injury_rows: D.injury_report.rows.length,
      slate_games: D.slate.rows.length,
      rules: D.rules.rows.length,
      questions: D.questions.length,
      open_questions: D.questions.filter(function (q) { return !/^Verified$/.test(q.status); }).length,
      suggestions: D.suggestions.length,
      flags: D.flags.length,
      sources: Object.keys(D.sources).length,
      strategies: 0,
      gates: D.gates.length
    };
    document.querySelectorAll("[data-count]").forEach(function (el) {
      var k = el.getAttribute("data-count");
      if (k in map) el.textContent = map[k];
    });
  }

  fetch("data/data.json", { cache: "no-cache" })
    .then(function (r) { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); })
    .then(function (D) {
      window.NBA3 = D;
      document.querySelectorAll("[data-view]").forEach(function (el) {
        var f = views[el.getAttribute("data-view")];
        if (f) f(el, D);
      });
      document.querySelectorAll("[data-generated]").forEach(function (el) { el.textContent = D.generated_on; });
      counts(D);
    })
    .catch(function (e) {
      document.querySelectorAll("[data-view]").forEach(function (el) {
        el.innerHTML = '<div class="notice">Data could not be loaded (' + esc(e.message) + "). Open the site over http, not file://.</div>";
      });
    });
})();
