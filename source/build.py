#!/usr/bin/env python3
"""Builds deskdives.com into ../site from the files in this folder.

You never need to edit this file. Content lives in:
  site.json            site-wide settings
  watches/<name>/      one folder per watch: watch.json plus photos
  videos.json          YouTube videos
  journal/*.md         journal entries
  about.md             the About page
"""
import json, os, re, shutil, html, hashlib, glob
from datetime import date
from urllib.parse import quote
from PIL import Image, ImageOps, ImageDraw, ImageFilter

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.normpath(os.path.join(ROOT, "..", "site"))
TODAY = date.today().isoformat()
IMG_EXT = (".jpg", ".jpeg", ".png", ".webp")

ABYSS = (6, 18, 28)
ABYSS2 = (11, 29, 43)
LUME = (220, 234, 185)
LUME_DIM = (127, 139, 118)

e = lambda s: html.escape(str(s if s is not None else ""), quote=True)


def fail(msg):
    raise SystemExit("\nBUILD STOPPED: " + msg + "\n(The live site is unchanged.)\n")


def load_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as err:
        fail(f"{os.path.relpath(path, ROOT)} has a typo on line {err.lineno}: {err.msg}. "
             "Check for a missing comma or quote near that line.")


S = load_json(os.path.join(ROOT, "site.json"))
SITE = S["domain"].rstrip("/")
NAME = S["name"]
TAGLINE = S["tagline"]
YT = (S.get("youtube") or "").strip()
EMAIL = (S.get("email") or "").strip()


# ---------- tiny markdown ----------
def front_matter(text):
    meta, body = {}, text
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) == 3:
            for line in parts[1].strip().splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    meta[k.strip()] = v.strip()
            body = parts[2]
    return meta, body.strip()


def inline(t, img_map=None):
    t = e(t)
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<em>\1</em>", t)
    t = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", lambda m: f'<a class="inline" href="{m.group(2)}"'
               + (' target="_blank" rel="noopener"' if m.group(2).startswith("http") else "") + f">{m.group(1)}</a>", t)
    return t


def markdown(body, img_map=None):
    out, para, items = [], [], []
    def flush():
        nonlocal para, items
        if para:
            out.append("<p>" + inline(" ".join(para)) + "</p>"); para = []
        if items:
            out.append("<ul>" + "".join(f"<li>{inline(i)}</li>" for i in items) + "</ul>"); items = []
    for raw in body.splitlines():
        line = raw.strip()
        if not line:
            flush(); continue
        m = re.match(r"!\[([^\]]*)\]\(([^)]+)\)$", line)
        if m:
            flush()
            alt, src = m.group(1), m.group(2)
            im = (img_map or {}).get(src)
            if im:
                out.append(f'<figure class="plate"><div class="win"><img src="{im[0]}" width="{im[1]}" height="{im[2]}" alt="{e(alt)}" loading="lazy" decoding="async"></div>'
                           f'<figcaption><span>{e(alt)}</span></figcaption></figure>')
            continue
        if line.startswith("## "):
            flush(); out.append(f"<h2>{inline(line[3:])}</h2>"); continue
        if line.startswith("# "):
            flush(); out.append(f"<h2>{inline(line[2:])}</h2>"); continue
        if line.startswith(("- ", "* ")):
            if para:
                out.append("<p>" + inline(" ".join(para)) + "</p>"); para = []
            items.append(line[2:]); continue
        para.append(line)
    flush()
    return "\n".join(out)


def plain(md):
    t = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", md)
    t = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", t)
    t = re.sub(r"(?m)^\s*(?:#+|>|-)\s+", "", t)  # headings, quotes, list bullets at line starts
    t = re.sub(r"[*`]|(?<!\w)_|_(?!\w)", "", t)  # bold/italic/code marks; keeps hyphens and snake_case
    return " ".join(t.split())


