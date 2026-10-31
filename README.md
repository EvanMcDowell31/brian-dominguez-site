# Brian Dominguez, audiobook narrator

The website for Brian Dominguez: every audiobook he has narrated, a page per title with a sample and store links, and a page for authors who want to hire him.

**Status: live at https://briandominguezvoice.com**, served by GitHub Pages from `docs/` on `main`. Brian approved it on 2026-10-31. Setting `"draft": true` in `data/site.json` and rebuilding puts the site back behind `noindex`, a closed `robots.txt` and a draft banner.

## Build and preview

```sh
python3 build.py                      # writes docs/
python3 -m http.server -d docs 8000   # open http://localhost:8000
```

There's nothing to install: the build uses only Python's standard library. GitHub Pages serves the committed `docs/` folder as it is.

| File | What it holds |
| --- | --- |
| `data/site.json` | Name, bio, contact, links, domain, the draft switch |
| `data/titles.json` | One entry per audiobook: facts from Audible's catalogue, store links, cover, sample |
| `src/` | Stylesheet, favicon, share card (`og.png`) |
| `build.py` | Turns the data into `docs/` |
| `tools/check_catalog.py` | Lists new Audible titles narrated by Brian that the site doesn't show yet |
| `tools/make_og.py` | Re-renders `src/og.png` with headless Chrome |

## Built for search engines and AI assistants

- Plain HTML that reads without JavaScript, fast, with no outside fonts or scripts.
- schema.org JSON-LD on every page. The home page is a `ProfilePage` about a `Person`. Each title is an `Audiobook` with `readBy`, `author`, `duration`, `publisher` and a sample. The Disavowed is a `BookSeries`, and every inner page has breadcrumbs.
- A Markdown twin of every page (`index.md`, linked with `rel="alternate"`), plus `llms.txt` (in the [llmstxt.org](https://llmstxt.org/) format), `llms-full.txt` and `audiobooks.json`.
- `sitemap.xml`, and, once launched, a `robots.txt` that admits search engines and the AI crawlers by name: OpenAI's, Anthropic's, Perplexity's, Google-Extended and Applebot-Extended.
- Canonical URLs, Open Graph and Twitter cards, `rel="me"` links to his profiles.

Google says Search ignores `llms.txt` ([guide](https://developers.google.com/search/docs/fundamentals/ai-optimization-guide)). It's here for other assistants and costs nothing. The structured data and clean HTML matter more.

## Launch checklist

- [x] Brian approved the site (2026-10-31).
- [x] Domain briandominguezvoice.com registered at Porkbun (2026-10-31, renews 2027-10-31).
- [x] `base_url` and `cname` set, `"draft": false`.
- [x] Repository on GitHub, with Pages deploying from branch `main`, folder `/docs`.
- [ ] DNS at Porkbun: delete the parking records pointing to `uixie.porkbun.com`. Then add A records 185.199.108.153, .109.153, .110.153 and .111.153, AAAA records 2606:50c0:8000::153 to 8003::153, and a `www` CNAME to `evanmcdowell31.github.io` ([GitHub docs](https://docs.github.com/en/pages/configuring-a-custom-domain-for-your-github-pages-site/managing-a-custom-domain-for-your-github-pages-site)).
- [ ] Verify the domain in GitHub (Settings → Pages → Add a domain → TXT record at Porkbun), then turn on "Enforce HTTPS".
- [ ] Brian's contact: an email address or ACX profile link (`contact`), plus any social profiles (`same_as`). An optional photo goes in `src/` and `photo`.
- [ ] Let each author know their cover and Audible sample appear on the site.
- [ ] Add the site to Google Search Console and Bing Webmaster Tools, and submit `sitemap.xml`.
- [ ] Paste Brian's ACX bounty links into `audible_bounty_url` for each title. A new Audible member who signs up through one pays a bounty ([ACX](https://help.acx.com/s/article/earn-with-the-bounty-program)).

## Keeping it current

Run `python3 tools/check_catalog.py` now and then. When it reports a new title, add an entry to `data/titles.json` (copy an existing one), then rebuild.

## Sources

Catalogue facts, covers and samples come from Audible's public catalog data (api.audible.com), and Apple Books links from Apple's iTunes Search API, all read on 2026-10-31. Summaries are the publishers' own.
