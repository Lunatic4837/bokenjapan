#!/usr/bin/env python3
from __future__ import annotations
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import load_hubs, OUT
from render_hub import render_to_html

def main(pref: str, slugs: list[str]):
    meta = load_hubs(pref)
    pref_en = meta.get('pref_en') or pref.title()
    for slug in slugs:
        p = OUT / slug / 'union.json'
        if not p.exists():
            print('SKIP no union', slug)
            continue
        union = json.loads(p.read_text(encoding='utf-8'))
        union.setdefault('place_en', meta['hubs'][slug]['name_en'])
        union.setdefault('pref_en', pref_en)
        paths = render_to_html(slug, pref, union)
        print(slug, 'rendered', paths)

if __name__ == '__main__':
    args = sys.argv[1:]
    pref = 'yamaguchi'
    if args and args[0] == '--pref':
        pref = args[1]
        args = args[2:]
    main(pref, args)
