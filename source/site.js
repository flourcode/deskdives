// Desk Dives: click-to-play YouTube, share links, The desk filters.
(function () {
  // Shorts try YouTube's tall thumbnail first; if it's missing (or a tiny placeholder), use the standard one.
  var fb = function (img) { var u = img.getAttribute("data-fb"); if (u && img.src !== u) { img.removeAttribute("data-fb"); img.src = u; } };
  document.addEventListener("error", function (e) { if (e.target.tagName === "IMG") fb(e.target); }, true);
  document.addEventListener("load", function (e) { var i = e.target; if (i.tagName === "IMG" && i.hasAttribute("data-fb") && i.naturalWidth && i.naturalWidth < 200) fb(i); }, true);
  document.addEventListener("click", function (e) {
    var c = e.target.closest && e.target.closest("[data-filter]");
    if (c) {
      var f = c.getAttribute("data-filter");
      document.querySelectorAll("[data-filter]").forEach(function (b) { b.setAttribute("aria-pressed", b === c ? "true" : "false"); });
      document.querySelectorAll("[data-filterable] > [data-cat]").forEach(function (el) { el.hidden = !(f === "all" || el.getAttribute("data-cat") === f || (f === "sound" && el.hasAttribute("data-sound"))); });
      return;
    }
    var t = e.target.closest && e.target.closest("[data-yt]");
    if (t && t.getAttribute("data-yt")) {
      var id = t.getAttribute("data-yt");
      var f = document.createElement("iframe");
      f.src = "https://www.youtube-nocookie.com/embed/" + encodeURIComponent(id) + "?autoplay=1&rel=0";
      f.title = t.getAttribute("aria-label") || "YouTube video";
      f.allow = "accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share";
      f.allowFullscreen = true;
      t.innerHTML = ""; t.appendChild(f); t.removeAttribute("data-yt");
      return;
    }
    var b = e.target.closest && e.target.closest("[data-share]");
    if (!b) return;
    var url = b.getAttribute("data-url"), title = b.getAttribute("data-title"), label = b.textContent;
    var flash = function (txt) { b.textContent = txt; setTimeout(function () { b.textContent = label; }, 1800); };
    if (navigator.share && window.matchMedia("(pointer: coarse)").matches) {
      navigator.share({ title: title, url: url }).catch(function () {});
    } else if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(url).then(function () { flash("Link copied"); }, function () { window.prompt("Copy this link:", url); });
    } else { window.prompt("Copy this link:", url); }
  });
})();
