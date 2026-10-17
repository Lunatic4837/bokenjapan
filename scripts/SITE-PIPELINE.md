# Site-level pipeline (run on a full checkout of gh-pages, last step before pushing)

```
python3 scripts/ai_friendly.py --root .     # titles, H1, JSON-LD, crumbs, data/*.json, llms*.txt, robots.txt, flat sitemap -> calls split_sitemap.py
python3 scripts/site_chrome.py --root .     # footer SNS + legal row, logo, lazy images, map placeholder, canonical/og/twitter/icons (skips tokyo/)
python3 scripts/split_sitemap.py --from-git # optional: rebuild sitemap index + sitemaps/<pref>.xml from files committed at HEAD
python3 scripts/optimize_maps.py --root .  # after (re)generating maps: 1-decimal relative paths, idempotent (skips data-opt="1"); hokkaido 264 KB -> 46 KB gzip
```

Both page scripts only rewrite marked or chrome blocks, are idempotent (`--check` exits 1 if anything would change) and take about 25 s on 22,700 pages.
Run `ai_friendly.py` first: `site_chrome.py` copies the page's own title and description into its share tags.
If a cherry-pick of the hub/root pages conflicts, take either side and re-run `site_chrome.py`: its output is reproducible.
Page generators (template_hub.py, build-pages-site.py) still emit the old footer; until they are updated, re-run both scripts after every publish.
