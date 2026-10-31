#!/usr/bin/env python3
"""Build Brian Dominguez's website into docs/ from data/site.json and data/titles.json.

Standard library only:  python3 build.py
Preview:                python3 -m http.server -d docs 8000

Every page is plain HTML that reads without scripts. Each one carries schema.org
JSON-LD and a Markdown twin (index.md) for AI agents. The build also writes
llms.txt, llms-full.txt, audiobooks.json, sitemap.xml and robots.txt.
"""
from __future__ import annotations

import hashlib
import html
import json
import math
import re
import shutil
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
OUT = ROOT / "docs"

# Crawlers named in robots.txt once the site launches. Training crawlers are
# welcome on purpose: the point is for search engines and assistants to know Brian's work.
CRAWLERS = [
    ("Search engines", ["Googlebot", "Bingbot", "DuckDuckBot", "Applebot"]),
    ("AI search and assistants fetching pages for people",
     ["OAI-SearchBot", "ChatGPT-User", "Claude-SearchBot", "Claude-User", "PerplexityBot", "Perplexity-User"]),
    ("AI model training", ["GPTBot", "ClaudeBot", "Google-Extended", "Applebot-Extended"]),
]


# ---------------------------------------------------------------- helpers

def esc(value) -> str:
    return html.escape(str(value), quote=True)


def length(minutes: int) -> str:
    hours, mins = divmod(minutes, 60)
    if hours and mins:
        return f"{hours} hr {mins} min"
    return f"{hours} hr" if hours else f"{mins} min"


def iso_duration(minutes: int) -> str:
    hours, mins = divmod(minutes, 60)
    return "PT" + (f"{hours}H" if hours else "") + (f"{mins}M" if mins or not hours else "")


def long_date(iso: str) -> str:
    d = date.fromisoformat(iso)
    return f"{d:%B} {d.day}, {d.year}"


def clip(text: str, limit: int) -> str:
    """Whole sentences that fit in `limit` characters, else the first words and an ellipsis."""
    out = ""
    for part in re.split(r"(?<=[.!?])\s+", text):
        if len(out) + len(part) + 1 > limit:
            break
        out = f"{out} {part}".strip()
    return out or text[: limit - 1].rsplit(" ", 1)[0].rstrip(",;:") + "…"


def and_list(names: list[str]) -> str:
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]


# Summaries in titles.json are light Markdown: paragraphs split by blank lines, list items as "- item".
def summary_blocks(text: str) -> list[tuple[str, object]]:
    blocks = []
    for block in text.split("\n\n"):
        lines = block.split("\n")
        if all(line.startswith("- ") for line in lines):
            blocks.append(("ul", [line[2:] for line in lines]))
        else:
            blocks.append(("p", " ".join(lines)))
    return blocks


def summary_html(text: str) -> str:
    out = []
    for kind, content in summary_blocks(text):
        if kind == "ul":
            out.append("<ul>" + "".join(f"<li>{esc(item)}</li>" for item in content) + "</ul>")
        else:
            out.append(f"<p>{esc(content)}</p>")
    return "\n    ".join(out)


def summary_flat(text: str) -> str:
    parts = []
    for kind, content in summary_blocks(text):
        if kind == "ul":
            parts += [item if item[-1:] in ".!?;:" else item + ";" for item in content]
        else:
            parts.append(content)
    return " ".join(parts)


def waveform(bars: int, height: int, cls: str) -> str:
    """A fixed, speech-like waveform: louder in the middle, uneven like a voice."""
    width, gap = 4, 3
    rects = []
    for i in range(bars):
        envelope = 0.45 + 0.55 * math.sin(math.pi * (i + 0.5) / bars)
        texture = 0.3 + 0.7 * abs(math.sin(i * 1.71) * math.cos(i * 0.43 + 0.6))
        h = max(4, round(height * envelope * texture))
        rects.append(f'<rect x="{i * (width + gap)}" y="{(height - h) / 2:g}" width="{width}" height="{h}" rx="2"/>')
    total = bars * (width + gap) - gap
    return (f'<svg class="{cls}" viewBox="0 0 {total} {height}" aria-hidden="true" focusable="false">'
            + "".join(rects) + "</svg>")


# ---------------------------------------------------------------- the site

