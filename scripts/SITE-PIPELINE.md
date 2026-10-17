# Site-level pipeline (run on a full checkout of gh-pages, last step before pushing)

```
python3 scripts/english_first_headings.py --root . [--pref <slug>]   # cards: English headline + Japanese subtitle (lang=ja); idempotent; skips tokyo/; run after regenerating, BEFORE ai_friendly.py
python3 scripts/ai_friendly.py --root .     # titles, H1, JSON-LD, crumbs, data/*.json, llms*.txt, robots.txt, flat sitemap -> calls split_sitemap.py
python3 scripts/site_chrome.py --root .     # footer SNS + legal row, logo, lazy images, map placeholder, canonical/og/twitter/icons (skips tokyo/)
python3 scripts/split_sitemap.py --from-git # optional: rebuild sitemap index + sitemaps/<pref>.xml from files committed at HEAD
python3 scripts/optimize_maps.py --root .  # after (re)generating maps: 1-decimal relative paths, idempotent (skips data-opt="1"); hokkaido 264 KB -> 46 KB gzip
```

Both page scripts only rewrite marked or chrome blocks, are idempotent (`--check` exits 1 if anything would change) and take about 25 s on 22,700 pages.
Run `ai_friendly.py` first: `site_chrome.py` copies the page's own title and description into its share tags.
If a cherry-pick of the hub/root pages conflicts, take either side and re-run `site_chrome.py`: its output is reproducible.
Page generators (template_hub.py, build-pages-site.py) still emit the old footer; until they are updated, re-run both scripts after every publish.

**English-first headings (Michael's decision 2026-10-17: English everywhere).** After you regenerate or merge content for a prefecture, run `python3 scripts/english_first_headings.py --root . --pref <slug>` (`--dry-run` previews, `--check` verifies 0 changes). It converts every card that still headlines Japanese into English headline + small Japanese subtitle, inside the card link, with no regeneration; `--include-tokyo` is off by default. English name ladder: the card's own clean English line, then the image alt, then a category-led headline ("Ramen shop in Taira") built only from facts on the card, with a distinguishing area, station or rank when two cards in a town would collide; a rough romanisation never headlines. In `post.sh` it is the last card rewrite. Details: HOWTO-ENGLISH-FIRST.md.

**Site-defect scripts (2026-10-17, strict-check fixes; all idempotent, `--check` exits 1 if a change is needed, `--report CSV`, tokyo/ skipped).** Run after `site_chrome.py` (or any time on a merged tree), then `split_sitemap.py --from-git` once committed:
```
python3 scripts/hub_tile_fix.py --root .        # X21: no hub tile repeats the hero / another tile (own-page photos only, else plain tile)
python3 scripts/ranks_contiguous.py --root .    # R4.other: close gaps in '#N ranked in' of Dining cards (skips towns with tied ranks)
python3 scripts/strip_draft_notes.py --root .   # X1.note: drop leaked 'local unpublished draft only ...' line from the boundary comment (keeps licence/citation)
python3 scripts/nav_refresh.py --root .         # X20/R8: refresh stale bj-nav of sub-pages (dead section links, missing 'Nearby in') using ai_friendly.py on a scratch copy of that prefecture
python3 scripts/day_to_day_tile.py --root .     # X18: add the Day to day hub tile only where <town>/day-to-day/ exists; others are listed in the report, never invented
```
