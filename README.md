# deskdives.com

Things on My Desk. Watches, toys, gadgets, and whatever else followed me home.

You run this site entirely from GitHub. You don't need to install anything or edit code. Every time you commit a change, AWS Amplify rebuilds the whole site in about two minutes: every page, image size, share preview, sitemap and search data.

```
source/
  site.json         site-wide settings: tagline, YouTube link, email, featured watch, The math price
  watches/          one folder per watch
    _template/      copy this to add a watch (never published)
    seiko-spb077/
      watch.json    the watch's details and your notes
      main.jpg      the big photo
      dial.jpg ...  any other photos become gallery plates
      figure.jpg    optional watercolor
  toys/             one folder per toy (Godzilla, Star Wars, LEGO...)
    _template/      copy this to add one (never published)
  gear/             one folder per piece of gear (pens, keyboards, mugs...)
    _template/
  videos.json       your YouTube videos, one entry each
  journal/          journal entries, one text file each
    images/         photos used in journal entries
  about.md          the About page
  brand/            about-watercolor.jpg, the art on the About page
  fonts/            the site's fonts, served from your own domain (no need to touch)
  build.py, site.css, site.js, analytics.js   (no need to touch, except analytics.js once)
amplify.yml         tells Amplify how to build
customHttp.yml      caching and security settings
```

## First-time setup

1. Create a GitHub repository (for example `deskdives`) and upload everything in this folder to it: **Add file → Upload files**, drag the contents in, **Commit changes**.
2. In AWS Amplify: **Create new app → GitHub**, pick the repository and the `main` branch, and deploy. Amplify reads `amplify.yml`.
3. **Hosting → Custom domains → Add domain** → `deskdives.com`, including `www`.
4. **Hosting → Rewrites and redirects → Manage redirects → Open text editor**, and paste:

```json
[
  { "source": "https://www.deskdives.com/<*>", "status": "301", "target": "https://deskdives.com/<*>" },
  { "source": "https://www.deskdives.com", "status": "301", "target": "https://deskdives.com" },
  { "source": "/<*>", "status": "404", "target": "/404.html" }
]
```

5. Open `source/site.json` and fill in `youtube` with your channel link (for example `https://www.youtube.com/@yourhandle`) and `email` if you want it shown. YouTube links and the subscribe box stay hidden until `youtube` is filled in.

## Add photos to a watch

Open the watch's folder on GitHub (for example `source/watches/seiko-turtle`), click **Add file → Upload files**, drop the photos in, and commit.

- **main.jpg** is the big photo. If there's no main.jpg, the first photo in name order is used.
- **Any other photo** becomes a gallery plate, in name order. Name them so they sort the way you want: `2-dial.jpg`, `3-lume.jpg`, `4-wrist.jpg`.
- **A photo whose name starts with "figure"** (figure.jpg) shows as a watercolor on that page.
- JPG or PNG, any size up to about 25 MB. The site makes the smaller versions and strips location data automatically.
- To give a photo a caption, add it under `captions` in watch.json: `"captions": { "3-lume.jpg": "Lume, closet, 2 a.m." }`. Without one, the caption is the file name.

To replace a photo, upload a new file with the same name.

## When a watch shows on the site

A watch appears once its folder has **at least one photo** and its watch.json has a real `ref` (not "TBD"). Until then it stays hidden, and the build log lists what each hidden watch still needs, for example `Hidden for now: watches/seiko-spb077 needs a photo`. Set `"draft": true` to hide a finished watch on purpose.

The watch count in the header, the collection and the About page is counted automatically from the watches that are showing. Numbers (No. 01, No. 02…) follow `order`.

Empty fields never show. The writing on each watch page has four parts, and each appears only once you fill it in:

- **Why I bought it**: `take`, one paragraph per line in quotes
- **What I like**: `likes`
- **What annoys me**: `annoyances`
- **Would I buy it again?**: `verdict` and `verdict_note`

Specs left as "TBD" or empty are skipped, and so is `acquired` until you fill it in.

## Add a watch

1. On GitHub, open `source/watches/_template/watch.json` and copy everything in it.
2. Click **Add file → Create new file** and name it `source/watches/citizen-ny0040/watch.json`, using your own folder name: lowercase, with dashes, no spaces. Typing the slash creates the folder. Paste, edit, and commit.
3. Upload photos into the new folder as described above.

## What's in watch.json