# ---------- images ----------
def fhash(path):
    with open(path, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()[:8]


def save(im, rel, **kw):
    path = os.path.join(OUT, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if rel.endswith(".jpg"):
        im = im.convert("RGB")
        kw = {"quality": 84, "optimize": True, "progressive": True, **kw}
    im.save(path, **kw)  # saved without EXIF, so no GPS or camera data is published
    return f"/{rel}?v={fhash(path)}"


def open_img(path):
    try:
        return ImageOps.exif_transpose(Image.open(path)).convert("RGB")
    except Exception:
        fail(f"{os.path.relpath(path, ROOT)} could not be opened as an image. Re-export it as a JPG.")


def sized(im, rel_base, sizes):
    """Save several widths; return list of (url, width) and the largest (url, w, h)."""
    out, big = [], None
    for s, suffix in sizes:
        if s > max(im.size) and suffix:
            continue
        c = im.copy(); c.thumbnail((s, s), Image.LANCZOS)
        url = save(c, f"{rel_base}{suffix}.jpg")
        out.append((url, c.size[0]))
        big = (url, c.size[0], c.size[1])
    return out, big


def og_card(im, rel):
    """1200x630 share image: the photo in a logbook plate on abyss blue."""
    card = Image.new("RGB", (1200, 630), ABYSS)
    d = ImageDraw.Draw(card)
    box_w, box_h = 1200 - 160, 630 - 110
    ph = im.copy(); ph.thumbnail((box_w - 28, box_h - 28), Image.LANCZOS)
    fw, fh = ph.size[0] + 28, ph.size[1] + 28
    x0, y0 = (1200 - fw) // 2, (630 - fh) // 2
    d.rectangle([x0, y0, x0 + fw, y0 + fh], fill=ABYSS2, outline=LUME_DIM, width=2)
    t = 22
    d.line([x0, y0, x0 + t, y0], fill=LUME, width=4); d.line([x0, y0, x0, y0 + t], fill=LUME, width=4)
    d.line([x0 + fw - t, y0 + fh, x0 + fw, y0 + fh], fill=LUME, width=4); d.line([x0 + fw, y0 + fh - t, x0 + fw, y0 + fh], fill=LUME, width=4)
    card.paste(ph, (x0 + 14, y0 + 14))
    return save(card, rel, quality=86)


def bezel_icon(size):
    """Site icon: a dive bezel with the lume pip at 12, drawn on abyss."""
    k = 4; S_ = size * k
    im = Image.new("RGB", (S_, S_), ABYSS)
    d = ImageDraw.Draw(im)
    pad = int(S_ * 0.12); w = max(2, int(S_ * 0.085))
    d.ellipse([pad, pad, S_ - pad, S_ - pad], outline=LUME, width=w)
    cx = S_ / 2; top = pad + w * 1.6
    tri = int(S_ * 0.13)
    d.polygon([(cx - tri, top), (cx + tri, top), (cx, top + tri * 1.5)], fill=LUME)
    if size >= 64:
        for a in range(0, 360, 30):
            import math
            if a == 0:
                continue
            r1, r2 = S_ / 2 - pad - w * 1.4, S_ / 2 - pad - w * 2.6
            x1 = cx + r1 * math.sin(math.radians(a)); y1 = cx - r1 * math.cos(math.radians(a))
            x2 = cx + r2 * math.sin(math.radians(a)); y2 = cx - r2 * math.cos(math.radians(a))
            d.line([x1, y1, x2, y2], fill=LUME_DIM, width=max(2, w // 3))
    return im.resize((size, size), Image.LANCZOS)


# ---------- watches ----------
def load_watches():
    ws = []
    for folder in sorted(glob.glob(os.path.join(ROOT, "watches", "*"))):
        slug = os.path.basename(folder)
        if not os.path.isdir(folder) or slug.startswith(("_", ".")):
            continue
        jp = os.path.join(folder, "watch.json")
        if not os.path.exists(jp):
            fail(f"watches/{slug} has no watch.json. Copy one from watches/_template.")
        w = load_json(jp)
        if w.get("draft"):
            continue
        if not re.fullmatch(r"[a-z0-9-]+", slug):
            fail(f"Folder name watches/{slug} should be lowercase letters, numbers and dashes only (e.g. citizen-ny0040).")
        w["slug"] = slug
        w["folder"] = folder
        w["url"] = f"/watches/{slug}/"
        w["title"] = f"{w.get('brand','')} {w.get('model','')}".strip()
        for k, v in (("take", []), ("likes", []), ("annoyances", []), ("key_numbers", []), ("specs", {}), ("captions", {})):
            w.setdefault(k, v)
        imgs = sorted(f for f in os.listdir(folder) if f.lower().endswith(IMG_EXT))
        main = next((f for f in imgs if os.path.splitext(f)[0].lower() == "main"), None)
        figs = [f for f in imgs if f.lower().startswith("figure")]
        rest = [f for f in imgs if f != main and f not in figs]
        if not main and rest:
            main, rest = rest[0], rest[1:]
        w["main_file"], w["gallery_files"], w["figure_files"] = main, rest, figs
        missing = [x for x, ok in (("a photo", main), ("a reference", (w.get("ref") or "").strip() not in ("", "TBD"))) if not ok]
        if missing:
            print(f"Hidden for now: watches/{slug} needs {' and '.join(missing)} before it shows on the site.")
            continue
        ws.append(w)
    ws.sort(key=lambda w: (w.get("order", 999), w["slug"]))
    for i, w in enumerate(ws):
        w["no"] = f"{i + 1:02d}"
    return ws


def process_watch_images(w):
    rel = f"images/watches/{w['slug']}"
    w["img"] = None
    if w["main_file"]:
        im = open_img(os.path.join(w["folder"], w["main_file"]))
        w["srcset"], (w["img"], w["iw"], w["ih"]) = sized(im, f"{rel}/{w['slug']}-{w['brand'].lower()}-watch", [(800, "-800"), (1600, ""), (2400, "-2400")])
        w["img_plain"] = f"/{rel}/{w['slug']}-{w['brand'].lower()}-watch.jpg"
        w["og"] = og_card(im, f"images/og/{w['slug']}.jpg")
    w["gallery"] = []
    for f in w["gallery_files"]:
        im = open_img(os.path.join(w["folder"], f))
        base = os.path.splitext(f)[0]
        t = im.copy(); t.thumbnail((900, 900), Image.LANCZOS)
        thumb = save(t, f"{rel}/{base}-900.jpg")
        big = im.copy(); big.thumbnail((2400, 2400), Image.LANCZOS)
        full = save(big, f"{rel}/{base}.jpg")
        cap = w["captions"].get(f) or w["captions"].get(base) or base.replace("-", " ").replace("_", " ").capitalize()
        w["gallery"].append(dict(thumb=thumb, full=full, w=t.size[0], h=t.size[1], caption=cap))
    w["figures"] = []
    for f in w["figure_files"]:
        im = open_img(os.path.join(w["folder"], f))
        big = im.copy(); big.thumbnail((1800, 1800), Image.LANCZOS)
        url = save(big, f"{rel}/{os.path.splitext(f)[0]}.jpg")
        w["figures"].append(dict(url=url, w=big.size[0], h=big.size[1], caption=w["captions"].get(f, "Watercolor, " + S.get("author", ""))))


# ---------- journal ----------
def load_journal():
    posts, img_map = [], {}
    idir = os.path.join(ROOT, "journal", "images")
    if os.path.isdir(idir):
        for f in sorted(os.listdir(idir)):
            if f.lower().endswith(IMG_EXT):
                im = open_img(os.path.join(idir, f)); im.thumbnail((1800, 1800), Image.LANCZOS)
                img_map[f] = (save(im, f"images/journal/{os.path.splitext(f)[0]}.jpg"), im.size[0], im.size[1])
    for path in sorted(glob.glob(os.path.join(ROOT, "journal", "*.md"))):
        name = os.path.basename(path)
        if name.startswith("_"):
            continue
        meta, body = front_matter(open(path, encoding="utf-8").read())
        if meta.get("draft", "").lower() in ("true", "yes"):
            continue
        slug = re.sub(r"[^a-z0-9-]+", "-", os.path.splitext(name)[0].lower()).strip("-")
        d = meta.get("date", "")
        try:
            dt = date.fromisoformat(d[:10]) if len(d) >= 10 else date.fromisoformat(d + "-01")
        except ValueError:
            fail(f"journal/{name}: the date should look like 2026-10-10.")
        words = len(plain(body).split())
        posts.append(dict(slug=slug, url=f"/journal/{slug}/", title=meta.get("title", slug), date=dt,
                          section=meta.get("section", "Journal"), summary=meta.get("summary", ""),
                          html=markdown(body, img_map), text=plain(body), minutes=max(1, round(words / 230))))
    posts.sort(key=lambda p: p["date"], reverse=True)
    return posts


# ---------- page shell ----------
ASSET_V = {n: fhash(os.path.join(ROOT, n)) for n in ("site.css", "site.js", "analytics.js")}


def ld(*nodes):
    return '<script type="application/ld+json">' + json.dumps({"@context": "https://schema.org", "@graph": [n for n in nodes if n]},
        ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/") + "</script>"


def crumbs(items):
    return {"@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": i + 1, "name": n, "item": f"{SITE}{u}"} for i, (n, u) in enumerate(items)]}


PERSON = {"@type": "Person", "@id": f"{SITE}/#author", "name": S.get("author", ""), "url": f"{SITE}/about/",
          **({"sameAs": [YT]} if YT else {})}
WEBSITE = {"@type": "WebSite", "@id": f"{SITE}/#website", "url": f"{SITE}/", "name": NAME, "description": TAGLINE,
           "inLanguage": "en-US", "publisher": {"@id": f"{SITE}/#author"}}


def page(path, title, description, body, nav="", og=None, og_alt="", og_type="website", schema=""):
    url = f"{SITE}{path}"
    og = og or IMG["og-site"]
    cur = ' aria-current="page"'
    link = lambda key, href, label: f'<a href="{href}"{cur if nav == key else ""}>{label}</a>'
    yt_foot = f' · <a href="{e(YT)}" target="_blank" rel="me noopener">{e(S.get("youtube_label","YouTube"))}</a>' if YT else ""
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{e(title)}</title>
<meta name="description" content="{e(description)}">
<link rel="canonical" href="{url}">
<meta name="robots" content="index, follow, max-image-preview:large">
<meta name="author" content="{e(S.get('author',''))}">
<meta property="og:site_name" content="{e(NAME)}">
<meta property="og:type" content="{og_type}">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(description)}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{SITE}{og}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="{e(og_alt or NAME)}">
<meta property="og:locale" content="en_US">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{e(title)}">
<meta name="twitter:description" content="{e(description)}">
<meta name="twitter:image" content="{SITE}{og}">
<meta name="theme-color" content="#06121c">
<link rel="icon" href="/favicon.ico" sizes="48x48">
<link rel="icon" type="image/svg+xml" href="/favicon.svg">
<link rel="icon" type="image/png" sizes="32x32" href="/favicon-32.png">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<link rel="manifest" href="/site.webmanifest">
<link rel="alternate" type="text/plain" title="LLM summary" href="/llms.txt">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&family=Newsreader:ital,opsz,wght@0,6..72,400;0,6..72,500;1,6..72,400;1,6..72,500&family=IBM+Plex+Mono:wght@400;500;600&display=swap">
<link rel="stylesheet" href="/assets/site.css?v={ASSET_V['site.css']}">
<script src="/assets/analytics.js?v={ASSET_V['analytics.js']}" defer></script>
<script src="/assets/site.js?v={ASSET_V['site.js']}" defer></script>
{schema}
</head>
<body>
<a class="skip" href="#main">Skip to content</a>
<div class="wrap">
  <header class="site">
    <div class="bar">
      <a class="wordmark" href="/">{e(NAME.upper())}</a>
      <nav class="primary" aria-label="Primary">
        {link("watches", "/watches/", "Watches")}
        {link("videos", "/videos/", "Videos")}
        {link("wallpapers", "/wallpapers/", "Wallpapers") if WALLS else ""}
        {link("journal", "/journal/", "Journal") if POSTS else ""}
        {link("about", "/about/", "About")}
      </nav>
    </div>
    <div class="dateline"><span>{len(WATCHES)} watch{"" if len(WATCHES) == 1 else "es"}{(" · " + e(S["dateline"])) if S.get("dateline") else ""}</span></div>
  </header>
</div>
<main id="main" class="clip">
{body}
</main>
<div class="wrap">
  <footer class="site"><div class="bar"><span class="wordmark small">{e(NAME.upper())}</span><span>{e(TAGLINE)}{yt_foot} · © {date.today().year} {e(S.get('author',''))}</span></div></footer>
</div>
</body>
</html>
"""


def write(path, content):
    full = os.path.join(OUT, path.lstrip("/"), "index.html") if path.endswith("/") else os.path.join(OUT, path.lstrip("/"))
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as f:
        f.write(content)


# ---------- components ----------
def plate(w, eager=False, sizes="(max-width: 900px) 46vw, 24vw", caption=True):
    if w.get("img"):
        srcset = ", ".join(f"{u} {x}w" for u, x in w["srcset"])
        load = 'fetchpriority="high"' if eager else 'loading="lazy"'
        img = (f'<img src="{w["img"]}" srcset="{srcset}" sizes="{sizes}" width="{w["iw"]}" height="{w["ih"]}" '
               f'alt="{e(w["title"])} {e(w.get("ref","")) if w.get("ref") not in (None,"","TBD") else ""} watch" {load} decoding="async">')
        win = f'<div class="win">{img}</div>'
        cls = "plate"
    else:
        win = '<div class="win"><span class="ring"></span></div>'
        cls = "plate empty"
    cap = (f'<figcaption><span><b>Plate {w["no"]}</b> · {e(w["title"])}</span><span>{"" if w.get("img") else "Photo to come"}</span></figcaption>'
           if caption else "")
    return f'<figure class="{cls}">{win}{cap}</figure>'


def rank(w):
    r = str(w.get("wrist_rank") or "").strip()
    return f"P{r}" if r else ""


def ref_text(w):
    r = w.get("ref") or "TBD"
    return f"REF {r}"


def watch_card(w):
    rk = rank(w)
    rk_html = f"<b>{rk} · WRIST TIME</b>" if rk == "P1" else (f"<span>{rk}</span>" if rk else "")
    return f"""        <a class="watch-card" href="{w['url']}">
          {plate(w, caption=False)}
          <div class="meta"><span class="no"><span>NO. {w['no']}</span>{rk_html}</span><span class="name">{e(w['title'])}</span><span class="ref">{e(ref_text(w))}</span><span class="line">{e(w.get('line',''))}</span></div>
        </a>"""


YT_ID = re.compile(r"(?:youtu\.be/|youtube\.com/(?:watch\?(?:.*&)?v=|shorts/|embed/|live/))([A-Za-z0-9_-]{11})")


def video_id(v):
    """Accepts a bare id or any YouTube link (watch, youtu.be, shorts)."""
    raw = (v.get("id") or v.get("url") or "").strip()
    m = YT_ID.search(raw)
    if m:
        if "/shorts/" in raw and "short" not in v:
            v["short"] = True
        return m.group(1)
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", raw):
        return raw
    if raw:
        fail(f"videos.json: '{raw}' doesn't look like a YouTube link or video id (video '{v.get('title','')}').")
    return ""


def video_card(v, big=False):
    short = bool(v.get("short"))
    big = big and not short
    thumb = v.get("poster") or f"https://i.ytimg.com/vi/{e(v['id'])}/hqdefault.jpg"
    w_titles = ", ".join(e(W_BY[s]["title"]) for s in v.get("watches", []) if s in W_BY)
    cls = "vid" + (" big" if big else "") + (" short" if short else "")
    link = f"https://www.youtube.com/shorts/{e(v['id'])}" if short else f"https://www.youtube.com/watch?v={e(v['id'])}"
    tc = f'<span class="tc">{e(v.get("length",""))}</span>' if v.get("length") else ""
    tag = '<span class="tag">Short</span>' if short else ""
    return f"""<div class="{cls}">
          <button type="button" class="thumb" data-yt="{e(v['id'])}" aria-label="Play video: {e(v['title'])}"><img src="{thumb}" alt="" loading="lazy" decoding="async"><span class="play"></span>{tag}{tc}</button>
          <h3><a href="{link}" target="_blank" rel="noopener">{e(v['title'])}</a></h3>
          <p>{e(v.get('summary',''))}{(' · Features ' + w_titles) if w_titles else ''}</p>
        </div>"""


def share_links(url, title, media, kind, item):
    pin = ("https://www.pinterest.com/pin/create/button/?url=" + quote(url, safe="") +
           "&media=" + quote(media, safe="") + "&description=" + quote(title, safe=""))
    data = f'data-kind="{kind}" data-id="{e(item)}"'
    return (f'<div class="share"><button type="button" data-share data-url="{e(url)}" data-title="{e(title)}" {data}>Share</button>'
            f'<a href="{e(pin)}" target="_blank" rel="noopener" data-pin {data}>Pin</a></div>')


def money(n):
    return f"${n:,.0f}"


# ---------- pages ----------
def build_home():
    f = W_BY.get(S.get("featured")) or (WATCHES[0] if WATCHES else None)
    hero_plate = ""
    if f:
        hero_plate = f'<a class="hero-link" href="{f["url"]}">{plate(f, eager=True, sizes="(max-width: 900px) 92vw, 46vw")}</a>'
    cards = "\n".join(watch_card(w) for w in WATCHES[:8])
    # modules
    if POSTS:
        jl = "".join(f'<li><span class="label">{e(p["section"])}</span><a href="{p["url"]}">{e(p["title"])}</a></li>' for p in POSTS[:4])
        journal_mod = f'<ol class="numbered">{jl}</ol>'
    else:
        journal_mod = '<p class="empty-note">The first entry is on its way.</p>'
    if VIDEOS:
        video_mod = "\n".join(video_card(v) for v in VIDEOS[:1])
    else:
        video_mod = '<div class="vid"><div class="thumb static"><span class="play"></span></div><p class="empty-note">The first new video is coming soon.</p></div>'
    journal_col = ""
    if POSTS:
        journal_col = f"""<div class="col-a"><span class="label">Only on {e(NAME)}</span><h2 class="mod-head">From the journal</h2>
        <p class="mod-sub">Occasional writing, mostly about watches I already own.</p>{journal_mod}
        <a class="more-link" href="/journal/">All entries →</a></div>"""
    ow = W_BY.get(S.get("on_wrist"))
    spot = ""
    if ow:
        disc = f'<img src="{ow["img"]}" alt="">' if ow.get("img") else ""
        note = S.get("on_wrist_note") or ow.get("line", "")
        spot = f"""<div class="spotlight"><span class="label">On the wrist this week</span>
          <a class="who" href="{ow['url']}"><span class="disc">{disc}</span><span><b>{e(ow['title'])}</b><i>No. {ow['no']}{(' · ' + rank(ow) + ' this year') if rank(ow) else ''}</i></span></a>
          <p>{e(note)}</p></div>"""
    sub = ""
    if YT:
        sub = f"""<div class="box"><span class="label">Subscribe</span><h2 class="mod-head">{e(S.get('subscribe_title',''))}</h2>
          <p>{e(S.get('subscribe_text',''))}</p><a class="cta" href="{e(YT)}" target="_blank" rel="noopener">Subscribe on YouTube →</a></div>"""
    body = f"""  <div class="wrap">
    <section class="grid hero">
      <div class="masthead">
        <h1 class="glow">{e(NAME)}</h1>
        <p class="standfirst">{('<i>' + e(S['kicker']) + '</i> ') if S.get('kicker') else ''}{e(TAGLINE)}</p>
      </div>
      {hero_plate}
    </section>
    <section class="sect" aria-labelledby="col-h">
      <div class="sect-head"><h2 id="col-h" class="label">The collection · {len(WATCHES):02d}</h2><a href="/watches/">All watches →</a></div>
      <div class="collection">
{cards}
      </div>
    </section>
    <section class="grid modules{'' if POSTS else ' two'}" aria-label="More">
      {journal_col}
      <div class="col-b"><span class="label">On YouTube</span><h2 class="mod-head">{'Latest video' if len(VIDEOS) <= 1 else 'Latest videos'}</h2>
        <p class="mod-sub">Wrist shots, lume tests and honest counts.</p>{video_mod}
        <a class="more-link" href="/videos/">All videos →</a></div>
      <div class="col-c">{spot}{sub}</div>
    </section>
  </div>"""
    items = {"@type": "ItemList", "name": "The collection", "itemListElement": [
        {"@type": "ListItem", "position": i + 1, "url": f"{SITE}{w['url']}", "name": w["title"]} for i, w in enumerate(WATCHES)]}
    write("/", page("/", f"{NAME} · Seiko Dive Watches, Specs and Honest Notes",
                    S.get("description") or TAGLINE,
                    body, schema=ld(WEBSITE, PERSON, items), og_alt=f"{NAME} dive watch collection"))


def build_watches_index():
    cards = "\n".join(watch_card(w) for w in WATCHES)
    body = f"""  <div class="wrap">
    <section class="page-head"><span class="label">The collection</span><h1 class="glow">Watches</h1>
      <p class="standfirst">{len(WATCHES)} watches, numbered in the order they arrived. Specs, photos and honest notes on each.</p></section>
    <div class="collection">
{cards}
    </div>
  </div>"""
    items = {"@type": "ItemList", "name": "Watches", "itemListElement": [
        {"@type": "ListItem", "position": i + 1, "url": f"{SITE}{w['url']}", "name": w["title"]} for i, w in enumerate(WATCHES)]}
    write("/watches/", page("/watches/", f"Watches · The Collection · {NAME}",
                            f"The {NAME} collection: {len(WATCHES)} watches, mostly Seiko Prospex divers, with specs, photos and honest notes.",
                            body, nav="watches", schema=ld({"@type": "CollectionPage", "url": f"{SITE}/watches/", "name": "Watches", "mainEntity": items},
                                                           crumbs([("Home", "/"), ("Watches", "/watches/")]))))


def build_watch(w, i):
    prev, nxt = (WATCHES[i - 1] if i else None), (WATCHES[i + 1] if i + 1 < len(WATCHES) else None)
    kn = "".join(f'<div><b>{e(v)}</b><span class="label">{e(l)}</span></div>' for v, l in w["key_numbers"])
    timing = f'<section class="timing" style="--n:{len(w["key_numbers"])}" aria-label="Key numbers">{kn}</section>' if w["key_numbers"] else ""
    blank = lambda v: v is None or str(v).strip() in ("", "TBD")
    rows = [("Ref", w["ref"])] + [(k, v) for k, v in w["specs"].items() if not blank(v)]
    if not blank(w.get("acquired")):
        rows.append(("Acquired", w["acquired"]))
    if w.get("deepest_dive"):
        rows.append(("Deepest dive", w["deepest_dive"]))
    if rank(w):
        rows.append(("Wrist time", rank(w) + " this year"))
    hot = {"Lume", "Wrist time"}
    hot_attr = ' class="hot"'
    spec_rows = "".join(f'<tr><th scope="row">{e(k)}</th><td{hot_attr if k in hot else ""}>{e(v)}</td></tr>' for k, v in rows)
    verdict = ""
    if w.get("verdict"):
        vnote = "<p>" + e(w["verdict_note"]) + "</p>" if w.get("verdict_note") else ""
        verdict = f'<div class="verdict"><h3 class="label">Would I buy it again?</h3><b class="glow">{e(w["verdict"])}</b>{vnote}</div>'
    share = share_links(SITE + w["url"], f"{w['title']} · {NAME}", SITE + (w.get("img_plain") or IMG["og-site"]), "watch", w["slug"])
    take = "".join(f"<p>{inline(p)}</p>" for p in w["take"])
    lists = ""
    if w["likes"] or w["annoyances"]:
        li = lambda xs: "".join(f"<li>{inline(x)}</li>" for x in xs)
        likes = '<div><h3 class="label">What I like</h3><ul>' + li(w["likes"]) + '</ul></div>' if w["likes"] else ""
        annoy = '<div class="no"><h3 class="label">What annoys me</h3><ul>' + li(w["annoyances"]) + '</ul></div>' if w["annoyances"] else ""
        lists = f'<div class="lists">{likes}{annoy}</div>'
    math = ""
    b = S.get("benchmark") or {}
    if isinstance(w.get("paid"), (int, float)) and b.get("price"):
        left = b["price"] - w["paid"]
        math = f"""<aside class="col-x"><div class="mathbox"><span class="label">The math</span><h2 class="mod-head">Sub money vs. Seiko money</h2>
          <dl><div><dt>{e(b.get('name',''))}</dt><dd>{money(b['price'])}</dd></div><div><dt>What I paid</dt><dd>{money(w['paid'])}</dd></div>
          <div class="res"><dt>Left over</dt><dd>{money(left)}</dd></div></dl>
          {f"<p>{e(w['math_quip'])}</p>" if w.get('math_quip') else ''}<small>{e(b.get('note',''))}</small></div></aside>"""
    take_sect = ""
    if take or lists or verdict or math:
        head = "Why I bought it" if take else ("Would I buy it again?" if verdict and not lists else "Notes")
        verdict_html = verdict if (take or lists) else verdict.replace('<h3 class="label">Would I buy it again?</h3>', "")
        take_sect = f"""<section class="grid take">
      <div class="col-l"><h2>{head}</h2></div>
      <div class="col-r body">{take}{lists}{verdict_html}</div>
      {math}
    </section>"""
    figs = "".join(f"""<section class="grid fig"><div class="txt"><span class="label">Fig.</span><p><i>From the sketchbook:</i> {e(f['caption'])}</p></div>
      <figure class="art"><img src="{f['url']}" width="{f['w']}" height="{f['h']}" alt="Watercolor of the {e(w['title'])}" loading="lazy" decoding="async"></figure></section>""" for f in w["figures"])
    gal = "".join(f"""<figure class="plate"><a class="win" href="{g['full']}"><img src="{g['thumb']}" width="{g['w']}" height="{g['h']}" alt="{e(w['title'])}: {e(g['caption'])}" loading="lazy" decoding="async"></a>
          <figcaption><span><b>Plate {w['no']}.{j + 2}</b> · {e(g['caption'])}</span></figcaption></figure>""" for j, g in enumerate(w["gallery"]))
    vids = [v for v in VIDEOS if w["slug"] in v.get("watches", [])]
    vid_html = "".join(video_card(v) for v in vids)
    more = ""
    if gal or vid_html:
        more = f"""<section class="sect"><div class="sect-head"><h2 class="label">More plates and videos</h2></div>
      <div class="gallery">{gal}{vid_html}</div></section>"""
    find = ""
    if w.get("affiliate_url"):
        find = f'<div class="find"><a href="{e(w["affiliate_url"])}" target="_blank" rel="sponsored noopener">{e(w.get("affiliate_label") or "Where to find one")} →</a><span>If you buy through this link, I may earn a small commission.</span></div>'
    pl = f'<a href="{prev["url"]}"><span class="label">← No. {prev["no"]}</span>{e(prev["title"])}</a>' if prev else '<a href="/watches/"><span class="label">← Collection</span>All watches</a>'
    nl = f'<a class="next" href="{nxt["url"]}"><span class="label">No. {nxt["no"]} →</span>{e(nxt["title"])}</a>' if nxt else '<a class="next" href="/watches/"><span class="label">Collection →</span>All watches</a>'
    sub = " · ".join(x for x in [w.get("brand"), w.get("collection"), w.get("type")] if x)
    longest = max((len(x) for x in w["model"].split()), default=0)
    h1_cls = " xlong" if longest > 11 else (" long" if longest > 8 else "")
    body = f"""  <div class="wrap">
    <section class="w-head">
      <span class="label">No. {w['no']} · {e(sub)}</span>
      <h1 class="glow{h1_cls}">{e(w['model'])}</h1>
      <p class="nick">{f"<i>{e(w.get('nickname'))}:</i> " if w.get('nickname') else ''}{e(w.get('line',''))}</p>
    </section>
    {timing}
    <section class="grid w-main">
      {plate(w, eager=True, sizes="(max-width: 900px) 92vw, 55vw")}
      <aside class="w-side">
        <table class="specs"><caption class="label">Specifications</caption>{spec_rows}</table>
        {share}
      </aside>
    </section>
    {take_sect}
    {figs}
    {more}
    {find}
    <nav class="pager" aria-label="More watches">{pl}{nl}</nav>
  </div>"""
    desc = (w["take"][0] if w["take"] else w.get("line", "")) or f"The {w['title']} in the {NAME} collection."
    desc = f"{w['title']}{(' (' + w['ref'] + ')') if w.get('ref') not in (None, '', 'TBD') else ''}: {plain(desc)}"[:300]
    product = {"@type": "Product", "@id": f"{SITE}{w['url']}#watch", "name": w["title"], "brand": {"@type": "Brand", "name": w.get("brand", "")},
               "category": "Dive watch" if "diver" in (w.get("type") or "").lower() else "Wristwatch", "url": f"{SITE}{w['url']}"}
    if w.get("ref") not in (None, "", "TBD"):
        product["mpn"] = w["ref"]; product["model"] = w["ref"]
    if w.get("img"):
        product["image"] = SITE + w["img_plain"]
    if w["take"]:
        product["review"] = {"@type": "Review", "author": {"@id": f"{SITE}/#author"}, "reviewBody": plain(" ".join(w["take"]))}
        schema = ld(product, crumbs([("Home", "/"), ("Watches", "/watches/"), (w["title"], w["url"])]))
    else:  # product markup without a review gets flagged by Google, so only breadcrumbs until the take is written
        schema = ld(crumbs([("Home", "/"), ("Watches", "/watches/"), (w["title"], w["url"])]))
    write(w["url"], page(w["url"], f"{w['title']}{(' ' + w['ref']) if w.get('ref') not in (None,'','TBD') else ''} · Specs, Photos and Honest Notes · {NAME}",
                         desc, body, nav="watches", og=w.get("og"), og_alt=f"{w['title']} dive watch", og_type="article",
                         schema=schema))


def build_videos():
    if VIDEOS:
        grid = "\n".join(video_card(v, big=(i == 0)) for i, v in enumerate(VIDEOS))
    else:
        grid = '<div class="vid"><div class="thumb static"><span class="play"></span></div><p class="empty-note">The first new video is coming soon.</p></div>'
    yt = f'<p class="standfirst">New videos on <a class="inline" href="{e(YT)}" target="_blank" rel="noopener">YouTube</a>. Every video is listed here with the watches it features.</p>' if YT else '<p class="standfirst">Wrist shots, lume tests and honest counts. The channel is coming back.</p>'
    body = f"""  <div class="wrap">
    <section class="page-head"><span class="label">On YouTube</span><h1 class="glow">Videos</h1>{yt}</section>
    <div class="video-grid">{grid}</div>
  </div>"""
    nodes = [{"@type": "VideoObject", "name": v["title"], "description": v.get("summary") or v["title"],
              "thumbnailUrl": (SITE + v["poster"]) if v.get("poster") else f"https://i.ytimg.com/vi/{v['id']}/hqdefault.jpg", "uploadDate": v.get("date") or TODAY,
              "embedUrl": f"https://www.youtube-nocookie.com/embed/{v['id']}", "contentUrl": (f"https://www.youtube.com/shorts/{v['id']}" if v.get("short") else f"https://www.youtube.com/watch?v={v['id']}")} for v in VIDEOS]
    write("/videos/", page("/videos/", f"Videos · Dive Watches on YouTube · {NAME}", f"{NAME} videos: wrist shots, lume tests and honest notes on Seiko and Citizen dive watches.",
                           body, nav="videos", schema=ld(*nodes, crumbs([("Home", "/"), ("Videos", "/videos/")]))))


def build_journal():
    if POSTS:
        rows = "".join(f'<li><a href="{p["url"]}"><span class="d">{p["date"].strftime("%b %Y").upper()}</span><span class="t">{e(p["title"])}<small>{e(p["summary"])}</small></span><span class="r">{p["minutes"]} MIN</span></a></li>' for p in POSTS)
        lst = f'<ol class="journal">{rows}</ol>'
    else:
        lst = '<p class="empty-note">The first entry is on its way.</p>'
    body = f"""  <div class="wrap">
    <section class="page-head"><span class="label">Only on {e(NAME)}</span><h1 class="glow">Journal</h1>
      <p class="standfirst">Occasional writing. Straps, old catalogs, and why I keep buying the same watch.</p></section>
    {lst}
  </div>"""
    write("/journal/", page("/journal/", f"Journal · {NAME}", f"Occasional writing about dive watches from {NAME}.", body, nav="journal",
                            schema=ld(crumbs([("Home", "/"), ("Journal", "/journal/")]))))
    for i, p in enumerate(POSTS):
        newer, older = (POSTS[i - 1] if i else None), (POSTS[i + 1] if i + 1 < len(POSTS) else None)
        pl = f'<a href="{older["url"]}"><span class="label">← Older</span>{e(older["title"])}</a>' if older else '<a href="/journal/"><span class="label">← Journal</span>All entries</a>'
        nl = f'<a class="next" href="{newer["url"]}"><span class="label">Newer →</span>{e(newer["title"])}</a>' if newer else '<a class="next" href="/journal/"><span class="label">Journal →</span>All entries</a>'
        body = f"""  <div class="wrap">
    <article class="post">
      <header><span class="label">{e(p['section'])} · {p['date'].strftime('%B %Y')} · {p['minutes']} min</span><h1 class="glow">{e(p['title'])}</h1>
        {f'<p class="standfirst">{e(p["summary"])}</p>' if p['summary'] else ''}</header>
      <div class="post-body">{p['html']}</div>
      {share_links(SITE + p['url'], p['title'] + ' · ' + NAME, SITE + IMG['og-site'], 'journal', p['slug'])}
    </article>
    <nav class="pager" aria-label="More entries">{pl}{nl}</nav>
  </div>"""
        art = {"@type": "BlogPosting", "headline": p["title"], "datePublished": p["date"].isoformat(), "author": {"@id": f"{SITE}/#author"},
               "url": f"{SITE}{p['url']}", "description": p["summary"] or p["text"][:200], "isPartOf": {"@id": f"{SITE}/#website"}}
        write(p["url"], page(p["url"], f"{p['title']} · {NAME}", p["summary"] or p["text"][:160], body, nav="journal", og_type="article",
                             schema=ld(art, crumbs([("Home", "/"), ("Journal", "/journal/"), (p["title"], p["url"])]))))


def build_about():
    meta, body_md = front_matter(open(os.path.join(ROOT, "about.md"), encoding="utf-8").read())
    n = len(WATCHES)
    words = "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty".split()
    count_word = words[n] if n < len(words) else str(n)
    for k in ("lead", "title"):
        if meta.get(k):
            meta[k] = meta[k].replace("{count}", count_word).replace("{number}", str(n))
    body_md = body_md.replace("{count}", count_word).replace("{number}", str(n))
    log_rows = [("Watches", str(n)), ("Most worn", meta.get("most_worn")), ("Grail", meta.get("grail"))]
    if YT:
        log_rows.append(("YouTube", f'<a class="inline" href="{e(YT)}" target="_blank" rel="me noopener">{e(YT.replace("https://www.youtube.com/", ""))}</a>'))
    if EMAIL:
        log_rows.append(("Email", e(EMAIL)))
    log = "".join(f"<div><dt>{k}</dt><dd>{v if k in ('YouTube',) else e(v)}</dd></div>" for k, v in log_rows if v and str(v).strip() not in ("", "TBD"))
    art = ""
    if IMG.get("about-art"):
        u, aw, ah = IMG["about-art"]
        art = f'<figure class="art"><img src="{u}" width="{aw}" height="{ah}" alt="Watercolor by {e(S.get("author",""))} of a dive watch" loading="lazy" decoding="async"><figcaption class="label">Fig. 1 · Watercolor, {e(S.get("author",""))}</figcaption></figure>'
    body = f"""  <div class="wrap">
    <section class="grid about">
      <div class="copy">
        <span class="label">About</span>
        <h1 class="glow">{e(meta.get('title','About'))}</h1>
        {f"<p class='lead'>{inline(meta['lead'])}</p>" if meta.get('lead') else ''}
        {markdown(body_md)}
        <dl class="logbook">{log}</dl>
      </div>
      {art}
    </section>
  </div>"""
    write("/about/", page("/about/", f"About · {NAME}", meta.get("lead") or TAGLINE, body, nav="about",
                          schema=ld(PERSON, {"@type": "AboutPage", "url": f"{SITE}/about/", "mainEntity": {"@id": f"{SITE}/#author"}},
                                    crumbs([("Home", "/"), ("About", "/about/")]))))


# ---------- wallpapers ----------
def load_wallpapers():
    """source/wallpapers/<name>/ holds the files people download, e.g. iphone.jpg and android.jpg."""
    out = []
    for folder in sorted(glob.glob(os.path.join(ROOT, "wallpapers", "*"))):
        slug = os.path.basename(folder)
        if not os.path.isdir(folder) or slug.startswith(("_", ".")):
            continue
        if not re.fullmatch(r"[a-z0-9-]+", slug):
            fail(f"Folder name wallpapers/{slug} should be lowercase letters, numbers and dashes only (e.g. shark-watercolor).")
        files = sorted(f for f in os.listdir(folder) if f.lower().endswith(IMG_EXT))
        if not files:
            continue
        items = []
        for f in files:
            low = f.lower()
            device = "iPhone" if "iphone" in low else "Android" if "android" in low else os.path.splitext(f)[0].replace("-", " ").replace("_", " ").title()
            items.append({"file": f, "device": device})
        items.sort(key=lambda x: (x["device"] != "iPhone", x["device"] != "Android", x["device"]))
        out.append({"slug": slug, "folder": folder, "title": slug.replace("-", " ").capitalize(), "items": items})
    return out


def build_wallpapers():
    if not WALLS:
        return
    cards = []
    for w in WALLS:
        btns = []
        for it in w["items"]:
            src = os.path.join(w["folder"], it["file"])
            ext = os.path.splitext(it["file"])[1].lower()
            rel = f"wallpapers/{w['slug']}/{w['slug']}-{it['device'].lower().replace(' ', '-')}{ext}"
            dst = os.path.join(OUT, rel); os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy(src, dst)  # the original file, untouched, so it stays sharp on the phone
            with Image.open(src) as im:
                it["w"], it["h"] = im.size
            it["url"] = f"/{rel}?v={fhash(dst)}"
            dl = f"Desk-Dives-{w['slug']}-{it['device'].replace(' ', '-')}{ext}"
            btns.append(f'<a class="dl" href="{it["url"]}" download="{e(dl)}" data-wall="{e(w["slug"])}" data-device="{e(it["device"])}">'
                        f'{e(it["device"])} <span>{it["w"]} × {it["h"]}</span></a>')
        first = open_img(os.path.join(w["folder"], w["items"][0]["file"]))
        th = first.copy(); th.thumbnail((640, 1400), Image.LANCZOS)
        w["thumb"] = save(th, f"images/wallpapers/{w['slug']}-preview.jpg", quality=82)
        w["og"] = og_card(first, f"images/og/wallpaper-{w['slug']}.jpg")
        cards.append(f"""<figure class="wall"><div class="plate"><div class="win"><img src="{w['thumb']}" width="{th.size[0]}" height="{th.size[1]}" alt="{e(w['title'])} phone wallpaper by {e(S.get('author',''))}" loading="lazy" decoding="async"></div></div>
        <figcaption><b>{e(w['title'])}</b><span class="dls">{''.join(btns)}</span></figcaption></figure>""")
    body = f"""  <div class="wrap">
    <section class="page-head"><span class="label">Free downloads</span><h1 class="glow">Wallpapers</h1>
      <p class="standfirst">Phone wallpapers from {e(NAME)}, free to use. Tap the button for your phone.</p>
      <p class="how">On iPhone: tap, then tap the share icon and choose <b>Save to Photos</b>. On Android: tap and the file saves to Downloads.</p></section>
    <div class="walls">{''.join(cards)}</div>
  </div>"""
    write("/wallpapers/", page("/wallpapers/", f"Free Phone Wallpapers · Dive Watch Watercolors · {NAME}",
                               f"Free {NAME} phone wallpapers for iPhone and Android: dive watch watercolors by {S.get('author','')}.",
                               body, nav="wallpapers", og=WALLS[0]["og"], og_alt=f"{NAME} phone wallpaper",
                               schema=ld(crumbs([("Home", "/"), ("Wallpapers", "/wallpapers/")]))))


def build_404():
    body = """  <div class="wrap"><section class="page-head"><span class="label">404</span><h1 class="glow">Too deep</h1>
    <p class="standfirst">That page doesn't exist. The watches are all <a class="inline" href="/watches/">here</a>.</p></section></div>"""
    write("/404.html", page("/404.html", f"Page not found · {NAME}", "This page could not be found.", body).replace(
        '<meta name="robots" content="index, follow, max-image-preview:large">', '<meta name="robots" content="noindex">'))


def build_static():
    os.makedirs(os.path.join(OUT, "assets"), exist_ok=True)
    for n in ("site.css", "site.js", "analytics.js"):
        shutil.copy(os.path.join(ROOT, n), os.path.join(OUT, "assets", n))
    urls = [("/", 1.0, None), ("/watches/", 0.9, None)] + [(w["url"], 0.8, w) for w in WATCHES] + \
           [("/videos/", 0.6, None)] + ([("/wallpapers/", 0.6, None)] if WALLS else []) + ([("/journal/", 0.6, None)] if POSTS else []) + [(p["url"], 0.6, None) for p in POSTS] + [("/about/", 0.5, None)]
    out = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">']
    for u, pr, w in urls:
        imgs = ""
        if w and w.get("img"):
            imgs = f"<image:image><image:loc>{SITE}{w['img_plain']}</image:loc></image:image>"
        out.append(f"  <url><loc>{SITE}{u}</loc><lastmod>{TODAY}</lastmod><priority>{pr}</priority>{imgs}</url>")
    out.append("</urlset>")
    open(os.path.join(OUT, "sitemap.xml"), "w").write("\n".join(out) + "\n")
    open(os.path.join(OUT, "robots.txt"), "w").write(f"""User-agent: *
Allow: /
Disallow: /404.html

# AI search and answer engines are welcome
User-agent: GPTBot
Allow: /
User-agent: OAI-SearchBot
Allow: /
User-agent: ChatGPT-User
Allow: /
User-agent: ClaudeBot
Allow: /
User-agent: Claude-SearchBot
Allow: /
User-agent: PerplexityBot
Allow: /
User-agent: Google-Extended
Allow: /
User-agent: Applebot-Extended
Allow: /

Sitemap: {SITE}/sitemap.xml
""")
    L = [f"# {NAME}", "", f"> {TAGLINE} A personal dive watch collection by {S.get('author','')}: mostly Seiko, some Omega and other Swiss and German watches, a few vintage pieces. Each watch page has specs, photos, videos and an honest verdict.", "",
         "## Pages", "", f"- [Watches]({SITE}/watches/): the full collection", f"- [Videos]({SITE}/videos/): YouTube videos", ] + ([f"- [Wallpapers]({SITE}/wallpapers/): free phone wallpapers"] if WALLS else []) + [f"- [About]({SITE}/about/)", "", "## Watches", ""]
    for w in WATCHES:
        bits = [w.get("ref") if w.get("ref") not in (None, "", "TBD") else None, w["specs"].get("Caliber") if w["specs"].get("Caliber") not in (None, "TBD") else None,
                w["specs"].get("Case") if w["specs"].get("Case") not in (None, "TBD") else None, ("Verdict: " + w["verdict"]) if w.get("verdict") else None]
        L.append(f"- [No. {w['no']} {w['title']}]({SITE}{w['url']})" + (": " + "; ".join(b for b in bits if b) if any(bits) else ""))
    if POSTS:
        L[L.index(f"- [About]({SITE}/about/)")] = f"- [Journal]({SITE}/journal/): occasional writing\n- [About]({SITE}/about/)"
        L += ["", "## Journal", ""] + [f"- [{p['title']}]({SITE}{p['url']}) ({p['date'].isoformat()})" for p in POSTS]
    if YT:
        L += ["", "## Elsewhere", "", f"- YouTube: {YT}"]
    open(os.path.join(OUT, "llms.txt"), "w").write("\n".join(L) + "\n")
    open(os.path.join(OUT, "site.webmanifest"), "w").write(json.dumps({"name": NAME, "short_name": NAME, "start_url": "/", "display": "browser",
        "background_color": "#06121c", "theme_color": "#06121c",
        "icons": [{"src": "/icon-192.png", "sizes": "192x192", "type": "image/png"}, {"src": "/icon-512.png", "sizes": "512x512", "type": "image/png"}]}, indent=2))
    open(os.path.join(OUT, "humans.txt"), "w").write(f"Watches and words: {S.get('author','')}\nType: Inter, Newsreader, IBM Plex Mono\n")


def build_brand_images():
    for s, name in ((512, "icon-512.png"), (192, "icon-192.png"), (180, "apple-touch-icon.png"), (48, "favicon-48.png"), (32, "favicon-32.png")):
        bezel_icon(s).save(os.path.join(OUT, name))
    bezel_icon(256).save(os.path.join(OUT, "favicon.ico"), sizes=[(16, 16), (32, 32), (48, 48)])
    open(os.path.join(OUT, "favicon.svg"), "w").write(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" fill="#06121c"/>'
        '<circle cx="32" cy="32" r="22" fill="none" stroke="#dceab9" stroke-width="5.4"/>'
        '<path d="M23.7 13.2h16.6L32 25.7z" fill="#dceab9"/></svg>')
    # default share image: featured watch if it has a photo, otherwise the bezel mark
    f = W_BY.get(S.get("featured"))
    if f and f.get("img"):
        IMG["og-site"] = og_card(open_img(os.path.join(f["folder"], f["main_file"])), "images/og/desk-dives.jpg")
    else:
        card = Image.new("RGB", (1200, 630), ABYSS)
        mark = bezel_icon(360)
        card.paste(mark, ((1200 - 360) // 2, (630 - 360) // 2))
        IMG["og-site"] = save(card, "images/og/desk-dives.jpg", quality=86)
    ap = next((p for p in glob.glob(os.path.join(ROOT, "brand", "about-*")) if p.lower().endswith(IMG_EXT)), None)
    if ap:
        im = open_img(ap); im.thumbnail((1600, 1600), Image.LANCZOS)
        IMG["about-art"] = (save(im, "images/about.jpg"), im.size[0], im.size[1])


if __name__ == "__main__":
    if os.path.exists(OUT):
        shutil.rmtree(OUT)
    os.makedirs(OUT)
    IMG = {}
    WATCHES = load_watches()
    if not WATCHES:
        fail("There are no watches. Add at least one folder in source/watches.")
    W_BY = {w["slug"]: w for w in WATCHES}
    for w in WATCHES:
        process_watch_images(w)
    VD = load_json(os.path.join(ROOT, "videos.json"))
    VIDEOS = []
    for v in VD.get("videos", []):
        vid = video_id(v)
        if not vid:
            continue
        v["id"] = vid
        pp = next((p for p in glob.glob(os.path.join(ROOT, "videos", vid + ".*")) if p.lower().endswith(IMG_EXT)), None)
        if pp:  # optional local poster: source/videos/<id>.jpg
            im = open_img(pp); im.thumbnail((900, 1600), Image.LANCZOS)
            v["poster"] = save(im, f"images/videos/{vid}.jpg")
        VIDEOS.append(v)
    for v in VIDEOS:
        for s in v.get("watches", []):
            if s not in W_BY:
                print(f"Note: video '{v['title']}' lists watch '{s}', which has no folder. Ignoring that link.")
    POSTS = load_journal()
    WALLS = load_wallpapers()
    build_brand_images()
    build_home(); build_watches_index()
    for i, w in enumerate(WATCHES):
        build_watch(w, i)
    build_videos(); build_journal(); build_wallpapers(); build_about(); build_404(); build_static()
    nv, np_ = len(VIDEOS), len(POSTS)
    v_word = "video" if nv == 1 else "videos"
    p_word = "journal entry" if np_ == 1 else "journal entries"
    print(f"Built {len(WATCHES)} watches, {nv} {v_word}, {np_} {p_word} into {OUT}")
