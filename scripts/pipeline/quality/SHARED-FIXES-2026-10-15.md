# Shared pipeline fixes — AUDIT-47 fix plan P1–P10 (2026-10-15)

Branch: `staging/partials-complete` (shared repo; see the commit SHA in the hand-off). Nothing was pushed to `gh-pages`, nothing published.
Live code locations (not in git): `/workspace/p1/partials-build`, `/workspace/p1/fn-uplift`, `/workspace/p1/data/catalog-uplift`, `/workspace/p1/quality`.
A tracked snapshot of every changed file is committed under `scripts/pipeline/<same relative path>`; `scripts/ai_friendly.py` is changed in place.
Pre-change backups: `*.bak-20261015-pre-shared` next to each edited file.

## New standing quality bar (Michael via Emma, built in)
- Every town lists **all** its facilities: no caps. Targets scale with population and are *minimums* that checks enforce; `BJ_COLLECT_ALL=1` (default) keeps every in-town row the source returns.
- Every card needs a relevant photo (a Stay photo shows the property or a room, never food/promo) and an English description.
- A card may have no photo only after the full search: source image → official site → Google Places → Tabelog → Jalan → Rakuten → Ikkyu → TripAdvisor → Wikimedia Commons → municipal tourism site. The attempt is stored per card as `photo_search` = `{tried:[…], result:'jalan'|null, notes:{src:reason}}` in `partials-build/data/<pref>/_photo_search.json` (and the rejects in `no-photo-found.csv`). Google Places is only tried when `BJ_GOOGLE_PLACES_KEY` is set; otherwise it is recorded as `no-api-key`.
- Clean official English names (Tabelog EN → Ikkyu → dictionary), no SEO-style titles.
- check_live enforces photo % and English-description % per town (X22/X23); `shared/coverage_report.py` reports both per town and per lane.

## What changed
| Fix | Where | Behaviour |
|---|---|---|
| P1 targets | `partials-build/shared/bj_shared.py` (`target_dining`, `target_stay`, `targets`), `pb_build.py`, all `run_pref*`/`run_*_capped`/`run_nationwide_wave` | `DINING_CAP/STAY_CAP=24/12` removed. Dining: ≥50k → pop/1000 (50–100); 10–50k → pop/750 (10–40); <10k → pop/500 (3–15). Stay: <20k → 1; <100k → 3; else pop/20k (cap 30). Matches the audit's `exp_dining`/`exp_stay` for all 1,741 towns. Population from `quality/audit47/popmap.json`. |
| P2 Tabelog | `bj_shared.tabelog_paginate/tabelog_collect`, `scrape_tabelog.py`, `pb_build.tabelog` | Loops `/rstLst/<n>/` until in-town ≥ target (or, with BJ_COLLECT_ALL, until the `N件` total is exhausted) or page 60. Strict in-town filter kept; when <50% of rows are in town it iterates the town's A-code sub-areas. Rank = score then review count. Row parsing also keeps genre, nearest station + distance, budget, score. |
| P3/P4 Jalan | `bj_shared.jalan_paginate`, `scrape_jalan.py`, `pb_build.jalan` | Ports `kyushu-uplift/jalan_area.py` `?idx=` pagination to the CTY page. Address filter enforced (empty locality passes only if the street address matches). |
| P4 Ikkyu | `bj_shared.ikkyu_pool`, `scrape_ikkyu.py`, `pb_build.ikkyu_pool` | Real collector: pref list pages (recommended order) → facility pages (name, addressRegion/Locality, og:image + gallery, description, official EN `alternateName` if present), cached per pref. Status is explicit (`ok`/`cached`/`BLOCKED_403`/`NO_AREA_CODE`), never a silent empty list. |
| P5 photo gate | `bj_shared.photo_gate/photo_search`, `shared/photo_judge.py`, `fn_render.photo`, both `fetch_photos.py` | Any image < 5 KB rejected (all card types). Stay photos: source ≥ 560 px, facility/exterior image preferred over the plan image (Jalan og:image at `pict2L`; Ikkyu gallery[0]), food/promo alt text or URL rejected, then a CLIP zero-shot judge (food / promo / pet / people). Rejects → `no-photo-found.csv`; then the `photo_search` cascade. |
| P6 neighbour stays | `fn_render.py`, `cu/template_hub.py`, `scripts/ai_friendly.py`, check_live | A Stay card whose address municipality ≠ the town gets `In neighbouring X.` at the start of its English description, a `<!-- neighbour: X -->` marker, and is described "in X". If **all** stays are neighbours, the hub tile, stay-page title/H1 and JSON-LD title become `Stays near {Town}`. Mixed towns keep tile "Stay" with per-card labels. The `#N ranked in {Town}` line is unchanged (R4 format). |
| P7 romaji | `bj_shared.romanize_name`, `shared/romaji_dict.json`, `fn_render.en_name` | Order: Tabelog EN (`tabelog.com/en`, cached) / Ikkyu alternateName → exact dictionary → word dictionary (本店→Main Store, 屋→-ya, 麺や→Menya, 屋台→Yatai, odoriji ゞゝ々 expanded, ら～めん→Ramen) → pykakasi per word (no space-splitting inside a word, long vowels collapsed). |
| P8 titles | `bj_shared.clean_title`, `partials-build/clean_titles.py` (in `post.sh`), `fetch_sights_en_site.py` | Splits on `｜ | » 【】 – -`, strips 公式/観光協会/ホームページ/HOME; prefers h1/og:title. `clean_titles.py ROOT pref [--dry]` fixes built pages. |
| P9 dining desc | `bj_shared.dining_desc`, `fn_render.build_sections` | Sourced from the Tabelog list row only: genre, nearest station + distance, budget, score. e.g. "Ramen shop 279 m from Itami Station (Hankyu), Itami; dinner ¥1,000–¥1,999. Tabelog 3.69 (1,070 reviews)." Stays without features get "Hotel in {place}; listed on Jalan/Ikkyu." |
| P10 check_live | `quality/check_live.py` | New: `R1.cap`, `R1.below-target`, `R1.max-rank`, `R2.cap`, `R2.neighbour-unlabelled`, `R3.stay-food-photo` (opt-in judge), `R4.rough-romaji`, `X12.title-as-name`, **X22 photo coverage %**, **X23 English-description coverage %** (both FAIL below threshold, % in the message and in `info.photo_pct/desc_pct`). |

