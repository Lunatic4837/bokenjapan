2026-10-14 21:59 Saitama: staging/saitama@5b7312d9a2 (Stay/Eat/genre pages, geo+ai_friendly, blocker sweep); publish commit cd5a6ccb0d on publish/saitama in /workspace/p1/pub-saitama (not pushed)
2026-10-14 23:41 Kanagawa: staging/kanagawa@a1a01bf0cc (collection, sights EN, Stay/Eat/genre, geo+ai_friendly, blocker sweep); publish commit ede086cb15 on publish/kanagawa in /workspace/p1/pub-kanagawa (not pushed)
2026-10-15 07:40 p1-rural-south HIROSHIMA quality pass started: worktree /workspace/p1/pub-q-hiroshima (branch q-hiroshima off origin/gh-pages 64e4b9f72e), before report quality/q-hiroshima/before.md
- 2026-10-15 08:02 hiroshima: collected expanded data in quality/q-hiroshima/data2 (cache-only Tabelog/Ikkyu, Jalan live); existing stay photos judged: 15 food/promo/pet/people, narrow list in force_replace.json
2026-10-15 08:30 hiroshima step1 pushed staging/q-hiroshima a7d6dcda81
2026-10-15 10:37 ehime 1c+1d done, pushed staging/q-ehime-1cd 25b5c8174e (58 rough names fixed, labels/scores removed from cards, 0 macrons). Next: dining shortfall via mcvb.jp / oideya.gr.jp / OSM sites; Tabelog polled every 12 min (still 403).
2026-10-15 11:35 ehime SAFE rebuild (no Tabelog-derived adds): worktree /workspace/p1/pub-q-ehime-safe, steps pushed staging/q-ehime-safe-1 4a56bce36e, -2 3fdbc71c4a, -3 b0de487e7b (not gh-pages). Logs /workspace/p1/quality/q-ehime-safe/
2026-10-15 13:54 okayama s1 (stays: 239 new cards, 62 desc, 21 photos replaced, 27 pages) pushed staging/q-okayama-s1 e029f8fc0d (not gh-pages)
2026-10-15 13:55 okayama s2 (20 dining names cleaned, 263 alts, 300 tile alts) pushed staging/q-okayama-s2 cee5aaf559
2026-10-15 14:09 okayama s3 (R2 within-town place names, JR names, SEO titles) pushed staging/q-okayama-s3 17b0aad3e1; checks/report next
2026-10-15 14:35 okayama-osm START: reading live eat format; worktree pub-q-okayama-osm next
2026-10-15 14:55 okayama-osm s1 adapter partials-build/osm_render.py (cards in 2nd osm-dining section, existing Tabelog lines untouched) sample pushed staging/q-okayama-osm-1 ea5bd83d6c (not gh-pages)
2026-10-15 15:10 okayama-osm s2 photo-yield code in osm_dining.py (staged official/commons/wikidata/municipal, chain skip, md5 guard, --need); testing on kurashiki
2026-10-15 15:55 okayama-osm s3 collection workers started (15 towns, --need gap+4)
2026-10-15 16:10 okayama-osm s3 render+merge+eat hubs+sitemap(284 eat URLs; okayama had none) pushed staging/q-okayama-osm-2 fc60b14f13 (not gh-pages); checks next
2026-10-15 16:16 okayama-osm2 START: s1 triage
2026-10-15 16:17 okayama-osm2 s1 triage done: pool 3860 (photo 220=5.7%, bare 1434), LIVE only 448 cards (photo 166=37.1%, bare 50); 103 live photo-less have website. report quality/okayama-osm2/s1-triage.md
2026-10-15 16:21 okayama-osm2 s2 photo2.py (official deep) running on 88 live photo-less w/ website; s3 desc3.py written
2026-10-15 16:36 okayama-osm2 s2 live official-deep: +17 photos (live 183/448); 41 of 42 timeouts are dead sites (curl 000); okayama-kanko.jp has no search/sitemap; pool pass running
2026-10-17 00:04 p1-rural-south: pushed staging/q-fix-tottori-6 (363b561ba) and staging/q-fix-tottori-6b (91e5cbca7, adds JSON-LD cleanup; use 6b). Stopped: required QA inputs/tools missing on box.
2026-10-17 09:15 p1-rural-south: tools-south branch created: staging/tools-south 2fa882b629: bjlib.py, osm_dining.py (lean, no torch), popmap.json (from quality/audit47). Next: osm_render, photo_check, coverage, Tottori proof.
