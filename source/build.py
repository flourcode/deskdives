#!/usr/bin/env python3
"""Builds deskdives.com into ../site from the files in this folder.

You never need to edit this file. Content lives in:
  site.json            site-wide settings
  watches/<name>/      one folder per watch: watch.json plus photos
  toys/<name>/, gear/<name>/   one folder per thing: item.json plus photos
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
# Categories besides watches. Each gets its menu link, page and filter once its first item is published.
CATS = [("watches", "Watches", "Watch"), ("toys", "Toys", "Toy"), ("gear", "Gear", "Gear")]
CAT_LABEL = {k: l for k, l, _ in CATS}
CAT_ONE = {k: o for k, _, o in CATS}


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
    elif rel.endswith(".webp"):
        im = im if im.mode in ("RGB", "RGBA") else im.convert("RGB")
        kw = {"quality": 78, "method": 6, **kw}
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


def widths(im, rel_base, ws):
    """WebP copies at the given widths (never upscaled). Returns [(url, width)], and (url, w, h) of the largest."""
    out, big = [], None
    for wd in sorted(ws):
        if wd > im.size[0] and out:
            break
        c = im.copy()
        if c.size[0] > wd:
            c = c.resize((wd, round(c.size[1] * wd / c.size[0])), Image.LANCZOS)
        url = save(c, f"{rel_base}-{c.size[0]}.webp")
        out.append((url, c.size[0])); big = (url, c.size[0], c.size[1])
    return out, big


def pick(srcset, want):
    """The candidate closest to `want` pixels wide, for the plain src."""
    return min(srcset, key=lambda x: abs(x[1] - want))[0]


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
        w["cat"] = "watches"
        main = find_images(w)
        missing = [x for x, ok in (("a photo", main), ("a reference", (w.get("ref") or "").strip() not in ("", "TBD"))) if not ok]
        if missing:
            print(f"Hidden for now: watches/{slug} needs {' and '.join(missing)} before it shows on the site.")
            continue
        ws.append(w)
    ws.sort(key=lambda w: (w.get("order", 999), w["slug"]))
    for i, w in enumerate(ws):
        w["no"] = f"{i + 1:02d}"
    return ws


def find_images(w):
    """main.jpg (or the first photo) is the big one; figure*.jpg are watercolors; the rest are gallery plates."""
    folder = w["folder"]
    imgs = sorted(f for f in os.listdir(folder) if f.lower().endswith(IMG_EXT))
    main = next((f for f in imgs if os.path.splitext(f)[0].lower() == "main"), None)
    figs = [f for f in imgs if f.lower().startswith("figure")]
    rest = [f for f in imgs if f != main and f not in figs]
    if not main and rest:
        main, rest = rest[0], rest[1:]
    w["main_file"], w["gallery_files"], w["figure_files"] = main, rest, figs
    return main


def load_things(cat):
    """source/toys/<name>/item.json, source/gear/<name>/item.json: lighter pages than watches."""
    out = []
    for folder in sorted(glob.glob(os.path.join(ROOT, cat, "*"))):
        slug = os.path.basename(folder)
        if not os.path.isdir(folder) or slug.startswith(("_", ".")):
            continue
        jp = os.path.join(folder, "item.json")
        if not os.path.exists(jp):
            fail(f"{cat}/{slug} has no item.json. Copy one from {cat}/_template.")
        t = load_json(jp)
        if t.get("draft"):
            continue
        if not re.fullmatch(r"[a-z0-9-]+", slug):
            fail(f"Folder name {cat}/{slug} should be lowercase letters, numbers and dashes only (e.g. godzilla-minus-one).")
        t.update(slug=slug, folder=folder, cat=cat, url=f"/{cat}/{slug}/", title=(t.get("name") or "").strip())
        for k, v in (("text", []), ("key_numbers", []), ("specs", {}), ("captions", {})):
            t.setdefault(k, v)
        main = find_images(t)
        missing = [x for x, ok in (("a photo", main), ("a name", t["title"])) if not ok]
        if missing:
            print(f"Hidden for now: {cat}/{slug} needs {' and '.join(missing)} before it shows on the site.")
            continue
        out.append(t)
    out.sort(key=lambda t: (t.get("order", 999), t["slug"]))
    for i, t in enumerate(out):
        t["no"] = f"{i + 1:02d}"
    return out


def slugify(t):
    return re.sub(r"[^a-z0-9]+", "-", str(t).lower()).strip("-")


def process_watch_images(w):
    cat = w.get("cat", "watches")
    rel = f"images/{cat}/{w['slug']}"
    w["img"] = None
    if w["main_file"]:
        im = open_img(os.path.join(w["folder"], w["main_file"]))
        base = f"{rel}/{w['slug']}-{slugify(w.get('brand', ''))}-watch" if cat == "watches" else f"{rel}/{w['slug']}"
        w["srcset"], (_, w["iw"], w["ih"]) = widths(im, base, [400, 600, 800, 1200, 1600])
        w["img"] = pick(w["srcset"], 800)
        big = im.copy(); big.thumbnail((1600, 1600), Image.LANCZOS)
        save(big, f"{base}.jpg")                        # JPG for share previews, Pinterest and search
        w["img_plain"] = f"/{base}.jpg"
        d = im.copy(); d.thumbnail((360, 360), Image.LANCZOS)
        w["disc"] = save(d, f"{base}-disc.webp")         # small round image in "On the wrist"
        w["og"] = og_card(im, f"images/og/{w['slug']}.jpg")
    w["gallery"] = []
    for f in w["gallery_files"]:
        im = open_img(os.path.join(w["folder"], f))
        base = os.path.splitext(f)[0]
        t = im.copy(); t.thumbnail((900, 900), Image.LANCZOS)
        tset, _ = widths(t, f"{rel}/{base}", [300, 450, 600, 900])
        thumb = pick(tset, 600)
        big = im.copy(); big.thumbnail((2400, 2400), Image.LANCZOS)
        full = save(big, f"{rel}/{base}.jpg")
        cap = w["captions"].get(f) or w["captions"].get(base) or base.replace("-", " ").replace("_", " ").capitalize()
        w["gallery"].append(dict(tset=", ".join(f"{u} {x}w" for u, x in tset), thumb=thumb, full=full, w=t.size[0], h=t.size[1], caption=cap))
    w["figures"] = []
    for f in w["figure_files"]:
        im = open_img(os.path.join(w["folder"], f))
        big = im.copy(); big.thumbnail((1800, 1800), Image.LANCZOS)
        url = save(big, f"{rel}/{os.path.splitext(f)[0]}.jpg")
        w["figures"].append(dict(url=url, w=big.size[0], h=big.size[1], caption=w["captions"].get(f, "Watercolor, " + S.get("author", ""))))


def is_watch(t):
    return t.get("cat", "watches") == "watches"


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
    cat_links = "".join(link(c, f"/{c}/", CAT_LABEL[c]) for c in LIVE_CATS)
    guides_nav = [g for g in GUIDES if g["meta"].get("nav_label")]
    # The nickname guide stays in the menu until Toys, Gear and Journal make it crowded (it's always in the footer and on Watches).
    show_guides = len(LIVE_CATS) + len(guides_nav) + (1 if POSTS else 0) + 2 <= 5
    yt_foot = f' · <a href="{e(YT)}" target="_blank" rel="me noopener">{e(S.get("youtube_label","YouTube"))}</a>' if YT else ""
    wall_foot = ' · <a href="/wallpapers/">Free wallpapers</a>' if WALLS else ""
    guide_foot = wall_foot + "".join(f' · <a href="{g["url"]}">{e(g["meta"].get("footer_label") or g["meta"].get("title", ""))}</a>' for g in GUIDES)
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
{'' if IMG.get("brand_icon") else '<link rel="icon" type="image/svg+xml" href="/favicon.svg">'}
<link rel="icon" type="image/png" sizes="32x32" href="/favicon-32.png">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<link rel="manifest" href="/site.webmanifest">
<link rel="alternate" type="text/plain" title="LLM summary" href="/llms.txt">
<link rel="preload" href="{FONT_URL['inter-latin-var.woff2']}" as="font" type="font/woff2" crossorigin>
<link rel="preload" href="{FONT_URL['newsreader-latin-400-normal.woff2']}" as="font" type="font/woff2" crossorigin>
<style>{INLINE_CSS}</style>
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
        {cat_links}
        {"".join(link("guide-" + g["slug"], g["url"], e(g["meta"]["nav_label"])) for g in guides_nav) if show_guides else ""}
        {link("videos", "/videos/", "Videos")}
        {link("journal", "/journal/", "Journal") if POSTS else ""}
        {link("about", "/about/", "About")}
      </nav>
    </div>
    <div class="dateline"><span>{len(ALL)} thing{"" if len(ALL) == 1 else "s"} on the desk{(" · " + e(S["dateline"])) if S.get("dateline") else ""}</span></div>
  </header>
</div>
<main id="main" class="clip">
{body}
</main>
<div class="wrap">
  <footer class="site"><div class="bar"><span class="wordmark small">{e(NAME.upper())}</span><span>{e(TAGLINE)}{yt_foot}{guide_foot} · © {date.today().year} {e(S.get('author',''))}</span></div></footer>
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
               f'alt="{e(alt_of(w))}" {load} decoding="async">')
        win = f'<div class="win">{img}</div>'
        cls = "plate"
    else:
        win = '<div class="win"><span class="ring"></span></div>'
        cls = "plate empty"
    cap = (f'<figcaption><span><b>Plate {w["no"]}</b> · {e(w["title"])}</span><span>{"" if w.get("img") else "Photo to come"}</span></figcaption>'
           if caption else "")
    return f'<figure class="{cls}">{win}{cap}</figure>'


def alt_of(t):
    if is_watch(t):
        return f"{t['title']} {t.get('ref','') if t.get('ref') not in (None,'','TBD') else ''} watch".replace("  ", " ")
    return t["title"]


def rank(w):
    r = str(w.get("wrist_rank") or "").strip()
    return f"P{r}" if r else ""


def ref_text(w):
    r = w.get("ref") or "TBD"
    return f"REF {r}"


def watch_card(w, mixed=False):
    if not is_watch(w):
        return thing_card(w, mixed)
    rk = rank(w)
    rk_html = f"<b>{rk} · WRIST TIME</b>" if rk == "P1" else (f"<span>{rk}</span>" if rk else "")
    no = f"WATCH · NO. {w['no']}" if mixed else f"NO. {w['no']}"
    return f"""        <a class="watch-card" href="{w['url']}" data-cat="watches"{sound_attr(w)}>
          {plate(w, caption=False)}
          <div class="meta"><span class="no"><span>{no}</span>{rk_html}</span><span class="name">{e(w['title'])}</span><span class="ref">{e(ref_text(w))}</span><span class="line">{e(w.get('line',''))}</span></div>
        </a>"""


def sound_attr(t):
    return ' data-sound="1"' if t["slug"] in SOUND else ""


def thing_sub(t):
    return " · ".join(x for x in [t.get("maker"), t.get("kind")] if x)


def thing_card(t, mixed=False):
    no = f"{CAT_ONE[t['cat']].upper()} · NO. {t['no']}" if mixed else f"NO. {t['no']}"
    return f"""        <a class="watch-card" href="{t['url']}" data-cat="{t['cat']}"{sound_attr(t)}>
          {plate(t, caption=False)}
          <div class="meta"><span class="no"><span>{no}</span></span><span class="name">{e(t['title'])}</span><span class="ref">{e(thing_sub(t))}</span><span class="line">{e(t.get('line',''))}</span></div>
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
    hq = f"https://i.ytimg.com/vi/{e(v['id'])}/hqdefault.jpg"
    thumb = v.get("poster") or (f"https://i.ytimg.com/vi/{e(v['id'])}/oardefault.jpg" if short else hq)
    fb = f' data-fb="{hq}"' if (short and not v.get("poster")) else ""
    poster_srcset = (' srcset="' + ", ".join(f"{u} {x}w" for u, x in v["poster_set"]) + '" sizes="(max-width: 600px) 80vw, 300px"') if v.get("poster_set") else ""
    w_titles = ", ".join(e(ALL_BY[s]["title"]) for s in features(v) if s in ALL_BY)
    cls = "vid" + (" big" if big else "") + (" short" if short else "")
    link = f"https://www.youtube.com/shorts/{e(v['id'])}" if short else f"https://www.youtube.com/watch?v={e(v['id'])}"
    tc = f'<span class="tc">{e(v.get("length",""))}</span>' if v.get("length") else ""
    tag = ('<span class="tag">Short' + (' · 🔊 Sound on' if v.get("sound") else "") + '</span>') if short else ('<span class="tag">🔊 Sound on</span>' if v.get("sound") else "")
    return f"""<div class="{cls}">
          <button type="button" class="thumb" data-yt="{e(v['id'])}" aria-label="Play video: {e(v['title'])}"><img src="{thumb}"{poster_srcset}{fb} alt="" loading="lazy" decoding="async"><span class="play"></span>{tag}{tc}</button>
          <h3><a href="{link}" target="_blank" rel="noopener">{e(v['title'])}</a></h3>
          <p>{e(v.get('summary',''))}{(' · Features ' + w_titles) if w_titles else ''}</p>
        </div>"""