class Site:
    def __init__(self) -> None:
        self.cfg = json.loads((ROOT / "data" / "site.json").read_text())
        self.titles = json.loads((ROOT / "data" / "titles.json").read_text())
        self.titles.sort(key=lambda t: t["release_date"], reverse=True)
        self.base = self.cfg["base_url"].rstrip("/")
        self.draft = bool(self.cfg.get("draft", True))
        self.name = self.cfg["name"]
        self.by_slug = {t["slug"]: t for t in self.titles}
        self.person_id = f"{self.base}/#person"
        self.website_id = f"{self.base}/#website"
        self.pages: list[str] = []  # canonical URLs for the sitemap
        self.css_version = ""

    # -- text from config, with {count} filled in
    def fill(self, text: str) -> str:
        words = {14: "fourteen", 15: "fifteen", 16: "sixteen", 17: "seventeen", 18: "eighteen"}
        return text.replace("{count}", words.get(len(self.titles), str(len(self.titles))))

    def series_titles(self, slug: str) -> list[dict]:
        found = [t for t in self.titles if t["series"] and t["series"]["slug"] == slug]
        return sorted(found, key=lambda t: t["series"]["position"])

    def url(self, path: str) -> str:
        return self.base + path

    # -- structured data
    def person(self) -> dict:
        contact = self.cfg.get("contact") or {}
        node = {
            "@type": "Person",
            "@id": self.person_id,
            "name": self.name,
            "jobTitle": self.cfg["role"],
            "description": self.fill(self.cfg["bio_short"]),
            "url": f"{self.base}/",
            "knowsLanguage": "en",
            "hasOccupation": {"@type": "Occupation", "name": self.cfg["role"]},
            "sameAs": self.cfg["same_as"] + [u for u in [contact.get("acx_profile")] if u],
        }
        if contact.get("email"):
            node["email"] = f"mailto:{contact['email']}"
        if self.cfg.get("photo"):
            node["image"] = self.url("/" + self.cfg["photo"].lstrip("/"))
        return node

    def website(self) -> dict:
        return {
            "@type": "WebSite",
            "@id": self.website_id,
            "url": f"{self.base}/",
            "name": f"{self.name}, {self.cfg['role'].lower()}",
            "inLanguage": "en",
            "publisher": {"@id": self.person_id},
        }

    def audiobook(self, t: dict) -> dict:
        page = self.url(f"/audiobooks/{t['slug']}/")
        node = {
            "@type": "Audiobook",
            "@id": f"{page}#audiobook",
            "url": page,
            "name": t["title"],
            "author": [{"@id": self.person_id} if a == self.name else {"@type": "Person", "name": a}
                       for a in t["authors"]],
            "readBy": {"@id": self.person_id},
            "publisher": {"@type": "Organization", "name": t["publisher"]},
            "datePublished": t["release_date"],
            "duration": iso_duration(t["runtime_min"]),
            "inLanguage": t["language"],
            "bookFormat": "https://schema.org/AudiobookFormat",
            "abridged": False,
            "genre": t["genre"],
            "image": t["cover_1024"],
            "description": clip(summary_flat(t["summary"]), 300),
            "sameAs": [u for u in (t["audible_url"], t["apple_url"], t["amazon_url"]) if u and "/s?" not in u],
        }
        if t.get("subtitle"):
            node["alternativeHeadline"] = t["subtitle"]
        if t.get("sample_url"):
            node["audio"] = {"@type": "AudioObject", "contentUrl": t["sample_url"],
                             "encodingFormat": "audio/mpeg", "name": f"Sample of {t['title']}"}
        if t.get("series"):
            node["isPartOf"] = {"@id": self.url(f"/series/{t['series']['slug']}/#series")}
            node["position"] = t["series"]["position"]
        return node

    def breadcrumbs(self, page: str, trail: list[tuple[str, str]]) -> dict:
        return {
            "@type": "BreadcrumbList",
            "@id": f"{page}#breadcrumb",
            "itemListElement": [{"@type": "ListItem", "position": i, "name": name, "item": link}
                                for i, (name, link) in enumerate(trail, 1)],
        }

    # -- page shell
    def page(self, *, path: str, depth: int, title: str, description: str, body: str,
             graph: list[dict], image: str | None = None, og_type: str = "website",
             root_relative: bool = False, listed: bool = True) -> str:
        # Relative links keep the site working at user.github.io/repo/ before the domain exists;
        # the 404 page is served at any depth, so it links from the root instead.
        up = "/" if root_relative else "../" * depth
        home = "/" if root_relative else (up or "./")
        canonical = self.url(path)
        robots = "noindex, nofollow" if self.draft else "index, follow, max-image-preview:large"
        image = image or self.url("/og.png")
        ld = json.dumps({"@context": "https://schema.org", "@graph": graph}, ensure_ascii=False, indent=1)
        ld = ld.replace("</", "<\\/")
        me_links = "\n".join(f'<link rel="me" href="{esc(u)}">' for u in self.cfg["same_as"])
        banner = ('<div class="draft-banner" role="note">Draft for Brian\'s review. Not published, '
                  'and search engines are asked to stay away until it launches.</div>\n') if self.draft else ""
        markdown_twin = '<link rel="alternate" type="text/markdown" href="index.md">\n' if listed else ""
        if listed:
            self.pages.append(canonical)
        return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(description)}">
