/* study-kit site behaviour. Progressive enhancement: every page is complete without this file. */
(function () {
  "use strict";
  var root = document.documentElement;

  function store(key, value) {
    try { if (value === undefined) return localStorage.getItem(key); localStorage.setItem(key, value); } catch (e) { return null; }
  }

  /* ---------------------------------------------------------- theme */
  function currentTheme() {
    var t = root.getAttribute("data-theme");
    if (t) return t;
    return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }
  document.querySelectorAll(".theme-toggle").forEach(function (btn) {
    function label() { btn.setAttribute("aria-label", "Switch to " + (currentTheme() === "dark" ? "light" : "dark") + " theme"); }
    label();
    btn.addEventListener("click", function () {
      var next = currentTheme() === "dark" ? "light" : "dark";
      root.setAttribute("data-theme", next);
      store("sk-theme", next);
      label();
    });
  });

  /* ---------------------------------------------------------- math */
  function renderMath() {
    if (typeof window.renderMathInElement !== "function") return;
    try {
      window.renderMathInElement(document.body, {
        delimiters: [{ left: "\\[", right: "\\]", display: true }, { left: "\\(", right: "\\)", display: false }],
        throwOnError: false,
        ignoredTags: ["script", "noscript", "style", "textarea", "pre", "code", "option"]
      });
    } catch (e) { /* raw TeX stays readable */ }
  }
  if (document.readyState === "complete") renderMath(); else window.addEventListener("load", renderMath);

  /* ---------------------------------------------------------- variants (home) */
  var chips = document.querySelectorAll("[data-variant]");
  chips.forEach(function (chip) {
    chip.addEventListener("click", function () {
      var ids = chip.getAttribute("data-variant").split(" ").filter(Boolean);
      chips.forEach(function (c) { c.setAttribute("aria-pressed", c === chip ? "true" : "false"); });
      document.querySelectorAll(".chapter-card[data-chapter], .dep-node[data-chapter]").forEach(function (el) {
        var on = ids.indexOf(el.getAttribute("data-chapter")) !== -1;
        el.classList.toggle("is-highlighted", ids.length > 0 && on);
        el.classList.toggle("is-dimmed", ids.length > 0 && !on);
      });
    });
  });

  /* ---------------------------------------------------------- quiz */
  document.querySelectorAll(".question[data-format='mc']").forEach(function (q) {
    var opts = q.querySelectorAll(".opt");
    var sol = q.querySelector("details.solution");
    opts.forEach(function (opt) {
      opt.setAttribute("role", "button");
      opt.setAttribute("tabindex", "0");
      function choose() {
        if (q.classList.contains("is-answered")) return;
        q.classList.add("is-answered");
        opts.forEach(function (o) {
          var right = o.getAttribute("data-correct") === "true";
          if (o === opt || right) {
            o.classList.add(right ? "is-right" : "is-wrong");
            var why = o.querySelector(".opt__why");
            if (why) why.hidden = false;
          }
          o.classList.add("is-disabled");
          o.setAttribute("aria-disabled", "true");
        });
        if (sol) sol.open = true;
      }
      opt.addEventListener("click", choose);
      opt.addEventListener("keydown", function (e) {
        if (e.key === "Enter" || e.key === " ") { e.preventDefault(); choose(); }
      });
    });
  });
  function toggleAll(selector, btn, onLabel, offLabel) {
    var open = btn.getAttribute("aria-pressed") !== "true";
    document.querySelectorAll(selector).forEach(function (d) {
      if (!d.closest("[hidden]")) d.open = open;
    });
    btn.setAttribute("aria-pressed", open ? "true" : "false");
    btn.textContent = open ? offLabel : onLabel;
  }
  document.querySelectorAll("[data-action='toggle-solutions']").forEach(function (btn) {
    btn.addEventListener("click", function () { toggleAll("details.solution", btn, "Show all solutions", "Hide all solutions"); });
  });
  document.querySelectorAll("[data-action='print']").forEach(function (btn) {
    btn.addEventListener("click", function () { window.print(); });
  });

  /* ---------------------------------------------------------- filters (glossary) */
  document.querySelectorAll("input[data-filter]").forEach(function (input) {
    var items = document.querySelectorAll(input.getAttribute("data-filter"));
    var empty = input.parentElement.querySelector(".filter__empty");
    input.addEventListener("input", function () {
      var q = input.value.trim().toLowerCase(), shown = 0;
      items.forEach(function (it) {
        var hit = !q || (it.getAttribute("data-text") || it.textContent.toLowerCase()).indexOf(q) !== -1;
        it.hidden = !hit;
        if (hit) shown++;
      });
      if (empty) empty.hidden = shown !== 0;
    });
  });

  /* ---------------------------------------------------------- cards */
  var cardSelects = document.querySelectorAll("[data-card-filter]");
  if (cardSelects.length) {
    var cards = document.querySelectorAll(".flashcard");
    var count = document.querySelector(".card-filters__count");
    var params = new URLSearchParams(window.location.search);
    cardSelects.forEach(function (s) {
      var v = params.get(s.getAttribute("data-card-filter"));
      if (v && s.querySelector("option[value='" + v.replace(/'/g, "") + "']")) s.value = v;
    });
    var apply = function () {
      var f = {}, shown = 0;
      cardSelects.forEach(function (s) { f[s.getAttribute("data-card-filter")] = s.value; });
      cards.forEach(function (c) {
        var ok = Object.keys(f).every(function (k) { return !f[k] || c.getAttribute("data-" + k) === f[k]; });
        c.hidden = !ok;
        if (ok) shown++;
      });
      if (count) count.textContent = shown + " of " + cards.length + " cards";
    };
    cardSelects.forEach(function (s) { s.addEventListener("change", apply); });
    apply();
  }
  document.querySelectorAll("[data-action='toggle-cards']").forEach(function (btn) {
    btn.addEventListener("click", function () { toggleAll(".flashcard details", btn, "Open all", "Close all"); });
  });

  /* ---------------------------------------------------------- copy BibTeX */
  document.querySelectorAll("[data-copy]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var el = document.querySelector(btn.getAttribute("data-copy"));
      if (!el) return;
      var text = el.textContent, label = btn.textContent;
      var done = function () { btn.textContent = "Copied"; setTimeout(function () { btn.textContent = label; }, 1500); };
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(done, function () { fallback(); });
      } else { fallback(); }
      function fallback() {
        var ta = document.createElement("textarea");
        ta.value = text; ta.setAttribute("readonly", ""); ta.style.position = "absolute"; ta.style.left = "-9999px";
        document.body.appendChild(ta); ta.select();
        try { document.execCommand("copy"); done(); } catch (e) { /* user can select the text */ }
        document.body.removeChild(ta);
      }
    });
  });

  /* ---------------------------------------------------------- print: open everything */
  var opened = [];
  window.addEventListener("beforeprint", function () {
    opened = [];
    document.querySelectorAll("details:not([open])").forEach(function (d) { opened.push(d); d.open = true; });
  });
  window.addEventListener("afterprint", function () { opened.forEach(function (d) { d.open = false; }); });
})();