def features(v):
    return list(v.get("watches", [])) + list(v.get("things", []))


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
    f = W_BY.get(S.get("featured")) or ALL_BY.get(S.get("featured")) or (WATCHES[0] if WATCHES else None)
    if IMG.get("hero"):   # brand/hero.jpg: a photo of the desk itself
        f = IMG["hero"]
    hero_plate = ""
    if f:
        hero_plate = f'<a class="hero-link" href="{f["url"]}">{plate(f, eager=True, sizes="(max-width: 900px) 92vw, 46vw")}</a>'
    desk = [ALL_BY[s] for s in (S.get("on_desk") or []) if s in ALL_BY] or WATCHES[:6]
    cards = "\n".join(watch_card(w, mixed=True) for w in desk[:8])
    # Latest from the desk: anything with an "added" date, newest first
    dated = sorted((t for t in ALL if re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(t.get("added") or "")) and t not in desk), key=lambda t: t["added"], reverse=True)[:4]  # skips what's already in the row above
    latest = ""
    if len(dated) >= 2:
        latest = f"""<section class="sect" aria-labelledby="new-h">
      <div class="sect-head"><h2 id="new-h" class="label">Latest from the desk</h2><a href="/desk/">Everything →</a></div>
      <div class="collection">
{chr(10).join(watch_card(t, mixed=True) for t in dated)}
      </div>
    </section>"""
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
    video_col = f"""<div class="col-b"><span class="label">On YouTube</span><h2 class="mod-head">{'Latest video' if len(VIDEOS) <= 1 else 'Latest videos'}</h2>
        <p class="mod-sub">{e(S.get("videos_sub") or "")}</p>{video_mod}
        <a class="more-link" href="/videos/">All videos →</a></div>"""
    # Listen to the desk: the newest Shorts, near the top, because the videos are what's working
    listen = ""
    if len(VIDEOS) >= 2:
        row = "\n".join(video_card(v) for v in VIDEOS[:4])
        listen = f"""<section class="sect" aria-labelledby="listen-h">
      <div class="sect-head"><h2 id="listen-h" class="label">{e(S.get("listen_title") or "Latest videos")}</h2><a href="/videos/">All {len(VIDEOS)} videos →</a></div>
      <p class="mod-sub listen-sub">{e(S.get("videos_sub") or "")}</p>
      <div class="shorts-row">{row}</div>
    </section>"""
    journal_col = ""
    if POSTS:
        journal_col = f"""<div class="col-a"><span class="label">Only on {e(NAME)}</span><h2 class="mod-head">{e(S.get("journal_title") or "From the journal")}</h2>
        <p class="mod-sub">{e(S.get("journal_sub") or "Occasional writing.")}</p>{journal_mod}
        <a class="more-link" href="/journal/">All entries →</a></div>"""
    ow = W_BY.get(S.get("on_wrist"))
    spot = ""
    if ow:
        disc = f'<img src="{ow["disc"]}" alt="" loading="lazy" decoding="async">' if ow.get("disc") else ""
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
        {f'<p class="subline">{e(S["subline"])}</p>' if S.get("subline") else ""}
      </div>
      {hero_plate}
    </section>
    {listen}
    <section class="sect" aria-labelledby="col-h">
      <div class="sect-head"><h2 id="col-h" class="label">On the desk now</h2><a href="/desk/">The whole desk · {len(ALL)} things →</a></div>
      <div class="collection">
{cards}
      </div>
    </section>
    {latest}
    <section class="grid modules{(' two' if not POSTS else '') if not listen else (' one' if not POSTS else ' two-j')}" aria-label="More">
      {journal_col}
      {'' if listen else video_col}
      <div class="col-c">{spot}{sub}</div>
    </section>
  </div>"""
    items = {"@type": "ItemList", "name": "On the desk now", "itemListElement": [
        {"@type": "ListItem", "position": i + 1, "url": f"{SITE}{w['url']}", "name": w["title"]} for i, w in enumerate(desk)]}
    write("/", page("/", S.get("home_title") or f"{NAME} · Dive Watches, Toys and Desk Gear",
                    S.get("description") or TAGLINE,
                    body, schema=ld(WEBSITE, PERSON, items), og_alt=f"{NAME}: things on the desk"))


def build_watches_index():
    cards = "\n".join(watch_card(w) for w in WATCHES)
    body = f"""  <div class="wrap">
    <section class="page-head"><span class="label">The collection</span><h1 class="glow">Watches</h1>
      <p class="standfirst">{(e(S["watch_tagline"]) + " ") if S.get("watch_tagline") else ""}{len(WATCHES)} watches, numbered in the order they arrived, with specs, photos and honest notes on each.</p>
      {"".join(f'<p class="how">Wondering why a Seiko is called a Turtle? <a class="inline" href="{g["url"]}">{e(g["meta"].get("footer_label") or g["meta"].get("title",""))} →</a></p>' for g in GUIDES[:1])}</section>
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
    gal = "".join(f"""<figure class="plate"><a class="win" href="{g['full']}"><img src="{g['thumb']}" srcset="{g['tset']}" sizes="(max-width: 560px) 46vw, 300px" width="{g['w']}" height="{g['h']}" alt="{e(w['title'])}: {e(g['caption'])}" loading="lazy" decoding="async"></a>
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
    gl = GUIDE_LINKS.get(w["slug"], [])
    nick_links = ('<p class="g-back">Nickname explained: ' + ", ".join(f'<a class="inline" href="{u}">{e(n)}</a>' for n, u in gl) + "</p>") if gl else ""
    longest = max((len(x) for x in w["model"].split()), default=0)
    h1_cls = " xlong" if longest > 11 else (" long" if longest > 8 else "")
    body = f"""  <div class="wrap">
    <section class="w-head">
      <span class="label">No. {w['no']} · {e(sub)}</span>
      <h1 class="glow{h1_cls}">{e(w['model'])}</h1>
      <p class="nick">{f"<i>{e(w.get('nickname'))}:</i> " if w.get('nickname') else ''}{e(w.get('line',''))}</p>
      {nick_links}
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


def build_category(cat):
    items = THINGS[cat]
    intro = (S.get("sections") or {}).get(cat, "")
    cards = "\n".join(thing_card(t) for t in items)
    body = f"""  <div class="wrap">
    <section class="page-head"><span class="label">On the desk</span><h1 class="glow">{e(CAT_LABEL[cat])}</h1>
      <p class="standfirst">{(e(intro) + " ") if intro else ""}{len(items)} so far.</p></section>
    <div class="collection">
{cards}
    </div>
  </div>"""
    lst = {"@type": "ItemList", "name": CAT_LABEL[cat], "itemListElement": [
        {"@type": "ListItem", "position": i + 1, "url": f"{SITE}{t['url']}", "name": t["title"]} for i, t in enumerate(items)]}
    write(f"/{cat}/", page(f"/{cat}/", f"{CAT_LABEL[cat]} · {NAME}", f"{CAT_LABEL[cat]} on the {NAME} desk. {intro}".strip(), body, nav=cat,
                           schema=ld({"@type": "CollectionPage", "url": f"{SITE}/{cat}/", "name": CAT_LABEL[cat], "mainEntity": lst},
                                     crumbs([("Home", "/"), (CAT_LABEL[cat], f"/{cat}/")]))))


def build_thing(t, i):
    items = THINGS[t["cat"]]
    prev, nxt = (items[i - 1] if i else None), (items[i + 1] if i + 1 < len(items) else None)
    cat, label = t["cat"], CAT_LABEL[t["cat"]]
    blank = lambda v: v is None or str(v).strip() in ("", "TBD")
    rows = [(k, v) for k, v in t["specs"].items() if not blank(v)]
    if not blank(t.get("acquired")):
        rows.append(("Acquired", t["acquired"]))
    spec_rows = "".join(f'<tr><th scope="row">{e(k)}</th><td>{e(v)}</td></tr>' for k, v in rows)
    specs = f'<table class="specs"><caption class="label">A few details</caption>{spec_rows}</table>' if rows else ""
    kn = "".join(f'<div><b>{e(v)}</b><span class="label">{e(l)}</span></div>' for v, l in t["key_numbers"])
    timing = f'<section class="timing" style="--n:{len(t["key_numbers"])}" aria-label="Key numbers">{kn}</section>' if t["key_numbers"] else ""
    share = share_links(SITE + t["url"], f"{t['title']} · {NAME}", SITE + (t.get("img_plain") or IMG["og-site"]), cat, t["slug"])
    # Every toy and gear page has the same small structure: What it is, Why it's on the desk, A few details (the table), Would I buy it again?
    paras = lambda v: [v] if isinstance(v, str) else list(v or [])
    what = "".join(f"<p>{inline(p)}</p>" for p in paras(t.get("what")) if str(p).strip())
    why = "".join(f"<p>{inline(p)}</p>" for p in (paras(t.get("why")) or paras(t.get("text"))) if str(p).strip())
    verdict = ""
    if t.get("verdict"):
        vnote = "<p>" + e(t["verdict_note"]) + "</p>" if t.get("verdict_note") else ""
        verdict = f'<div class="verdict"><h3 class="label">Would I buy it again?</h3><b class="glow">{e(t["verdict"])}</b>{vnote}</div>'
    parts = (f'<h3 class="label">What it is</h3>{what}' if what else "") + (f'<h3 class="label">Why it\'s on the desk</h3>{why}' if why else "") + verdict
    notes = f"""<section class="grid take thing-notes">
      <div class="col-l"><h2>On the desk</h2></div>
      <div class="col-r body">{parts}</div>
    </section>""" if parts else ""
    gal = "".join(f"""<figure class="plate"><a class="win" href="{g['full']}"><img src="{g['thumb']}" srcset="{g['tset']}" sizes="(max-width: 560px) 46vw, 300px" width="{g['w']}" height="{g['h']}" alt="{e(t['title'])}: {e(g['caption'])}" loading="lazy" decoding="async"></a>
          <figcaption><span><b>Plate {t['no']}.{j + 2}</b> · {e(g['caption'])}</span></figcaption></figure>""" for j, g in enumerate(t["gallery"]))
    vid_html = "".join(video_card(v) for v in VIDEOS if t["slug"] in features(v))
    more = f"""<section class="sect"><div class="sect-head"><h2 class="label">More plates and videos</h2></div>
      <div class="gallery">{gal}{vid_html}</div></section>""" if (gal or vid_html) else ""
    figs = "".join(f"""<section class="grid fig"><div class="txt"><span class="label">Fig.</span><p><i>From the sketchbook:</i> {e(f['caption'])}</p></div>
      <figure class="art"><img src="{f['url']}" width="{f['w']}" height="{f['h']}" alt="Watercolor of the {e(t['title'])}" loading="lazy" decoding="async"></figure></section>""" for f in t["figures"])
    find = ""
    if t.get("affiliate_url"):
        find = f'<div class="find"><a href="{e(t["affiliate_url"])}" target="_blank" rel="sponsored noopener">{e(t.get("affiliate_label") or "Where to find one")} →</a><span>If you buy through this link, I may earn a small commission.</span></div>'
    pl = f'<a href="{prev["url"]}"><span class="label">← No. {prev["no"]}</span>{e(prev["title"])}</a>' if prev else f'<a href="/{cat}/"><span class="label">← {e(label)}</span>All {e(label.lower())}</a>'
    nl = f'<a class="next" href="{nxt["url"]}"><span class="label">No. {nxt["no"]} →</span>{e(nxt["title"])}</a>' if nxt else f'<a class="next" href="/desk/"><span class="label">The desk →</span>Everything else</a>'
    sub = " · ".join(x for x in [CAT_ONE[cat], t.get("maker"), t.get("kind")] if x)
    words = t["title"].split()
    h1_cls = " words" if len(words) > 2 or len(t["title"]) > 14 else (" xlong" if max(len(x) for x in words) > 11 else (" long" if max(len(x) for x in words) > 8 else ""))
    body = f"""  <div class="wrap">
    <section class="w-head">
      <span class="label">No. {t['no']} · {e(sub)}</span>
      <h1 class="glow{h1_cls}">{e(t['title'])}</h1>
      {f'<p class="nick">{e(t.get("line",""))}</p>' if t.get("line") else ""}
    </section>
    {timing}
    <section class="grid w-main">
      {plate(t, eager=True, sizes="(max-width: 900px) 92vw, 55vw")}
      <aside class="w-side">
        {specs}
        {share}
      </aside>
    </section>
    {notes}
    {figs}
    {more}
    {find}
    <nav class="pager" aria-label="More {e(label.lower())}">{pl}{nl}</nav>
  </div>"""
    what_txt = plain(" ".join(str(x) for x in paras(t.get("what")))) or t.get("line", "")
    desc = f"{t['title']}{(' (' + t['maker'] + ')') if t.get('maker') else ''}: {what_txt or 'On the ' + NAME + ' desk.'}"[:300]
    trail = crumbs([("Home", "/"), (label, f"/{cat}/"), (t["title"], t["url"])])
    write(t["url"], page(t["url"], f"{t['title']} · {label} · {NAME}", desc, body, nav=cat, og=t.get("og"), og_alt=t["title"], og_type="article",
                         schema=ld(trail)))


def build_desk():
    chips = ""
    if len(LIVE_CATS) > 1:
        chips = '<div class="chips" role="group" aria-label="Show">' + '<button type="button" class="chip" data-filter="all" aria-pressed="true">All <span>' + str(len(ALL)) + '</span></button>' + \
            "".join(f'<button type="button" class="chip" data-filter="{c}" aria-pressed="false">{e(CAT_LABEL[c])} <span>{len(WATCHES) if c == "watches" else len(THINGS[c])}</span></button>' for c in LIVE_CATS) + \
            (f'<button type="button" class="chip" data-filter="sound" aria-pressed="false">🔊 Sounds <span>{sum(1 for t in ALL if t["slug"] in SOUND)}</span></button>' if any(t["slug"] in SOUND for t in ALL) else "") + "</div>"
    cards = "\n".join(watch_card(t, mixed=True) for t in ALL)
    body = f"""  <div class="wrap">
    <section class="page-head"><span class="label">Everything</span><h1 class="glow">The desk</h1>
      <p class="standfirst">{len(ALL)} things. {(e(S["dateline"].rstrip(".")) + ".") if S.get("dateline") else ""}</p>{chips}</section>
    <div class="collection" data-filterable>
{cards}
    </div>
  </div>"""
    lst = {"@type": "ItemList", "name": "The desk", "itemListElement": [
        {"@type": "ListItem", "position": i + 1, "url": f"{SITE}{t['url']}", "name": t["title"]} for i, t in enumerate(ALL)]}
    write("/desk/", page("/desk/", f"The Desk · Everything in the Collection · {NAME}", f"Everything on the {NAME} desk: {len(ALL)} watches, toys and other things, with photos and notes.",
                         body, nav="desk", schema=ld({"@type": "CollectionPage", "url": f"{SITE}/desk/", "name": "The desk", "mainEntity": lst},
                                                     crumbs([("Home", "/"), ("The desk", "/desk/")]))))


def build_videos():
    if VIDEOS:
        grid = "\n".join(video_card(v, big=(i == 0)) for i, v in enumerate(VIDEOS))
    else:
        grid = '<div class="vid"><div class="thumb static"><span class="play"></span></div><p class="empty-note">The first new video is coming soon.</p></div>'
    yt = f'<p class="standfirst">New videos on <a class="inline" href="{e(YT)}" target="_blank" rel="noopener">YouTube</a>. Every video is listed here with the things it features.</p>' if YT else '<p class="standfirst">' + e(S.get("videos_sub") or "") + '</p>'
    body = f"""  <div class="wrap">
    <section class="page-head"><span class="label">On YouTube</span><h1 class="glow">Videos</h1>{yt}</section>
    <div class="video-grid">{grid}</div>
  </div>"""
    nodes = [{"@type": "VideoObject", "name": v["title"], "description": v.get("summary") or v["title"],
              "thumbnailUrl": (SITE + v["poster_jpg"]) if v.get("poster_jpg") else f"https://i.ytimg.com/vi/{v['id']}/hqdefault.jpg", "uploadDate": v.get("date") or TODAY,
              "embedUrl": f"https://www.youtube-nocookie.com/embed/{v['id']}", "contentUrl": (f"https://www.youtube.com/shorts/{v['id']}" if v.get("short") else f"https://www.youtube.com/watch?v={v['id']}")} for v in VIDEOS]
    write("/videos/", page("/videos/", f"Videos · Watches and Desk Things on YouTube · {NAME}", f"{NAME} videos: {S.get('videos_sub') or 'watches and other things on the desk'}",
                           body, nav="videos", schema=ld(*nodes, crumbs([("Home", "/"), ("Videos", "/videos/")]))))


def build_journal():
    if POSTS:
        rows = "".join(f'<li><a href="{p["url"]}"><span class="d">{p["date"].strftime("%b %Y").upper()}</span><span class="t">{e(p["title"])}<small>{e(p["summary"])}</small></span><span class="r">{p["minutes"]} MIN</span></a></li>' for p in POSTS)
        lst = f'<ol class="journal">{rows}</ol>'
    else:
        lst = '<p class="empty-note">The first entry is on its way.</p>'
    body = f"""  <div class="wrap">
    <section class="page-head"><span class="label">Only on {e(NAME)}</span><h1 class="glow">Journal</h1>
      <p class="standfirst">{e(S.get("journal_sub") or "Occasional writing.")}</p></section>
    {lst}
  </div>"""
    write("/journal/", page("/journal/", f"Journal · {NAME}", f"{S.get('journal_sub') or 'Occasional writing'} From {NAME}.", body, nav="journal",
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
        u, aw, ah, aset = IMG["about-art"]
        art = f'<figure class="art"><img src="{u}" srcset="{aset}" sizes="(max-width: 900px) 100vw, 50vw" width="{aw}" height="{ah}" alt="Watercolor by {e(S.get("author",""))} of a dive watch" loading="lazy" decoding="async"><figcaption class="label">Fig. 1 · Watercolor, {e(S.get("author",""))}</figcaption></figure>'
    body = f"""  <div class="wrap">
    <section class="grid about">
      <div class="copy">
        {f'<img class="headshot" src="{IMG["headshot"]}" width="240" height="240" alt="{e(S.get("author",""))}, who writes {e(NAME)}">' if IMG.get("headshot") else ""}
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
        w["thumb"] = save(th, f"images/wallpapers/{w['slug']}-preview.webp")
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


# ---------- guides (cornerstone pages such as /seiko-nicknames/) ----------
GUIDE_TAGS = {"seiko": "Seiko name", "collector": "Collector name", "adopted": "Collector name, adopted by Seiko"}


def anchor(t):
    return re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-")


def load_guides():
    """source/guides/<name>.md becomes /<name>/. Entries are '## Name {seiko|collector|adopted}';
    '**Key:** value' lines become a fact list; '[[mine: watch-folder]]' adds an 'In my collection' card."""
    guides = []
    for path in sorted(glob.glob(os.path.join(ROOT, "guides", "*.md"))):
        name = os.path.splitext(os.path.basename(path))[0]
        if name.startswith("_"):
            continue
        meta, body = front_matter(open(path, encoding="utf-8").read())
        if meta.get("draft") in (True, "true", "yes"):
            continue
        g = {"slug": name, "url": f"/{name}/", "meta": meta, "intro": [], "blocks": []}
        cur = None
        for raw in body.splitlines():
            line = raw.rstrip()
            m = re.match(r"^##\s+(.+?)\s*\{(seiko|collector|adopted)\}\s*$", line)
            if m:
                cur = {"kind": "entry", "name": m.group(1).strip(), "tag": m.group(2), "lines": [], "mine": [], "facts": []}
                cur["id"] = anchor(cur["name"]); g["blocks"].append(cur); continue
            m = re.match(r"^#{1,2}\s+(.+?)\s*$", line)
            if m:
                cur = {"kind": "part", "name": m.group(1).strip(), "lines": []}; g["blocks"].append(cur); continue
            if line.strip() == "---":
                continue
            target = cur["lines"] if cur else g["intro"]
            mm = re.match(r"^\[\[mine:\s*([a-z0-9-]+)\s*\]\]$", line.strip())
            fm = re.match(r"^\*\*([^*]+?):\*\*\s*(.+)$", line.strip())
            if cur and cur["kind"] == "entry" and mm:
                cur["mine"].append(mm.group(1))
            elif cur and cur["kind"] == "entry" and fm:
                cur["facts"].append((fm.group(1), fm.group(2)))
            else:
                target.append(line)
        guides.append(g)
    return guides


def guide_links():
    """watch folder -> [(nickname, url#anchor)] so watch pages can link to their nickname entry."""
    links = {}
    for g in GUIDES:
        for b in g["blocks"]:
            for slug in b.get("mine", []):
                links.setdefault(slug, []).append((b["name"], f"{g['url']}#{b['id']}"))
    return links


def build_guides():
    for g in GUIDES:
        meta, entries = g["meta"], [b for b in g["blocks"] if b["kind"] == "entry"]
        jump = sorted(entries, key=lambda b: (not b["name"][0].isdigit(), b["name"].lower()))
        jump_html = "".join(f'<a href="#{b["id"]}">{e(b["name"])}</a>' for b in jump)
        parts = []
        for b in g["blocks"]:
            text = markdown("\n".join(b["lines"]))
            if b["kind"] == "part":
                parts.append(f'<section class="g-part"><h2>{inline(b["name"])}</h2>{text}</section>'); continue
            facts = "".join(f"<div><dt>{e(k)}</dt><dd>{inline(v)}</dd></div>" for k, v in b["facts"])
            mine = ""
            for slug in b["mine"]:
                w = W_BY.get(slug)
                if not w or not w.get("img"):
                    continue
                th = pick(w["srcset"], 400)
                mine += (f'<a class="mine" href="{w["url"]}"><img src="{th}" alt="My {e(w["title"])}" loading="lazy" decoding="async">'
                         f'<span><span class="label">In my collection</span><b>{e(w["title"])}</b><i>{e(w.get("line",""))}</i>'
                         f'<em>See my {e(w["model"])} →</em></span></a>')
            parts.append(f'<section class="g-entry" id="{b["id"]}"><div class="g-head"><h2>{e(b["name"])}</h2>'
                         f'<span class="g-tag g-{b["tag"]}">{GUIDE_TAGS[b["tag"]]}</span></div>'
                         f'<div class="g-body">{text}{("<dl class=g-facts>" + facts + "</dl>") if facts else ""}{mine}</div></section>')
        title = meta.get("title", g["slug"].replace("-", " ").title())
        body = f"""  <div class="wrap">
    <section class="page-head guide-head"><span class="label">Guide</span><h1 class="glow">{e(title)}</h1>
      {f'<p class="standfirst">{inline(meta["kicker"])}</p>' if meta.get("kicker") else ""}</section>
    <div class="g-intro">{markdown(chr(10).join(g["intro"]))}</div>
    <nav class="g-jump" aria-label="Jump to a nickname"><span class="label">Jump to</span><div>{jump_html}</div></nav>
    <div class="g-list">{"".join(parts)}</div>
  </div>"""
        art = {"@type": "Article", "headline": title, "description": meta.get("description", ""), "url": f"{SITE}{g['url']}",
               "author": {"@id": f"{SITE}/#author"}, "publisher": {"@id": f"{SITE}/#website"}, "dateModified": TODAY,
               "about": [b["name"] for b in entries]}
        write(g["url"], page(g["url"], f"{meta.get('seo_title') or title} · {NAME}", meta.get("description") or title, body, nav="guide-" + g["slug"],
                             og_type="article", schema=ld(art, crumbs([("Home", "/"), (title, g["url"])]))))


def build_redirects():
    """Old addresses from site.json 'redirects' forward to the new page."""
    for old, new in (S.get("redirects") or {}).items():
        if not old.startswith("/") or not new.startswith("/"):
            fail(f"site.json redirects: both addresses should start with / (got '{old}' -> '{new}').")
        target = SITE + new
        html_ = (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Moved · {e(NAME)}</title>'
                 f'<link rel="canonical" href="{target}"><meta name="robots" content="noindex">'
                 f'<meta http-equiv="refresh" content="0; url={new}"></head>'
                 f'<body><p>This page moved to <a href="{new}">{target}</a>.</p></body></html>')
        dst = os.path.join(OUT, old.strip("/"), "index.html") if old.endswith("/") else os.path.join(OUT, old.lstrip("/"))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if os.path.exists(dst):
            fail(f"site.json redirects: '{old}' is still a real page. Remove the redirect or hide that page first.")
        open(dst, "w", encoding="utf-8").write(html_)


def build_404():
    body = """  <div class="wrap"><section class="page-head"><span class="label">404</span><h1 class="glow">Too deep</h1>
    <p class="standfirst">That page doesn't exist. Everything is <a class="inline" href="/desk/">on the desk</a>.</p></section></div>"""
    write("/404.html", page("/404.html", f"Page not found · {NAME}", "This page could not be found.", body).replace(
        '<meta name="robots" content="index, follow, max-image-preview:large">', '<meta name="robots" content="noindex">'))


FONT_FACES = [  # self-hosted (no Google Fonts request): family, file, weight, style
    ("Inter", "inter-latin-var.woff2", "100 900", "normal"),
    ("Newsreader", "newsreader-latin-400-normal.woff2", "400", "normal"),
    ("Newsreader", "newsreader-latin-400-italic.woff2", "400", "italic"),
    ("Newsreader", "newsreader-latin-500-normal.woff2", "500", "normal"),
    ("Newsreader", "newsreader-latin-500-italic.woff2", "500", "italic"),
    ("IBM Plex Mono", "ibm-plex-mono-latin-400-normal.woff2", "400", "normal"),
    ("IBM Plex Mono", "ibm-plex-mono-latin-500-normal.woff2", "500", "normal"),
    ("IBM Plex Mono", "ibm-plex-mono-latin-600-normal.woff2", "600", "normal"),
]


def prepare_fonts_and_css():
    """Copy fonts to /assets/fonts and build the CSS that every page carries inline (one less request before the page can draw)."""
    global INLINE_CSS
    os.makedirs(os.path.join(OUT, "assets", "fonts"), exist_ok=True)
    faces = []
    for fam, fn, wt, st in FONT_FACES:
        src = os.path.join(ROOT, "fonts", fn)
        if not os.path.exists(src):
            fail(f"Missing font file: source/fonts/{fn}")
        shutil.copy(src, os.path.join(OUT, "assets", "fonts", fn))
        FONT_URL[fn] = f"/assets/fonts/{fn}?v={fhash(src)}"
        faces.append(f"@font-face{{font-family:'{fam}';font-style:{st};font-weight:{wt};font-display:swap;src:url({FONT_URL[fn]}) format('woff2')}}")
    css = open(os.path.join(ROOT, "site.css"), encoding="utf-8").read()
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)          # drop comments
    css = re.sub(r"\s*\n\s*", "\n", css).strip()
    INLINE_CSS = "".join(faces) + "\n" + css


def build_static():
    os.makedirs(os.path.join(OUT, "assets"), exist_ok=True)
    for n in ("site.css", "site.js", "analytics.js"):
        shutil.copy(os.path.join(ROOT, n), os.path.join(OUT, "assets", n))
    urls = [("/", 1.0, None), ("/desk/", 0.8, None), ("/watches/", 0.9, None)] + [(w["url"], 0.8, w) for w in WATCHES] + \
           [(u, 0.8, None) for c in LIVE_CATS if c != "watches" for u in [f"/{c}/"]] + [(t["url"], 0.7, t) for c in LIVE_CATS if c != "watches" for t in THINGS[c]] + \
           [(g["url"], 0.8, None) for g in GUIDES] + [("/videos/", 0.6, None)] + ([("/wallpapers/", 0.6, None)] if WALLS else []) + ([("/journal/", 0.6, None)] if POSTS else []) + [(p["url"], 0.6, None) for p in POSTS] + [("/about/", 0.5, None)]
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
    L = [f"# {NAME}", "", f"> {TAGLINE} {S.get('subline','')} A personal collection by {S.get('author','')}, anchored by dive watches (mostly Seiko, some Omega and other Swiss and German watches, a few vintage pieces), plus toys, gadgets and desk gear. Watch pages have specs, photos, videos and an honest verdict.", "",
         "## Pages", "", f"- [The desk]({SITE}/desk/): everything", f"- [Watches]({SITE}/watches/): the watch collection"] + \
        [f"- [{CAT_LABEL[c]}]({SITE}/{c}/)" for c in LIVE_CATS if c != "watches"] + [f"- [Videos]({SITE}/videos/): YouTube videos", ] + [f"- [{g['meta'].get('title','')}]({SITE}{g['url']}): {g['meta'].get('description','')}" for g in GUIDES] + ([f"- [Wallpapers]({SITE}/wallpapers/): free phone wallpapers"] if WALLS else []) + [f"- [About]({SITE}/about/)", "", "## Watches", ""]
    for w in WATCHES:
        bits = [w.get("ref") if w.get("ref") not in (None, "", "TBD") else None, w["specs"].get("Caliber") if w["specs"].get("Caliber") not in (None, "TBD") else None,
                w["specs"].get("Case") if w["specs"].get("Case") not in (None, "TBD") else None, ("Verdict: " + w["verdict"]) if w.get("verdict") else None]
        L.append(f"- [No. {w['no']} {w['title']}]({SITE}{w['url']})" + (": " + "; ".join(b for b in bits if b) if any(bits) else ""))
    for c in LIVE_CATS:
        if c != "watches":
            L += ["", f"## {CAT_LABEL[c]}", ""] + [f"- [{t['title']}]({SITE}{t['url']})" + (f": {t['line']}" if t.get("line") else "") for t in THINGS[c]]
    if POSTS:
        L[L.index(f"- [About]({SITE}/about/)")] = f"- [Journal]({SITE}/journal/): occasional writing\n- [About]({SITE}/about/)"
        L += ["", "## Journal", ""] + [f"- [{p['title']}]({SITE}{p['url']}) ({p['date'].isoformat()})" for p in POSTS]
    if YT:
        L += ["", "## Elsewhere", "", f"- YouTube: {YT}"]
    open(os.path.join(OUT, "llms.txt"), "w").write("\n".join(L) + "\n")
    open(os.path.join(OUT, "site.webmanifest"), "w").write(json.dumps({"name": NAME, "short_name": NAME, "start_url": "/", "display": "browser",
        "background_color": "#06121c", "theme_color": "#06121c",
        "icons": [{"src": "/icon-192.png", "sizes": "192x192", "type": "image/png"}, {"src": "/icon-512.png", "sizes": "512x512", "type": "image/png"}]}, indent=2))
    open(os.path.join(OUT, "humans.txt"), "w").write(f"Watches, toys and words: {S.get('author','')}\nType: Inter, Newsreader, IBM Plex Mono\n")


def rounded(im, r=0.2):
    """The square icon with rounded corners on a transparent background, for browser tabs."""
    k = 4; big = im.convert("RGBA").resize((im.size[0] * k, im.size[1] * k), Image.LANCZOS)
    mask = Image.new("L", big.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, big.size[0] - 1, big.size[1] - 1], radius=int(big.size[0] * r), fill=255)
    big.putalpha(mask)
    return big.resize(im.size, Image.LANCZOS)


def build_brand_images():
    ip = next((p for p in glob.glob(os.path.join(ROOT, "brand", "icon.*")) if p.lower().endswith(IMG_EXT)), None)
    if ip:  # brand/icon.png: a square logo, full bleed. Home screens round it themselves; tabs get rounded corners here.
        src = ImageOps.exif_transpose(Image.open(ip)).convert("RGB")
        sq = lambda n: src.resize((n, n), Image.LANCZOS)
        for n, name in ((512, "icon-512.png"), (192, "icon-192.png"), (180, "apple-touch-icon.png")):
            sq(n).save(os.path.join(OUT, name))
        for n, name in ((48, "favicon-48.png"), (32, "favicon-32.png")):
            rounded(sq(n * 4)).resize((n, n), Image.LANCZOS).save(os.path.join(OUT, name))
        rounded(sq(256)).save(os.path.join(OUT, "favicon.ico"), sizes=[(16, 16), (32, 32), (48, 48)])
        IMG["brand_icon"] = True
    else:
        for s, name in ((512, "icon-512.png"), (192, "icon-192.png"), (180, "apple-touch-icon.png"), (48, "favicon-48.png"), (32, "favicon-32.png")):
            bezel_icon(s).save(os.path.join(OUT, name))
        bezel_icon(256).save(os.path.join(OUT, "favicon.ico"), sizes=[(16, 16), (32, 32), (48, 48)])
    if not ip:
      open(os.path.join(OUT, "favicon.svg"), "w").write(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" fill="#06121c"/>'
        '<circle cx="32" cy="32" r="22" fill="none" stroke="#dceab9" stroke-width="5.4"/>'
        '<path d="M23.7 13.2h16.6L32 25.7z" fill="#dceab9"/></svg>')
    # the home page photo: brand/hero.jpg if there is one
    hp_ = next((p for p in glob.glob(os.path.join(ROOT, "brand", "hero.*")) if p.lower().endswith(IMG_EXT)), None)
    if hp_:
        im = open_img(hp_)
        hset, (_, hw, hh) = widths(im, "images/desk-dives-desk", [400, 600, 800, 1200, 1600])
        IMG["hero"] = {"img": pick(hset, 800), "srcset": hset, "iw": hw, "ih": hh, "no": "00", "url": "/desk/", "cat": "brand",
                       "title": S.get("hero_caption") or "The desk"}
    # default share image: the desk photo, else the featured watch, else the bezel mark
    f = W_BY.get(S.get("featured"))
    if hp_:
        IMG["og-site"] = og_card(open_img(hp_), "images/og/desk-dives.jpg")
    elif f and f.get("img"):
        IMG["og-site"] = og_card(open_img(os.path.join(f["folder"], f["main_file"])), "images/og/desk-dives.jpg")
    else:
        card = Image.new("RGB", (1200, 630), ABYSS)
        mark = bezel_icon(360)
        card.paste(mark, ((1200 - 360) // 2, (630 - 360) // 2))
        IMG["og-site"] = save(card, "images/og/desk-dives.jpg", quality=86)
    hp = next((p for p in glob.glob(os.path.join(ROOT, "brand", "headshot.*")) if p.lower().endswith(IMG_EXT)), None)
    if hp:
        with Image.open(hp) as im:
            IMG["headshot"] = save(ImageOps.exif_transpose(im).convert("RGBA").resize((240, 240), Image.LANCZOS), "images/headshot.webp")
    ap = next((p for p in glob.glob(os.path.join(ROOT, "brand", "about-*")) if p.lower().endswith(IMG_EXT)), None)
    if ap:
        im = open_img(ap); im.thumbnail((1600, 1600), Image.LANCZOS)
        aset, (_, aw, ah) = widths(im, "images/about", [600, 900, 1300, 1600])
        IMG["about-art"] = (pick(aset, 900), aw, ah, ", ".join(f"{u} {x}w" for u, x in aset))


if __name__ == "__main__":
    if os.path.exists(OUT):
        shutil.rmtree(OUT)
    os.makedirs(OUT)
    IMG = {}
    FONT_URL = {}
    INLINE_CSS = ""
    prepare_fonts_and_css()
    WATCHES = load_watches()
    if not WATCHES:
        fail("There are no watches. Add at least one folder in source/watches.")
    W_BY = {w["slug"]: w for w in WATCHES}
    THINGS = {c: load_things(c) for c, _, _ in CATS if c != "watches"}
    LIVE_CATS = ["watches"] + [c for c, _, _ in CATS if c != "watches" and THINGS[c]]
    ALL = WATCHES + [t for c in LIVE_CATS if c != "watches" for t in THINGS[c]]
    ALL_BY = {}
    for t in ALL:
        if t["slug"] in ALL_BY:
            fail(f"Two folders are both named '{t['slug']}' ({ALL_BY[t['slug']]['cat']} and {t['cat']}). Rename one; folder names must be unique across watches, toys and gear.")
        ALL_BY[t["slug"]] = t
    for w in ALL:
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
            v["poster_jpg"] = save(im, f"images/videos/{vid}.jpg")   # for search results
            v["poster_set"], _ = widths(im, f"images/videos/{vid}", [360, 540, 720])
            v["poster"] = pick(v["poster_set"], 540)
        VIDEOS.append(v)
    # things with a sound-first video (ASMR, squish, clicks): tagged on cards and filterable on The desk
    SOUND = {s for v in VIDEOS if v.get("sound") or re.search(r"\basmr\b", v.get("title", ""), re.I) for s in features(v)}
    for v in VIDEOS:
        for s in features(v):
            if s not in ALL_BY:
                print(f"Note: video '{v['title']}' lists '{s}', which isn't showing on the site. Ignoring that link.")
    POSTS = load_journal()
    WALLS = load_wallpapers()
    GUIDES = load_guides()
    GUIDE_LINKS = guide_links()
    build_brand_images()
    build_home(); build_watches_index(); build_desk()
    for i, w in enumerate(WATCHES):
        build_watch(w, i)
    for c in LIVE_CATS:
        if c != "watches":
            build_category(c)
            for i, t in enumerate(THINGS[c]):
                build_thing(t, i)
    build_videos(); build_journal(); build_wallpapers(); build_guides(); build_about(); build_404(); build_static(); build_redirects()
    nv, np_ = len(VIDEOS), len(POSTS)
    v_word = "video" if nv == 1 else "videos"
    p_word = "journal entry" if np_ == 1 else "journal entries"
    extra = "".join(", " + str(len(THINGS[c])) + " " + (CAT_ONE[c].lower() if len(THINGS[c]) == 1 else c) for c in LIVE_CATS if c != "watches")
    print(f"Built {len(WATCHES)} watches{extra}, {nv} {v_word}, {np_} {p_word} into {OUT}")
