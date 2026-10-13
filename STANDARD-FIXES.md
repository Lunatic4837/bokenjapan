# BokenJapan municipality page — standard CoS fixes

Checklist derived from `/workspace/p1/aomori-review/report.md` FAIL/WARN patterns and implemented in `scripts/catalog-uplift/scripts/cos_fix.py` (plus pref-specific round-2 passes). Apply before `check_local.py --pref <slug>` (use `CHECK_BASE=http://127.0.0.1:<port>`; localhost is treated as internal).

## Must reach 0 FAIL

### R3 — Photo credits (no placeholders)
- Every Dining/Stay thumb has `<!-- photo-credit: … · Source https://… -->` with a **real** host.
- Never `source.com` / `source.net` (broken neutralize that rewrote `tabelog.com` / `jalan.net`).
- Prefer brand label + listing URL: `食べログ · Source https://tabelog.com/…`, `じゃらんnet · Source https://www.jalan.net/…`.

### R5 — No source-link chrome; cards clickable
- Remove visible `Official / source link` anchors from Sights meta.
- Wrap Sight name+thumb in `<a href="https://…">` to the real destination.
- No visible Tabelog/Jalan/Ikkyu/Tripadvisor chrome in the body.

### R2 — Stay sourced or documented zero
- Stay waterfall: **Ikkyu ∪ Jalan** first (Ikkyu-first when both). If both empty → **Rakuten Travel**, then the **official municipal / tourism-association inn list** (real names + links).
- stay-none only when all sources are empty, worded exactly:  
  `No bookable places to stay found in {Town} — nearest options in <a href="/{pref}/{near}/">{Near}</a>.`
- Path must match `^/[a-z-]+/[a-z0-9-]+/$` (relative site path). Nearest by land (or ferry for islands).
- **Note (Aomori / Oirase):** Jalan/Ikkyu hits geocode elsewhere, but Rakuten lists in-town Momoishi inns (旅館 高橋) → real Stay, not stay-none.

### R1 / locality — No out-of-town Dining padding
- Do not pad Dining with restaurants from other municipalities.
- When Tabelog area/address is known, keep only rows whose address contains the page’s `muni_ja`.
- Emit `<!-- muni-ja: {JA} -->` on the page and `<!-- locality-addr: {address} -->` on Dining cards.
- Checker (`check_local` / `check_live` `X2.town-locality`): if both present, `muni_ja` must appear in `locality-addr`.
- Renumber `#N ranked in {Town}` after drops.

### R4 — Card lines
- Dining/Stay: JA name / EN name / `#N ranked in {Town}` / short English explanation.
- **Do not** use identical filler `Restaurant in {Town}, {Pref}.` / `Lodging in {Town}, {Pref}.`
- Prefer genre-based line (`Ramen shop in …`) from Tabelog area, or `{EN name} — restaurant in {Town}, {Pref}.`, or omit line 4 (3-line card) rather than copy-paste filler.
- Sights: English name + `place-desc` explanation; no romaji-only dump when a real EN name exists.
- No full-width punctuation (`・` `～` `　`) in English fields.

### R7 — Section order
- After Official meta-block: **Stay → Dining → Sights**.

### X8 — Head tags
- Every muni + pref index: `<title>`, viewport, **canonical**, meta description, `og:title|description|url|image`.

### X1 — No draft/GSI redistribute notes
- Strip `Note: local unpublished draft only; GSI reproduction filing…` from HTML comments.
- Keep the MLIT N03 licensing comment (same source as live Miyagi/Oita):
  - Dataset: National Land Numerical Information N03 2026  
  - License: **CC BY 4.0**  
  - URL: https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-N03-2026.html  
  - Plus one-line `<!-- map-credit: … -->`.

