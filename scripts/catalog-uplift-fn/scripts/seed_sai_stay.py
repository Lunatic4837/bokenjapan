#!/usr/bin/env python3
"""Seed Sai village Stay from official Sai tourism association inn list (sourced)."""
from __future__ import annotations
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from render_hub import render_to_html
from common import OUT, save_json

STAY = [
  {'name_ja':'民宿みやの','name_en':'Minshuku Miyano','jalan_url':'https://minsyuku-miyano.com/index.html',
   'place_desc':'Coastal minshuku in Sai, Aomori, known for local seafood.','source':'sai_kanko'},
  {'name_ja':'民宿芳栄丸','name_en':'Minshuku Yoshieimaru','jalan_url':'https://saikanko.sakura.ne.jp/inn/yoshieimaru.html',
   'place_desc':'Simple minshuku in Sai village for business and budget stays.','source':'sai_kanko'},
  {'name_ja':'田中旅館','name_en':'Tanaka Ryokan','jalan_url':'https://saikanko.sakura.ne.jp/inn/tanaka.html',
   'place_desc':'Traditional inn listed by the Sai tourism association.','source':'sai_kanko'},
  {'name_ja':'福寿荘','name_en':'Fukujuso','jalan_url':'https://saikanko.sakura.ne.jp/inn/fukujyusou.html',
   'place_desc':'Minshuku in the Fukura area of Sai, Aomori.','source':'sai_kanko'},
  {'name_ja':'民宿なみえ荘','name_en':'Minshuku Namie-so','jalan_url':'https://saikanko.sakura.ne.jp/inn/namie.html',
   'place_desc':'Seafood-focused minshuku in Fukura, Sai.','source':'sai_kanko'},
]

def main():
    union_path = OUT / 'sai' / 'union.json'
    if union_path.exists():
        union = json.loads(union_path.read_text(encoding='utf-8'))
    else:
        union = {'slug':'sai','place_en':'Sai','pref_en':'Aomori','dining':[],'stay':[]}
    union['stay'] = [{
        'name_ja': s['name_ja'], 'name_en': s['name_en'],
        'jalan_url': s['jalan_url'], 'place_desc': s['place_desc'],
        'source': s['source'], 'stay_rank': i+1,
    } for i,s in enumerate(STAY)]
    union['stay_union'] = len(union['stay'])
    save_json(union_path, union)
    paths = render_to_html('sai', 'aomori', union)
    print('seeded sai stay', len(STAY), paths)

if __name__ == '__main__':
    main()