<meta name="author" content="{esc(self.name)}">
<meta name="robots" content="{robots}">
<link rel="canonical" href="{esc(canonical)}">
<meta name="color-scheme" content="light dark">
<meta name="theme-color" content="#f6f2ea" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#14120f" media="(prefers-color-scheme: dark)">
<meta property="og:type" content="{og_type}">
<meta property="og:site_name" content="{esc(self.name)}">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(description)}">
<meta property="og:url" content="{esc(canonical)}">
<meta property="og:image" content="{esc(image)}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="{up}favicon.svg" type="image/svg+xml">
<link rel="stylesheet" href="{up}style.css?v={self.css_version}">
{markdown_twin}<link rel="describedby" type="text/markdown" href="{up}llms.txt">
{me_links}
<script type="application/ld+json">
{ld}
</script>
</head>
<body>
<a class="skip" href="#main">Skip to content</a>
{banner}<header class="site-header">
  <div class="wrap header-inner">
    <a class="brand" href="{home}">{waveform(7, 22, "brand-wave")}<span>{esc(self.name)}</span></a>
    <nav aria-label="Main">
      <a href="{home}#audiobooks">Audiobooks</a>
      <a href="{up}series/the-disavowed/">The Disavowed</a>
      <a href="{up}for-authors/">For authors</a>
      <a href="{home}#about">About</a>
    </nav>
  </div>
</header>
<main id="main">
{body}
</main>
<footer class="site-footer">
  <div class="wrap">
    <p class="footer-name">{esc(self.name)} · {esc(self.cfg['role'])}</p>
    <p><a href="{esc(self.cfg['same_as'][0])}">All his titles on Audible</a> · <a href="{up}for-authors/">Narration for authors</a> · <a href="{up}llms.txt">llms.txt</a> · <a href="{up}audiobooks.json">Catalogue as JSON</a></p>
    <p class="fineprint">Cover art, summaries and audio samples belong to each book's rights holder and appear here to promote the audiobooks. Updated {long_date(self.cfg['updated'])}.</p>
  </div>
</footer>
</body>
</html>
"""

    # -- shared pieces
    def stores(self, t: dict) -> str:
        audible = t.get("audible_bounty_url") or t["audible_url"]
        links = [f'<a class="btn btn-primary" href="{esc(audible)}">Listen on Audible</a>']
        if t.get("apple_url"):
            links.append(f'<a class="btn" href="{esc(t["apple_url"])}">Apple Books</a>')
        links.append(f'<a class="btn" href="{esc(t["amazon_url"])}">Amazon</a>')
        return '<div class="stores">' + "".join(links) + "</div>"

    def card(self, t: dict, up: str) -> str:
        href = f"{up}audiobooks/{t['slug']}/"
        return f"""<article class="card">
  <a class="cover-link" href="{href}" tabindex="-1" aria-hidden="true"><img class="cover" src="{esc(t['cover_500'])}" alt="" width="500" height="500" loading="lazy" decoding="async"></a>
  <p class="card-kicker">{esc(t['genre'])}</p>
  <h3 class="card-title"><a href="{href}">{esc(t['title'])}</a></h3>
  <p class="card-meta">{esc(and_list(t['authors']))} · {length(t['runtime_min'])}</p>
