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
- Stay cards from **Ikkyu ∪ Jalan** only (Ikkyu-first when both).
- If none in-town:  
  `No listed places to stay in {Town} — nearest options in <a href="/{pref}/{near}/">{Near}</a>.`
- Path must match `^/[a-z-]+/[a-z0-9-]+/$` (relative site path).
- **Note (Aomori / Oirase):** stay-none → Misawa because Jalan/Ikkyu hits for Oirase geocode to other towns.

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
- Northern Territories (Hokkaido `shikotan`, `tomari-nt`, `ruyobetsu`, `ryubetsu`, `shana`, `shibetoro`): **Official/Sights only**, **not** linked from pref index / not in publish crawl (map shapes may remain as non-`href` spans).

### Other
- Dedupe same facility within a section.
- HTTPS on Official links.
- Drop `（…開業）` / similar opening-date asides from visible EN copy when they are noise.

## Tooling
- Generic pass: `python3 scripts/catalog-uplift/scripts/cos_fix.py --root <site> --pref <pref> --data <cos-data.json>`
- Verify: `CHECK_BASE=http://127.0.0.1:<port> python3 quality/check_local.py --pref <pref> --check-pref-index --delay 0 …` → **0 FAIL**.
- Push: see `/workspace/p1/PUSH-HOWTO.md` (staging branches only; never `main` / `gh-pages`).
