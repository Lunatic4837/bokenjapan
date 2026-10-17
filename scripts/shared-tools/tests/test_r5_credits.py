#!/usr/bin/env python3
"""Tests for the R5 photo-credits policy in check_live.py (r5_credits). Usage: python3 test_r5_credits.py [path/to/check_live.py]"""
import importlib.util, os, sys
from bs4 import BeautifulSoup
here = os.path.dirname(os.path.abspath(__file__))
src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(here, "..", "check_live.py")
spec = importlib.util.spec_from_loader("cl", importlib.machinery.SourceFileLoader("cl", src))
cl = importlib.util.module_from_spec(spec); sys.argv = [src]; spec.loader.exec_module(cl)
CASES = [  # file, url path, expected R5 status
    ("pass-subpage-with-footer-link.html", "/aichi/okazaki/eat/", "PASS"),
    ("pass-credits-page.html", "/photo-credits/", "PASS"),
    ("pass-credits-page.html", "/aichi/photo-credits/", "PASS"),
    ("pass-credits-page-real.html", "/photo-credits/", "PASS"),
    ("fail-card-credit-row.html", "/aichi/okazaki/eat/", "FAIL"),
    ("fail-subpage-credit-text.html", "/aichi/okazaki/stay/", "FAIL"),
    ("fail-credits-page-incomplete.html", "/photo-credits/", "FAIL"),
    ("pass-osm-footer-data.html", "/aichi/okazaki/eat/", "PASS"),          # ODbL footer line is allowed
    ("fail-osm-credit-paragraph-on-page.html", "/aichi/okazaki/eat/", "FAIL"),  # per-section credit paragraph is not
    ("fail-foot-data-extra-credit.html", "/aichi/okazaki/eat/", "FAIL"),   # footer line may carry only the OSM credit
]
bad = 0
for fn, path, want in CASES:
    soup = BeautifulSoup(open(os.path.join(here, "r5-test", fn), encoding="utf-8").read(), "html.parser")
    body = cl.visible_text_root(soup, set())
    body = body.body or body
    res = cl.Result(); cl.r5_credits(res, body, "https://bokenjapan.com" + path)
    got = res.rules["R5"]["status"]
    ok = got == want; bad += not ok
    print(("ok  " if ok else "BAD ") + f"{fn:40s} {path:28s} want {want} got {got} {[f['code'] for f in res.rules['R5']['findings'] if f.get('code')]}")
sys.exit(1 if bad else 0)