</article>"""

    # -- pages
    def home(self) -> tuple[str, str]:
        cfg = self.cfg
        series = self.series_titles(cfg["featured"]["series"])
        own = self.by_slug[cfg["featured"]["own_book"]]
        series_minutes = sum(t["runtime_min"] for t in series)
        opener = clip(summary_flat(series[0]["summary"]), 120) if series else ""
        shelf = "".join(
            f'<li><a href="audiobooks/{t["slug"]}/"><img src="{esc(t["cover_500"])}" alt="Cover of {esc(t["title"])}" '
            f'width="500" height="500" loading="lazy" decoding="async"><span class="num">Book {t["series"]["position"]}</span></a></li>'
            for t in series)
        fiction = "\n".join(self.card(t, "") for t in self.titles if t["kind"] == "fiction")
        nonfiction = "\n".join(self.card(t, "") for t in self.titles if t["kind"] == "nonfiction")
        bio = "\n".join(f"<p>{esc(self.fill(p))}</p>" for p in cfg["bio"])
        count = self.fill("{count}").capitalize()
        body = f"""<section class="hero">
  <div class="wrap">
    <p class="eyebrow">{esc(cfg['role'])}</p>
    <h1>{esc(self.name)}</h1>
    <p class="lede">{count} audiobooks on Audible since 2025: an espionage series, science fiction, family drama and practical nonfiction, plus a book of his own.</p>
    <div class="actions">
      <a class="btn btn-primary" href="#audiobooks">Browse the audiobooks</a>
      <a class="btn" href="for-authors/">Narration for authors</a>
    </div>
    {waveform(72, 72, "hero-wave")}
  </div>
</section>

<section class="feature-series" aria-labelledby="series-heading">
  <div class="wrap feature-series-inner">
    <div>
      <p class="eyebrow">A series in one voice</p>
      <h2 id="series-heading">The Disavowed</h2>
      <p>Tobey Alvarez's espionage series, books 1 to {len(series)}, all narrated by Brian: {length(series_minutes)} of listening.</p>
      <p class="quote">{esc(opener)}</p>
      <div class="actions"><a class="btn btn-primary" href="series/the-disavowed/">See the series</a></div>
    </div>
    <ol class="shelf">{shelf}</ol>
  </div>
</section>

<section class="feature-own" aria-labelledby="own-heading">
  <div class="wrap feature-own-inner">
    <a href="audiobooks/{own['slug']}/"><img class="feature-cover" src="{esc(own['cover_500'])}" alt="Cover of {esc(own['title'])}" width="500" height="500" loading="lazy" decoding="async"></a>
    <div>
      <p class="eyebrow">Written and narrated by Brian</p>
      <h2 id="own-heading">{esc(own['title'])}</h2>
      {summary_html(own['summary'])}
      <p class="meta">{length(own['runtime_min'])} · {esc(cfg['featured']['own_book_note'])}</p>
      {self.stores(own)}
    </div>
  </div>
</section>

<section id="audiobooks" class="catalogue" aria-labelledby="catalogue-heading">
  <div class="wrap">
    <h2 id="catalogue-heading">All audiobooks</h2>
    <p class="section-lede">Newest first. Every page has a sample to play.</p>
    <h3 class="group-heading">Fiction</h3>
    <div class="grid">
{fiction}
    </div>
    <h3 class="group-heading">Nonfiction</h3>
    <div class="grid">
{nonfiction}
    </div>
  </div>
</section>

<section id="about" class="about" aria-labelledby="about-heading">
  <div class="wrap about-inner">
    <h2 id="about-heading">About Brian</h2>
{bio}
    <p><a class="text-link" href="for-authors/">Narration for authors →</a></p>
  </div>
