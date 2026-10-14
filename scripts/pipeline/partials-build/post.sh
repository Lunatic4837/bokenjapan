#!/bin/bash
# post-render chain for one prefecture: hub template + daily + sights + names
set -e; P=$1; PE=$2; R=${BJ_ROOT:-${FN_WT:-/workspace/p1/wt-partials}}; cd /workspace/p1/partials-build
python3 cu/template_hub.py --root $R --pref $P --tb tb.jsonl --photos | tail -1
python3 cu/rename_cards.py $R $P | tail -1
python3 add_daily.py $R $P $PE | grep -c . || true
python3 fix_sights.py $R $P $PE
python3 sight_names.py $R $P
python3 loan_fix.py $R $P
python3 kata_en.py $R $P
grep -rl "Camp Ba\b" $R/$P | xargs -r sed -i 's/Camp Ba\b/Campground/g'
python3 fix_bare.py $R $P
python3 clean_titles.py $R $P                 # AUDIT-47 P8: SEO page titles -> clean place names
python3 /workspace/p1/quality/check_live.py --help >/dev/null 2>&1 || true
python3 shared/coverage_report.py --root $R --pref $P   # standing bar: photo / EN-desc coverage per town