```json
"order": 9,                  number on the site: No. 09
"draft": false,              true hides the watch while you work on it
"brand": "Citizen",
"collection": "Promaster",
"type": "Diver's 200 m",
"model": "NY0040",           the giant headline
"ref": "NY0040-09E",
"nickname": "The Fugu",      shows in italics before the line
"line": "One dry sentence.",
"key_numbers": [["42.0","Case mm"],["200","Water res. m"]],   the glowing strip, as many as you like
"specs": { "Caliber": "8203", "Case": "42 mm steel" },        any rows you want, in order
"acquired": "2019, used",
"wrist_rank": 1,             1 shows as P1 · WRIST TIME
"deepest_dive": "The office pool",
"take": ["First paragraph.", "Second paragraph."],   Why I bought it
"likes": ["One thing per line"],
"annoyances": ["One thing per line"],
"verdict": "Yes.",           Would I buy it again?
"verdict_note": "But on the Jubilee this time.",
"paid": 180,                 a number turns on The math. null hides it
"math_quip": "Enough for a dive trip to Belize.",
"captions": {},
"affiliate_url": "",         a link here shows "Where to find one" with a commission note
"affiliate_label": ""
```

Keep the quotes, commas and square brackets as they are. Text in the take, likes and annoyances can use `**bold**`, `*italic*` and `[links](https://...)`.

## Add a toy or a piece of gear

Toys and gear get lighter pages than watches, and every one has the same four parts, so a mug and a fountain pen feel like part of the same site: **What it is**, **Why it's on the desk**, **A few details** (the table) and **Would I buy it again?**

1. On GitHub, open `source/toys/_template/item.json` (or `source/gear/_template/item.json`) and copy everything in it.
2. **Add file → Create new file**, name it `source/toys/godzilla-minus-one/item.json` with your own folder name (lowercase, dashes), paste, edit, and commit.
3. Upload photos into the new folder, the same way as for a watch: `main.jpg` is the big one, the rest become gallery plates.

It shows on the site once it has a `name` and a photo. Every other field is optional and hidden when empty:

```json
"order": 1,                     number within Toys: No. 01
"added": "2026-10-12",          the day it joined the desk, for Latest from the desk
"name": "Godzilla Minus One",   the headline
"maker": "S.H. MonsterArts",
"kind": "Figure",
"line": "One dry sentence.",
"what": "What it is, in a sentence or two.",
"why": ["Why it's on the desk.", "Another paragraph."],
"specs": { "Height": "16 cm" }, A few details: any rows you want
"acquired": "2024",
"verdict": "Yes.",              Would I buy it again?
"verdict_note": "Probably two.",
"captions": {},
"affiliate_url": ""
```

The first toy turns on the **Toys** menu link, the Toys page and the Toys filter on The desk; the same goes for gear. Folder names have to be unique across watches, toys and gear, because a video can feature any of them: in videos.json, list them under `"things": ["godzilla-minus-one"]` (or keep using `"watches"`; either works).

The menu holds five links. Once Toys and Gear are both showing, Nicknames moves out of the menu to keep it on one line on phones. It stays in the footer and at the top of the Watches page.

## The desk and the home page

- **deskdives.com/desk** lists everything, with filter buttons for Watches, Toys and Gear (they appear once a category has something in it).
- **On the desk now** on the home page is `on_desk` in site.json: a list of folder names, from any category, in the order you want. Swap them as things come and go. Mixing categories matters: a row of only watches makes the site read as a watch site.
- **Latest from the desk** on the home page shows the four newest things that have an `added` date (watches can have one too: add `"added": "2026-10-12"` to watch.json). It appears once two things have a date.

## Add a video

Open `source/videos.json`, click the pencil, and add an entry at the top of the list:

```json
{
  "url": "https://youtube.com/shorts/xPnFMMdfSJY",
  "title": "Seiko Great Blue Hole on the wrist",
  "date": "2026-10-10",
  "length": "0:06",
  "summary": "One line about it.",
  "watches": ["seiko-spb083"]
},
```

- `url` is the video's link, copied straight from YouTube's Share button. Regular videos, youtu.be links and Shorts all work.
- Shorts show in a tall 9:16 frame with a SHORT tag.
- `watches` lists the folder names of the watches in the video, so it appears on those watch pages too.
- Optional cover image: upload a JPG named after the video id (the 11 characters after `/shorts/` or `v=`) to `source/videos`, for example `source/videos/xPnFMMdfSJY.jpg`. Without one, YouTube's thumbnail is used.

Videos load from YouTube only when someone presses play, which keeps the site fast.