</section>"""
        graph = [
            self.website(),
            self.person(),
            {
                "@type": "ProfilePage",
                "@id": f"{self.base}/#profilepage",
                "url": f"{self.base}/",
                "name": f"{self.name}, {cfg['role'].lower()}",
                "isPartOf": {"@id": self.website_id},
                "mainEntity": {"@id": self.person_id},
                "dateModified": cfg["updated"],
            },
            {
                "@type": "ItemList",
                "@id": f"{self.base}/#audiobooks",
                "name": f"Audiobooks narrated by {self.name}",
                "numberOfItems": len(self.titles),
                "itemListElement": [{"@type": "ListItem", "position": i, "url": self.url(f"/audiobooks/{t['slug']}/"),
                                     "name": t["title"]} for i, t in enumerate(self.titles, 1)],
            },
        ]
        page_html = self.page(path="/", depth=0, title=f"{self.name}, {cfg['role'].lower()}",
                              description=cfg["description"], body=body, graph=graph, og_type="profile")
        md = [f"# {self.name}, {cfg['role'].lower()}", ""]
        md += [self.fill(p) + "\n" for p in cfg["bio"]]
        md += [f"## Audiobooks narrated by {self.name}", ""]
        md += [self.md_line(t) for t in self.titles]
        md += ["", "## More", "",
               f"- [The Disavowed series]({self.url('/series/the-disavowed/index.md')}): books 1 to {len(series)}, in order",
               f"- [Narration for authors]({self.url('/for-authors/index.md')}): what he narrates and how to reach him",
               f"- [All his titles on Audible]({cfg['same_as'][0]})", ""]
        return page_html, "\n".join(md)

    def md_line(self, t: dict) -> str:
        series = f", book {t['series']['position']} of {t['series']['name']}" if t.get("series") else ""
        link = self.url("/audiobooks/" + t["slug"] + "/index.md")
        return (f"- [{t['title']}]({link}): by {and_list(t['authors'])}; {t['genre'].lower()}{series}; "
                f"{length(t['runtime_min'])}; released {long_date(t['release_date'])}")

    def title_page(self, t: dict) -> tuple[str, str]:
        page = self.url(f"/audiobooks/{t['slug']}/")
        series = t.get("series")
        eyebrow = esc(t["genre"])
        if series:
            eyebrow += f' · <a href="../../series/{series["slug"]}/">Book {series["position"]} of {esc(series["name"])}</a>'
        authors = and_list(t["authors"])
        own = t["authors"] == [self.name]
        byline = (f"Written and narrated by <a href=\"../../\">{esc(self.name)}</a>" if own else
                  f"Written by {esc(authors)} · Narrated by <a href=\"../../\">{esc(self.name)}</a>")
        sample = ""
        if t.get("sample_url"):
            sample = f"""<figure class="sample">
      <figcaption>Hear a sample</figcaption>
      <audio controls preload="none" src="{esc(t['sample_url'])}">Your browser can't play this sample. <a href="{esc(t['audible_url'])}">Hear it on Audible</a>.</audio>
    </figure>"""
        subtitle = f'<p class="subtitle">{esc(t["subtitle"])}</p>' if t.get("subtitle") else ""
        if series:
            more = [x for x in self.series_titles(series["slug"]) if x is not t]
        else:
            more = [x for x in self.titles if x is not t and x["kind"] == t["kind"] and not x.get("series")]
            more += [x for x in self.titles if x is not t and x not in more]
        more_cards = "\n".join(self.card(x, "../../") for x in more[:4])
        more_heading = f"More of {esc(series['name'])}" if series else "More narrated by Brian"
        body = f"""<nav class="crumbs wrap" aria-label="Breadcrumb"><a href="../../">Home</a> <span aria-hidden="true">/</span> <a href="../../#audiobooks">Audiobooks</a> <span aria-hidden="true">/</span> <span aria-current="page">{esc(t['title'])}</span></nav>
<article class="title-page wrap">
  <div class="title-cover"><img src="{esc(t['cover_1024'])}" alt="Cover of {esc(t['title'])}" width="1024" height="1024" decoding="async"></div>
  <div class="title-main">
    <p class="eyebrow">{eyebrow}</p>
    <h1>{esc(t['title'])}</h1>
    {subtitle}
    <p class="byline">{byline}</p>
    <dl class="facts">
      <div><dt>Length</dt><dd>{length(t['runtime_min'])}</dd></div>
      <div><dt>Released</dt><dd>{long_date(t['release_date'])}</dd></div>
      <div><dt>Publisher</dt><dd>{esc(t['publisher'])}</dd></div>
      <div><dt>Language</dt><dd>English, unabridged</dd></div>
    </dl>
    {sample}
    {self.stores(t)}
    <h2>About the book</h2>
    {summary_html(t['summary'])}
    <p class="source">Summary from the publisher.</p>
  </div>
</article>
<section class="more wrap" aria-labelledby="more-heading">
  <h2 id="more-heading">{more_heading}</h2>
  <div class="grid">
{more_cards}
  </div>