## How other builders run it
```
# collect (population targets, full pagination, shared Ikkyu/Jalan)
python3 /workspace/p1/partials-build/pb_build.py <pref> <pref_ja> collect [slugs…]      # BJ_RECOLLECT=1 to overwrite existing json
# render (photo gate + photo_search + neighbour labels + EN names + dining descriptions)
python3 /workspace/p1/partials-build/fn_render.py <pref> <pref_ja> <PrefEn> [slugs…]
# post chain (hub template, names, titles, coverage report); root = $BJ_ROOT or $FN_WT
BJ_ROOT=/path/to/worktree /workspace/p1/partials-build/post.sh <pref> <PrefEn>
# coverage (per town / per lane) – exits 1 with --strict when below the bar
python3 /workspace/p1/partials-build/shared/coverage_report.py --root <tree> --pref ehime
python3 /workspace/p1/partials-build/shared/coverage_report.py --root <tree> --lane South --out south.md --csv south.csv --strict
python3 /workspace/p1/quality/check_live.py --pref <pref>      # new rules run automatically
python3 /workspace/p1/partials-build/clean_titles.py <tree> <pref> [--dry]
```
Old collectors (`run_pref_v2.py`, `run_pref_capped.py`, `fn-uplift/scripts/run_*`) now call the same code: `TD, TS, POP = BJS.targets(pref, slug, h)` and `scrape_tabelog(..., target=TD)`.
The photo judge needs `/home/box/venvs/bjclip` (open_clip ViT-B-32, laion2b weights; already installed on the box). Without it the other gate checks still run.

