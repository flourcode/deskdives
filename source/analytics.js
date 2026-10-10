/*
  Google Analytics 4 for deskdives.com

  1. In Google Analytics, create a GA4 property with a Web data stream for https://deskdives.com
  2. Copy the Measurement ID (it looks like G-XXXXXXXXXX)
  3. Paste it between the quotes below and commit. Amplify redeploys in a couple of minutes.

  Until an ID is filled in, this file does nothing.
*/
(function () {
  var GA_MEASUREMENT_ID = "G-57J108WKB0"; // e.g. "G-ABC123DEF4"

  if (!GA_MEASUREMENT_ID) return;
  if (location.hostname === "localhost" || location.hostname === "127.0.0.1") return;

  var s = document.createElement("script");
  s.async = true;
  s.src = "https://www.googletagmanager.com/gtag/js?id=" + encodeURIComponent(GA_MEASUREMENT_ID);
  document.head.appendChild(s);
  window.dataLayer = window.dataLayer || [];
  window.gtag = function () { window.dataLayer.push(arguments); };
  window.gtag("js", new Date());
  window.gtag("config", GA_MEASUREMENT_ID);

  // Events: video plays on the site, shares, outbound YouTube and affiliate clicks
  document.addEventListener("click", function (e) {
    var t = e.target;
    var yt = t.closest && t.closest("[data-yt]");
    if (yt) { window.gtag("event", "video_play", { video_id: yt.getAttribute("data-yt"), page_path: location.pathname }); return; }
    var sh = t.closest && t.closest("[data-share], [data-pin]");
    if (sh) {
      var native = sh.hasAttribute("data-share") && navigator.share && window.matchMedia("(pointer: coarse)").matches;
      window.gtag("event", "share", { method: sh.hasAttribute("data-pin") ? "pinterest" : (native ? "share_sheet" : "copy_link"),
        content_type: sh.getAttribute("data-kind"), item_id: sh.getAttribute("data-id") });
      return;
    }
    var a = t.closest && t.closest("a[href]");
    if (!a) return;
    if (a.rel && a.rel.indexOf("sponsored") > -1) { window.gtag("event", "affiliate_click", { link_url: a.href, page_path: location.pathname }); return; }
    if (/youtube\.com|youtu\.be/.test(a.href)) window.gtag("event", "youtube_click", { link_url: a.href, page_path: location.pathname });
  });
})();