</section>"""
        trail = [("Home", f"{self.base}/"), ("Audiobooks", f"{self.base}/#audiobooks"), (t["title"], page)]
        graph = [
            self.website(),
            self.person(),
            self.audiobook(t),
            {"@type": "ItemPage", "@id": f"{page}#webpage", "url": page, "name": f"{t['title']}, narrated by {self.name}",
             "isPartOf": {"@id": self.website_id}, "mainEntity": {"@id": f"{page}#audiobook"},
             "breadcrumb": {"@id": f"{page}#breadcrumb"}},
            self.breadcrumbs(page, trail),
        ]
        if series:
            graph.append(self.series_node(series["slug"]))
        description = clip(f"{t['title']} by {authors}, narrated by {self.name}. {clip(summary_flat(t['summary']), 160)}", 158)
        page_html = self.page(path=f"/audiobooks/{t['slug']}/", depth=2, title=f"{t['title']}, narrated by {self.name}",
                              description=description, body=body, graph=graph, image=t.get("share_image") or t["cover_1024"],
                              og_type="book")
        md = [f"# {t['title']}", ""]
        if t.get("subtitle"):
            md += [f"*{t['subtitle']}*", ""]
        md += [f"- Written by: {authors}", f"- Narrated by: {self.name}", f"- Genre: {t['genre']}"]
        if series:
            md.append(f"- Series: {series['name']}, book {series['position']}")
        md += [f"- Length: {length(t['runtime_min'])}", f"- Released: {long_date(t['release_date'])}",
               f"- Publisher: {t['publisher']}", "- Language: English, unabridged",
               f"- Listen: [Audible]({t.get('audible_bounty_url') or t['audible_url']})"
               + (f", [Apple Books]({t['apple_url']})" if t.get("apple_url") else "") + f", [Amazon]({t['amazon_url']})"]
        if t.get("sample_url"):
            md.append(f"- Sample: {t['sample_url']}")
        md += ["", "## About the book", "", t["summary"], "", "Summary from the publisher.", ""]
        return page_html, "\n".join(md)

    def series_node(self, slug: str) -> dict:
        books = self.series_titles(slug)
        return {
            "@type": "BookSeries",
            "@id": self.url(f"/series/{slug}/#series"),
            "url": self.url(f"/series/{slug}/"),
            "name": books[0]["series"]["name"],
            "author": [{"@type": "Person", "name": a} for a in books[0]["authors"]],
            "hasPart": [{"@type": "Audiobook", "@id": self.url(f"/audiobooks/{t['slug']}/#audiobook"),
                         "name": t["title"], "url": self.url(f"/audiobooks/{t['slug']}/"),
                         "position": t["series"]["position"]} for t in books],
        }

    def series_page(self, slug: str) -> tuple[str, str]:
        books = self.series_titles(slug)
        name = books[0]["series"]["name"]
        author = and_list(books[0]["authors"])
        page = self.url(f"/series/{slug}/")
        items = "\n".join(f"""<li class="series-item">
    <a href="../../audiobooks/{t['slug']}/" tabindex="-1" aria-hidden="true"><img src="{esc(t['cover_500'])}" alt="" width="500" height="500" loading="lazy" decoding="async"></a>
    <div>
      <p class="eyebrow">Book {t['series']['position']}</p>
      <h2><a href="../../audiobooks/{t['slug']}/">{esc(t['title'])}</a></h2>
      <p class="card-meta">{length(t['runtime_min'])} · Released {long_date(t['release_date'])}</p>
      <p>{esc(clip(summary_flat(t['summary']), 220))}</p>
    </div>
  </li>""" for t in books)
        total = sum(t["runtime_min"] for t in books)
        body = f"""<nav class="crumbs wrap" aria-label="Breadcrumb"><a href="../../">Home</a> <span aria-hidden="true">/</span> <span aria-current="page">{esc(name)}</span></nav>
<section class="wrap series-page">
  <p class="eyebrow">Espionage thriller series by {esc(author)}</p>
  <h1>{esc(name)}</h1>
  <p class="lede">Books 1 to {len(books)}, all narrated by {esc(self.name)}: {length(total)} in one voice. Start with book 1.</p>
  <ol class="series-list">
  {items}
  </ol>