## Add a wallpaper

1. On your computer, make a folder named for the wallpaper, lowercase with dashes (for example `lume-closeup`), and put the images in it.
2. On GitHub, open `source/wallpapers`, click **Add file → Upload files**, and drag the whole folder in. Name the images `iphone.jpg` and `android.jpg` and the buttons are labeled iPhone and Android. Suggested sizes: 1290 × 2796 for iPhone, 1440 × 3200 for Android.
3. Commit. The Wallpapers page and its footer link ("Free wallpapers") appear automatically. The files are served exactly as uploaded, so they stay sharp. The folder name becomes the title ("lume-closeup" → "Lume closeup").

Downloads are counted in Google Analytics as `wallpaper_download`.

## The Seiko nickname guide

The guide at deskdives.com/seiko-nicknames lives in `source/guides/seiko-nicknames.md`. Edit it like the About page:

- `## Turtle {adopted}` starts an entry. The tag in curly brackets sets the label: `{seiko}` for a Seiko name, `{collector}` for a collector name, `{adopted}` for a collector name Seiko now uses. Entries appear in the jump menu alphabetically.
- Lines like `**Original:** 6217-8000` become the small fact table under the entry.
- `[[mine: seiko-turtle]]` adds an "In my collection" card for that watch folder, with its photo, and the watch page links back to the entry.
- `# Heading` (one #) starts a plain section with no label.

`nav_label: Nicknames` at the top puts the guide in the main menu; `footer_label` sets its footer link. Another file in `source/guides`, for example `seiko-movements.md`, becomes its own page the same way.

## Write a journal entry

1. Open `source/journal/_example-entry.md` and copy it.
2. **Add file → Create new file**, name it `source/journal/2026-11-lume-test.md` (the name becomes the web address), paste, and change the lines between the dashes. Set `draft: false` when it's ready.
3. Write below the dashes. Blank lines separate paragraphs, `## ` starts a subheading, `- ` starts a list item.
4. For photos, upload them to `source/journal/images` and add a line like `![Caption](lume-test.jpg)`.

## Other settings in site.json

- `tagline` and `subline` are the big lines on the home page. `watch_tagline` opens the Watches page. `description` is what Google and link previews show for the home page, and `home_title` is the home page's title in Google. `dateline` is the small line under the masthead, after the count of things.
- `videos_sub` and `journal_sub` are the one-line intros for videos and the journal. `sections` holds the intro line for the Toys and Gear pages.
- **The site icon** (browser tab, home screen, bookmarks) is `source/brand/icon.png`: a square logo, edge to edge, at least 512 × 512. The build makes every size from it and rounds the corners for browser tabs. Upload a new icon.png to change it.
- **The big home page photo** is `source/brand/hero.jpg`, a photo of the desk itself, with `hero_caption` under it. It's also the picture that shows when someone shares the home page. To change it, upload a new hero.jpg. Without one, the home page shows `featured` instead.
- `featured` is the watch (or toy or gear) shown large on the home page when there's no hero.jpg, and its photo becomes the site's default share image. `on_wrist` is the "On the wrist this week" watch. Both use folder names.
- `benchmark` is the Rolex price used in The math. Update `price` and `note` when Rolex changes its prices.

## The About page

Edit `source/about.md`. Write `{count}` anywhere and it becomes the number of watches on the site in words ("five"), or `{number}` for digits. `most_worn` and `grail` show in the logbook only when filled in.

## The journal

The Journal link and home page box stay hidden until you publish your first entry.

## Google Analytics

Open `source/analytics.js`, paste your Measurement ID (`G-XXXXXXXXXX`) between the quotes on the `GA_MEASUREMENT_ID` line, and commit. Besides page views, it records video plays, shares, YouTube clicks and affiliate clicks.

## Sharing and search

Every watch page gets its own share image: the main photo in a logbook frame on abyss blue. It shows when the link is posted to Messages, Facebook, X, Slack or anywhere else. Pin links are on every watch page. The sitemap, structured data, robots.txt and llms.txt rebuild automatically. After launch, add the site to Google Search Console and Bing Webmaster Tools and submit `https://deskdives.com/sitemap.xml`.

## If a build fails

The live site stays exactly as it was. In Amplify, open the failed build and read the last lines of the log. It says what to fix, for example:

```
BUILD STOPPED: watches/citizen-ny0040/watch.json has a typo on line 12: Expecting ',' delimiter.
```

That almost always means a missing comma or quote on or just above that line.
