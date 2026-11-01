/* Loaded first. If a script or stylesheet fails to load (for example the server answers 429 under a burst) or the app never replaces the loading text, say so with a Retry
 * button instead of leaving a blank page. It touches nothing else and uses no inline script, so a strict Content-Security-Policy is fine. */
(function () {
  var failed = [];
  var main = function () { return document.getElementById("main"); };
  function panel(reason) {
    var m = main(); if (!m || m.querySelector(".bootfail")) return;
    var box = document.createElement("section"); box.className = "bootfail"; box.setAttribute("role", "alert");
    var h = document.createElement("h1"); h.textContent = "This page could not finish loading"; box.appendChild(h);
    var p = document.createElement("p"); p.textContent = reason + " The server may be limiting requests from this network for a moment. Nothing was changed or submitted."; box.appendChild(p);
    if (failed.length) { var l = document.createElement("p"); l.className = "small"; l.textContent = "Could not load: " + failed.slice(0, 6).join(", ") + (failed.length > 6 ? ", and " + (failed.length - 6) + " more" : "") + "."; box.appendChild(l); }
    var b = document.createElement("button"); b.type = "button"; b.className = "btn"; b.textContent = "Try again"; b.addEventListener("click", function () { location.reload(); }); box.appendChild(b);
    m.textContent = ""; m.appendChild(box);
  }
  window.addEventListener("error", function (e) {
    var t = e.target;
    if (t && (t.tagName === "SCRIPT" || t.tagName === "LINK")) { failed.push(((t.src || t.href || "").split("/").slice(-2).join("/")) || "a file"); setTimeout(function () { if (window.DF === undefined || !window.DF.views || !window.DF.ready) panel("Part of the site did not load."); }, 1500); }
  }, true);
  function stillLoading() { var m = main(); return !!(m && m.querySelector(".loading")); }
  [8000, 20000].forEach(function (ms) { setTimeout(function () { if (stillLoading()) panel("The page is taking too long to start."); }, ms); });
  var skip = function () { var s = document.querySelector(".skip"); if (!s) return; s.addEventListener("click", function (e) { e.preventDefault(); var m = main(); if (m) m.focus(); }); };   // the hash is the router: the link must not change it
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", skip); else skip();
})();