</section>"""
        trail = [("Home", f"{self.base}/"), (name, page)]
        graph = [self.website(), self.person(), self.series_node(slug), self.breadcrumbs(page, trail)]
        graph += [self.audiobook(t) for t in books]
        page_html = self.page(path=f"/series/{slug}/", depth=2, title=f"{name} audiobooks, narrated by {self.name}",
                              description=clip(f"{name}, the espionage series by {author}: books 1 to {len(books)} as audiobooks, "
                                               f"all narrated by {self.name}. {length(total)} of listening.", 158),
                              body=body, graph=graph, image=books[0].get("share_image"))
        md = [f"# {name}", "", f"Espionage thriller series by {author}. Books 1 to {len(books)} are audiobooks narrated by {self.name}, "
              f"{length(total)} in all.", ""]
        md += [self.md_line(t) for t in books] + [""]
        return page_html, "\n".join(md)

    def authors_page(self) -> tuple[str, str]:
        contact = self.cfg.get("contact") or {}
        fiction = [t for t in self.titles if t["kind"] == "fiction"]
        nonfiction = [t for t in self.titles if t["kind"] == "nonfiction"]
        series = self.series_titles("the-disavowed")
        genres_nf = sorted({t["genre"].lower() for t in nonfiction})
        reach = []
        if contact.get("email"):
            reach.append(f'<a class="btn btn-primary" href="mailto:{esc(contact["email"])}">Email Brian</a>')
        if contact.get("acx_profile"):
            reach.append(f'<a class="btn" href="{esc(contact["acx_profile"])}">Brian on ACX</a>')
        reach_html = ('<div class="actions">' + "".join(reach) + "</div>") if reach else \
            '<p class="todo">Contact to come: Brian\'s email address or ACX profile link.</p>'
        picks = [self.by_slug[s] for s in ("the-disavowed-the-ninth-division", "whats-so-special-about-rome", "sam-on-the-way")
                 if s in self.by_slug]
        body = f"""<section class="wrap prose-page">
  <p class="eyebrow">For authors</p>
  <h1>Narration for authors</h1>
  <p class="lede">Brian narrates for independent authors through ACX, Audible's marketplace for audiobook production.</p>
  <h2>What he has narrated</h2>
  <ul>
    <li><strong>{len(fiction)} fiction titles:</strong> all {len(series)} books of the espionage series <a href="../series/the-disavowed/">The Disavowed</a>, a science-fiction story collection and a family drama.</li>
    <li><strong>{len(nonfiction)} nonfiction titles:</strong> {esc(and_list(genres_nf))}.</li>
  </ul>
  <h2>Series work</h2>
  <p>He recorded books 1 to {len(series)} of Tobey Alvarez's The Disavowed, so listeners hear one voice from the first book to the latest.</p>
  <h2>Hear him first</h2>
  <p>Every audiobook page here has a sample to play. Three places to start:</p>
  <ul>{''.join(f'<li><a href="../audiobooks/{t["slug"]}/">{esc(t["title"])}</a>, {esc(t["genre"].lower())}</li>' for t in picks)}</ul>
  <h2>Get in touch</h2>
  {reach_html}
</section>"""
        page = self.url("/for-authors/")
        service = {"@type": "Service", "@id": f"{page}#service", "serviceType": "Audiobook narration",
                   "name": f"Audiobook narration by {self.name}", "provider": {"@id": self.person_id},
                   "areaServed": "Worldwide", "url": page}
        graph = [self.website(), self.person(), service,
                 {"@type": "WebPage", "@id": f"{page}#webpage", "url": page, "name": "Narration for authors",
                  "isPartOf": {"@id": self.website_id}, "about": {"@id": self.person_id},
                  "mainEntity": {"@id": f"{page}#service"}}]
        page_html = self.page(path="/for-authors/", depth=1, title=f"Narration for authors · {self.name}",
                              description=f"{self.name} narrates audiobooks for independent authors through ACX: "
                                          f"thrillers, series fiction and nonfiction. Hear samples and get in touch.",
                              body=body, graph=graph)
        md = ["# Narration for authors", "",
              f"{self.name} narrates for independent authors through ACX, Audible's marketplace for audiobook production.", "",
              f"- Fiction: {len(fiction)} titles, including all {len(series)} books of The Disavowed",
              f"- Nonfiction: {len(nonfiction)} titles: {and_list(genres_nf)}"]
        if contact.get("email"):
            md.append(f"- Email: {contact['email']}")
        if contact.get("acx_profile"):
            md.append(f"- ACX profile: {contact['acx_profile']}")
        md.append("")
        return page_html, "\n".join(md)

    def not_found(self) -> str:
        body = """<section class="wrap prose-page">
  <p class="eyebrow">Page not found</p>
  <h1>That page isn't here</h1>
  <p class="lede">Try the <a href="/">home page</a> or the <a href="/#audiobooks">list of audiobooks</a>.</p>