### X6 / X14 — Covers & alts
- Cover present and credited; **English** `alt` (e.g. `{Town}, {Pref}`), never raw Wikipedia/`<span lang=…>` markup.
- Thumbs: meaningful `alt`, lazy-loading; prefer slim **WebP** (max edge ~1280, quality ~78) for Pages size.

### Slugs & publish set
- No `jis#####` slugs when a romanized name exists (rename + update maps/index).
- Drop code-suffix slugs when unambiguous (`hidakacho-01601` → `hidakacho`, etc.; keep true disambiguators like `esashi-01514`).
- Northern Territories (Hokkaido `shikotan`, `tomari-nt`, `ruyobetsu`, `ryubetsu`, `shana`, `shibetoro`): **exclude from publish** — no index links, no deploy dirs (git-rm from publish tree); map shapes may remain as non-`href` spans. Real Shiribeshi Tomari stays at `tomari/`.

### Other
- Dedupe same facility within a section.
- HTTPS on Official links.
- Drop `（…開業）` / similar opening-date asides from visible EN copy when they are noise.

## Tooling
- Generic pass: `python3 scripts/catalog-uplift/scripts/cos_fix.py --root <site> --pref <pref> --data <cos-data.json>`
- Verify: `CHECK_BASE=http://127.0.0.1:<port> python3 quality/check_local.py --pref <pref> --check-pref-index --delay 0 …` → **0 FAIL**.
- Push: see `/workspace/p1/PUSH-HOWTO.md` (staging branches only; never `main` / `gh-pages`).


## Filler place-desc
- Checker: Dining/Stay missing line 4 is **WARN** (`R4.no-line4`), not FAIL — omit beats invented filler.
- Drop lines like `Restaurant in X, Hokkaido.` / `Sushi restaurant in X, Aomori.` / `… — a place to visit in X, Hokkaido.` — use a real short English explanation or omit the line.

## Template — Miyagi/Ohira hub (all prefectures, from 2026-10-14)
- Municipality page = hub: `<body class="hubbed">`, Official meta-block, optional stay-none line, then `section.hub > ul.hub-tiles` with tiles Stay → Eat → Do → See → Day to day (only non-empty).
- List pages `stay/ do/ see/ day-to-day/` and `eat/<genre>/` = `section.place-section > h2.visually-hidden + ul.place-list` (same card markup), media paths absolute `/media/…`.
- `eat/` = genre category tiles (`ul.hub-tiles.hub-tiles-sm`, `a.hub-tile.hub-tile-sm`), categories from `phase-d/rollout/rules.py` (CAT/TB) using each card's Tabelog `servesCuisine`; convenience stores go to Day to day.
- Photos: every Dining card without a thumb gets its own Tabelog listing og:image when usable (slim WebP ≤480px, credit only in `<!-- photo-credit -->`); otherwise logged in no-photo-found.csv. Stay photos: official HP → Ikkyu/Jalan/Rakuten listing.
- Stay EN line: real JA name stays as the name; EN line via `en_natural.py` (loanword dictionary + Hepburn, no kana-dump romaji like "Hoteruruutoin"). Phones normalized (`0xxx-xx-xxxx`, multiple joined with ` / `).
- Generator: `scripts/catalog-uplift/scripts/template_hub.py --root <site> --pref <pref> --photos` (genre cache: /workspace/p1/data/template4/tb.jsonl, fetch_tb.py). Run after cos_fix/finalize; idempotent (skips pages already hubbed).
- Self-check: `python3 scripts/quality/template_selfcheck.py <site> <pref>` must report 0 fails (compares against miyagi/ohira).
- Analytics beacon: the generator keeps any `<script>` containing `beacon`/`cloudflareinsights` before `</body>` (hub and list pages); it never edits homepage index.html or styles.css.

- 2026-10-14 Stay sources: Ikkyu, Jalan, Rakuten Travel, official facility/municipal site are all valid (checker STAY-FALLBACK). Ranks are numbered per town across all sub-pages (Dining 1..N, Stay 1..N); card img alt = English name.