## Env vars / flags
| Var | Default | Meaning |
|---|---|---|
| `BJ_TARGET_MODE` | `pop` | `legacy` restores 24/12 caps and 2 Tabelog pages |
| `BJ_COLLECT_ALL` | `1` | keep every in-town source row; `0` stops at the target |
| `BJ_DINING_TARGET`, `BJ_STAY_TARGET` | – | force a fixed target for a run |
| `BJ_POPMAP` | `quality/audit47/popmap.json` | population source |
| `BJ_TABELOG_MAX_PAGES` | `60` | page limit per Tabelog list |
| `BJ_JALAN_MAX_IDX` | `3000` | Jalan `?idx=` limit |
| `BJ_TABELOG_EN` | `1` | look up official English name (tabelog.com/en), cached in `shared/data/tabelog_en.json` |
| `BJ_PHOTO_JUDGE` | `1` | CLIP food/promo judge on Stay photos |
| `BJ_STAY_MIN_W`, `BJ_MIN_IMG_BYTES` | `560`, `5120` | Stay photo min width; min bytes for any image |
| `BJ_JALAN_FACILITY_PHOTO` | `1` | use the facility page photo instead of the plan image |
| `BJ_GOOGLE_PLACES_KEY` | – | enables the Google Places step of the photo search |
| `BJ_REGATE` | – | re-run the gate over already downloaded media |
| `BJ_DATA_DIR`, `BJ_REJECT_CSV`, `BJ_ROOT` | – | alternate data dir / reject log / post.sh root (used for tests) |
| `BJ_CACHE_ONLY` | – | `1`, or `tabelog,ikyu`: never touch the network for those hosts (use cached pages) |
| `BJ_MIN_PHOTO_PCT`, `BJ_MIN_DESC_PCT` | `100` | check_live X22/X23 and coverage_report thresholds |
| `BJ_CAP_STRICT` | `1` | `0` downgrades `R1.below-target` to WARN |
| `BJ_CHECK_JUDGE`, `BJ_MEDIA_ROOT` | – | enable R3.stay-food-photo (judge on local media) |

## Test results (before → after, sample towns)
Tests ran against cached pages: **tabelog.com started returning a Cloudflare "Just a moment" 403 to the box at ~06:30 and ikyu.com 403s**, so pagination past the cached pages could not be re-fetched. I did not work around either block.
| Fix | Sample | Before | After |
|---|---|---|---|
| P1 | all 1,741 towns | – | targets equal the audit's expected values for 1,741/1,741 |
| P2 Tabelog | hyogo/itami, hyogo/kawanishi, fukushima/fukushima | Dining 24 / 24 / 60 | 40 / 40 / 60 (cache holds only the first 2–4 pages; Itami reports 897 hits, Kawanishi 633, Fukushima 1,977) |
| P3/P4 Jalan | fukushima/fukushima; hyogo/itami CTY | Stay 6 (page 1) | 70 in-town hotels over 4 pages; Itami CTY 5 pages / 91 hotels (1 in town) |
| P4 Ikkyu | hyogo pref list (cache) | stub: 0 items | 316 facilities parsed, 96 with gallery images; live fetch → explicit `BLOCKED_403` |
| P5 gate | 120 sampled Stay photos from the audit | 15 food/promo/pet/people shots found by the audit passed | 14 of the 15 rejected (9 food, 2 promo, 2 pet, 1 people shot); 1 borderline scenic shot (Akaigawa) is kept; Jalan 300 px thumbnails rejected, 600 px exterior kept; Kawanishi's exterior photo (alt 【外観】…料理) correctly kept |
| P6 | synthetic: Itami (only neighbour stays), Kawanishi (mixed) | no label | `In neighbouring Nishinomiya/Takarazuka.` on cards; Itami tile/H1/title = `Stays near Itami`; `R2.neighbour-unlabelled` fails when the label is removed. Real cached data (3,047 stay cards, 27 prefecture caches): 0 false positives after the 郡/prefecture-prefix fixes (those caches were already strict-filtered, so they hold no true neighbour stays) |
| P7 romaji | itami / kawanishi / amagasaki / matsuyama (25/25/34/36 names) | rough 2 / 2 / 6 / 7 | 0 / 1 / 0 / 0 |
| P8 titles | aichi (copied live tree) | 73 SEO-title names | 2 left (both bare 観光協会 names) |
| P9 desc | itami, kawanishi | Dining without EN description 24/24 (audit: no-desc D+S 24 and 24) | 41/41 cards with an English description |
| P10 | synthetic + rendered pages | – | 24 dining cards at pop 195k → `R1.cap` FAIL; 99/100 photos → X22 FAIL; 99/100 descriptions → X23 FAIL |

## Not feasible / caveats
- Ikkyu and Tabelog currently block the box (403 / Cloudflare); the collectors report this explicitly. Re-run `BJ_RECOLLECT=1 pb_build.py …` from an unblocked network (or with a browser-fetched cache) to reach the Tabelog 100-per-town targets.
- Google Places photo search needs an API key; TripAdvisor names still come from URL slugs (P3 page_max is scaled, h1/JSON-LD parsing not done: TA needs JS).
- `bj-pref-check` workflow (`/home/box/sand-data/workflows/bj-pref-check`) only wraps `/workspace/p1/quality/check_live.py`, so it picks up the new rules automatically.
- `wt-partials` disappeared from `/workspace/p1` at ~06:26 (not removed by this work); the commit was made from a new sparse worktree `/workspace/p1/wt-shared-fixes` on the same branch.
