#!/usr/bin/env python3
from __future__ import annotations
import re, sys
from pathlib import Path
_sp = Path(__file__).resolve().parent.parent / '.venv' / 'lib'
# find site-packages
for p in _sp.glob('python*/site-packages'):
    sys.path.insert(0, str(p))

_k = None
def _kakasi():
    global _k
    if _k is None:
        try:
            import pykakasi
            _k = pykakasi.kakasi()
        except Exception:
            _k = False
    return _k

def _romanize(ja: str) -> str:
    k = _kakasi()
    if not k or not ja:
        return ja or ''
    parts = k.convert(ja)
    s = ' '.join(p.get('hepburn') or p.get('passport') or p.get('kunrei') or '' for p in parts)
    s = re.sub(r'\s+', ' ', s).strip()
    return s.title() if s else ja

def display_ja(name_ja, name_en) -> str:
    return (name_ja or name_en or 'Place').strip()

def display_en(name_ja, name_en) -> str:
    en = (name_en or '').strip()
    if en and not re.search(r'[\u3040-\u30ff\u4e00-\u9fff]', en):
        return en
    ja = (name_ja or '').strip()
    if ja:
        rom = _romanize(ja)
        return rom or ja
    return en or 'Place'

def rank_chrome(n: int, place_en: str) -> str:
    return f'#{n} ranked in {place_en}'
