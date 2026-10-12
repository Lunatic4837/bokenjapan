#!/usr/bin/env python3
from __future__ import annotations
import re

def _norm(s: str) -> str:
    s = (s or '').lower()
    s = re.sub(r'[\s\u3000\-・ー]', '', s)
    return s

def build_union(slug: str, place_en: str, tb: dict, ta: dict, ik: dict, jl: dict, pref_en: str = 'Yamaguchi') -> dict:
    dining = []
    # Tabelog first (ranked)
    for it in tb.get('items') or []:
        dining.append({
            'name_ja': it.get('name_ja') or '',
            'name_en': it.get('name_en') or '',
            'tabelog_url': it.get('tabelog_url') or it.get('url'),
            'tabelog_rank': it.get('tabelog_rank'),
            'rst_id': it.get('rst_id'),
            'source': 'tabelog',
        })
    tb_names = {_norm(d['name_ja']) for d in dining if d.get('name_ja')}
    # TA fill
    for it in ta.get('items') or []:
        n = _norm(it.get('name_en') or '')
        # skip if similar JA already present (weak)
        if n and n in tb_names:
            continue
        dining.append({
            'name_ja': it.get('name_ja') or '',
            'name_en': it.get('name_en') or '',
            'ta_url': it.get('ta_url'),
            'ta_rank': it.get('ta_rank'),
            'source': 'tripadvisor',
        })
    stay = []
    for it in jl.get('items') or []:
        stay.append({
            'name_ja': it.get('name_ja') or '',
            'name_en': it.get('name_en') or '',
            'jalan_url': it.get('jalan_url'),
            'image': it.get('image'),
            'source': 'jalan',
        })
    for it in ik.get('items') or []:
        stay.append({
            'name_ja': it.get('name_ja') or '',
            'name_en': it.get('name_en') or '',
            'ikkyu_url': it.get('ikkyu_url'),
            'source': 'ikkyu',
        })
    return {
        'slug': slug,
        'place_en': place_en,
        'pref_en': pref_en,
        'tabelog_count': tb.get('count', 0),
        'tripadvisor_count': ta.get('count', 0),
        'dining_union': len(dining),
        'ikkyu_count': ik.get('count', 0),
        'jalan_count': jl.get('count', 0),
        'stay_union': len(stay),
        'ikkyu_status': ik.get('status'),
        'dining': dining,
        'stay': stay,
    }
