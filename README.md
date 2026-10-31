# Brian Dominguez, audiobook narrator

The website for Brian Dominguez: every audiobook he has narrated, a page per title with a sample and store links, and a page for authors who want to hire him.

**Status: draft for Brian's review.** Nothing here is published. While `"draft": true` is set in `data/site.json`, every page carries `noindex`, `robots.txt` closes the site to crawlers, and a banner marks each page as a draft.

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

## Before launch

1. Brian reads every page and approves it, then rewrites the bio in his own words (`data/site.json` → `bio`).
2. Add his contact: an email address or ACX profile link (`contact`), plus any social profiles (`same_as`). An optional photo goes in `src/` and `photo`.
3. Check with each author that the cover and Audible sample can appear on the site.
4. Register the domain **in Brian's name**. On 2026-10-31, briandominguez.com was taken, and briandominguezvoice.com, briandomingueznarrator.com and briandominguez.net were unregistered.
5. Set `base_url` and `cname` to the domain, set `"draft": false`, and run `python3 build.py`. The build refuses to launch without contact details and a domain.
6. Create the GitHub repository and push. In Settings → Pages, deploy from branch `main`, folder `/docs`.
7. Verify the domain in GitHub's Pages settings before pointing DNS at it. Then add A records 185.199.108.153, .109.153, .110.153 and .111.153, AAAA records 2606:50c0:8000::153 to 8003::153, and a `www` CNAME to `<user>.github.io`. Turn on "Enforce HTTPS" ([GitHub docs](https://docs.github.com/en/pages/configuring-a-custom-domain-for-your-github-pages-site/managing-a-custom-domain-for-your-github-pages-site)).
8. Add the site to Google Search Console and Bing Webmaster Tools, and submit `sitemap.xml`.
9. Paste Brian's ACX bounty links into `audible_bounty_url` for each title. A new Audible member who signs up through one pays a bounty ([ACX](https://help.acx.com/s/article/earn-with-the-bounty-program)).

## Keeping it current

Run `python3 tools/check_catalog.py` now and then. When it reports a new title, add an entry to `data/titles.json` (copy an existing one), then rebuild.

## Sources

Catalogue facts, covers and samples come from Audible's public catalog data (api.audible.com), and Apple Books links from Apple's iTunes Search API, all read on 2026-10-31. Summaries are the publishers' own.
