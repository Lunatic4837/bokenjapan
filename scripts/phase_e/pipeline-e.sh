#!/bin/bash
# Phase E (on top of main 1393c5f): accepted no-photo state, no-lodging Stay lines, sourced Stay lines, English names.
set -e
cd /workspace/p1/pr12-work
git checkout -- . && git clean -fdq -- akita fukuoka miyagi oita yamaguchi
P=/workspace/p1/phase-d
[ -s $P/tbphoto/manifest.csv ] && python3 $P/tbphoto/wire_tb.py
python3 $P/strip_stale_credit.py
python3 $P/stay4/apply_stay4.py
python3 $P/nostay/apply_nostay.py | head -1
python3 $P/names/apply_sights_en.py
python3 $P/names/apply_en2.py
python3 $P/names/blurb_fix.py
python3 $P/compact.py