</section>"""
        return self.page(path="/404.html", depth=0, title=f"Not found · {self.name}",
                         description="This page doesn't exist.", body=body, graph=[self.website(), self.person()],
                         root_relative=True, listed=False)

    # -- files for crawlers and agents
    def robots(self) -> str:
        if self.draft:
            return ("# Draft: closed to crawlers until launch.\n"
                    "# Set \"draft\": false in data/site.json and rebuild to open it.\n"
                    "User-agent: *\nDisallow: /\n")
        lines = ["# Search engines and AI assistants are welcome here.", ""]
        for heading, agents in CRAWLERS:
            lines.append(f"# {heading}")
            lines += [f"User-agent: {a}" for a in agents]
            lines += ["Allow: /", ""]
        lines += ["User-agent: *", "Allow: /", "", f"Sitemap: {self.url('/sitemap.xml')}", ""]
        return "\n".join(lines)

    def sitemap(self) -> str:
        rows = "".join(f"  <url><loc>{esc(u)}</loc><lastmod>{self.cfg['updated']}</lastmod></url>\n" for u in self.pages)
        return ('<?xml version="1.0" encoding="UTF-8"?>\n'
                '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + rows + "</urlset>\n")

    def llms(self) -> str:
        series = self.series_titles("the-disavowed")
        lines = [f"# {self.name}", "",
                 f"> {self.fill(self.cfg['bio_short'])}", "",
                 "Each audiobook page lists the author, length, release date, publisher, a sample and store links "
                 "(Audible, Apple Books, Amazon). Facts come from Audible's catalogue. Every page has a Markdown "
                 "twin at index.md, linked below.", "",
                 "## Audiobooks", ""]
        lines += [self.md_line(t) for t in self.titles]
        lines += ["", "## About", "",
                  f"- [About {self.name}]({self.url('/index.md')}): bio and full list of titles",
                  f"- [The Disavowed]({self.url('/series/the-disavowed/index.md')}): books 1 to {len(series)}, in order",
                  f"- [Narration for authors]({self.url('/for-authors/index.md')}): what he narrates and how to reach him",
                  "", "## Optional", "",
                  f"- [Catalogue as JSON]({self.url('/audiobooks.json')}): the same facts, machine-readable",
                  f"- [Everything in one file]({self.url('/llms-full.txt')}): all pages as Markdown", ""]
        return "\n".join(lines)

    def catalogue_json(self) -> str:
        return json.dumps({
            "narrator": {"name": self.name, "role": self.cfg["role"], "url": f"{self.base}/",
                         "same_as": self.cfg["same_as"]},
            "updated": self.cfg["updated"],
            "audiobooks": [{
                "title": t["title"], "subtitle": t.get("subtitle"), "authors": t["authors"],
                "narrators": [self.name], "publisher": t["publisher"], "released": t["release_date"],
                "length_minutes": t["runtime_min"], "genre": t["genre"], "series": t.get("series"),
                "language": t["language"], "page": self.url(f"/audiobooks/{t['slug']}/"),
                "audible": t["audible_url"], "apple_books": t.get("apple_url"), "amazon": t["amazon_url"],
                "sample": t.get("sample_url"),
            } for t in self.titles],
        }, indent=2, ensure_ascii=False) + "\n"

    # -- build
    def launch_problems(self) -> list[str]:
        contact = self.cfg.get("contact") or {}
        problems = []
        if not (contact.get("email") or contact.get("acx_profile")):
            problems.append("contact: add an email address or an ACX profile link")
        if not self.cfg.get("cname"):
            problems.append("cname: set the registered domain")
        if self.cfg.get("cname") and self.cfg["cname"] not in self.base:
            problems.append("base_url: must use the domain in cname")
        return problems

    def build(self) -> None:
        if not self.draft and (problems := self.launch_problems()):
            sys.exit("Not ready to launch:\n  " + "\n  ".join(problems))
        if OUT.exists():
            shutil.rmtree(OUT)
        OUT.mkdir()
        for name in ("style.css", "favicon.svg", "og.png"):
            if (SRC / name).exists():
                shutil.copy2(SRC / name, OUT / name)
        self.css_version = hashlib.sha256((SRC / "style.css").read_bytes()).hexdigest()[:10]

        def write(path: str, text: str) -> None:
            target = OUT / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text)

        full = []
        page_html, md = self.home()
        write("index.html", page_html); write("index.md", md); full.append(md)
        for t in self.titles:
            page_html, md = self.title_page(t)
            write(f"audiobooks/{t['slug']}/index.html", page_html); write(f"audiobooks/{t['slug']}/index.md", md)
            full.append(md)
        page_html, md = self.series_page("the-disavowed")
        write("series/the-disavowed/index.html", page_html); write("series/the-disavowed/index.md", md); full.append(md)
        page_html, md = self.authors_page()
        write("for-authors/index.html", page_html); write("for-authors/index.md", md); full.append(md)
        write("404.html", self.not_found())
        write("robots.txt", self.robots())
        write("sitemap.xml", self.sitemap())
        write("llms.txt", self.llms())
        write("llms-full.txt", "\n---\n\n".join(full))
        write("audiobooks.json", self.catalogue_json())
        write(".nojekyll", "")
        if self.cfg.get("cname") and not self.draft:
            write("CNAME", self.cfg["cname"] + "\n")
        state = "DRAFT (noindex, robots closed)" if self.draft else "LIVE build"
        print(f"{state}: {len(self.pages)} pages, {len(self.titles)} audiobooks -> {OUT.relative_to(ROOT)}/")


if __name__ == "__main__":
    Site().build()
