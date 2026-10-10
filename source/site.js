// Desk Dives: click-to-play YouTube, share links.
(function () {
  document.addEventListener("click", function (e) {
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
