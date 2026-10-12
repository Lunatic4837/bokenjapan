#!/usr/bin/env python3
from __future__ import annotations
import html as htmlmod, re
from pathlib import Path
from common import CUTOVER, load_hubs
from en_names import display_ja, display_en, rank_chrome

def esc(s: str) -> str:
    return htmlmod.escape(s or '', quote=True)

def _dining_rank(it: dict):
    return it.get('tabelog_rank') or it.get('ta_rank')

def _stay_rank(it: dict):
    return it.get('stay_rank')


def _card_href(it: dict, kind: str) -> str:
    if kind == 'stay':
        for k in ('jalan_url', 'ikkyu_url', 'official_url', 'url'):
            if it.get(k):
                return it[k]
    else:
        for k in ('tabelog_url', 'ta_url', 'tripadvisor_url', 'official_url', 'url'):
            if it.get(k):
                return it[k]
    return ''

def _place_desc(it: dict, place_en: str, pref_en: str, kind: str) -> str:
    desc = (it.get('place_desc') or it.get('desc') or it.get('blurb_en') or '').strip()
    if desc:
        return desc
    # English 4th line fallback (no invented reviews)
    if kind == 'stay':
        return f'Lodging in {place_en}, {pref_en}.'
    return f'Restaurant in {place_en}, {pref_en}.'

def neutralize_credit(credit: str) -> str:
    if not credit:
        return ''
    credit = re.sub(r'\b(Tabelog|TripAdvisor|Jalan|Ikkyu|食べログ|じゃらん|一休)\b', 'source', credit, flags=re.I)
    return credit

def _photo_block(it: dict, alt: str) -> str:
    photo = it.get('photo')
    if not photo:
        return ''
    credit = neutralize_credit(it.get('photo_credit') or '')
    cmt = f'<!-- photo-credit: {esc(credit)} -->' if credit else ''
    return f'<img class="thumb" src="{esc(photo)}" alt="{esc(alt)}" loading="lazy">{cmt}'

def li_dining(it: dict, place_en: str, pref_en: str = 'Japan', rank: int | None = None) -> str:
    ja = display_ja(it.get('name_ja'), it.get('name_en'))
    en = display_en(it.get('name_ja'), it.get('name_en'))
    n = rank if rank is not None else (_dining_rank(it) or 1)
    meta = rank_chrome(n, place_en)
    img = _photo_block(it, ja)
    href = _card_href(it, 'dining')
    desc = _place_desc(it, place_en, pref_en, 'dining')
    src_bits = []
    for k in ('tabelog_url', 'ta_url', 'tripadvisor_url'):
        if it.get(k):
            src_bits.append(f'{k}={it[k]}')
    src_cmt = f'<!-- sources: {" | ".join(src_bits)} -->' if src_bits else ''
    desc_cmt = f'<!-- desc-source: {esc(href)} -->' if href else ''
    name_img = f'<p class="place-name">{esc(ja)}</p>{img}'
    if href:
        name_img = f'<a href="{esc(href)}">{name_img}</a>'
    return (
        f'<li>{name_img}'
        f'<p class="place-blurb">{esc(en)}</p>'
        f'<p class="place-meta">{esc(meta)}</p>'
        f'<p class="place-desc">{esc(desc)}</p>{desc_cmt}{src_cmt}</li>'
    )

def li_stay(it: dict, place_en: str, pref_en: str = 'Japan', rank: int | None = None) -> str:
    ja = display_ja(it.get('name_ja'), it.get('name_en'))
    en = display_en(it.get('name_ja'), it.get('name_en'))
    n = rank if rank is not None else (_stay_rank(it) or rank or 1)
    meta = rank_chrome(n, place_en)
    img = _photo_block(it, ja)
    href = _card_href(it, 'stay')
    desc = _place_desc(it, place_en, pref_en, 'stay')
    src_bits = []
    for k in ('jalan_url', 'ikkyu_url'):
        if it.get(k):
            src_bits.append(f'{k}={it[k]}')
    src_cmt = f'<!-- sources: {" | ".join(src_bits)} -->' if src_bits else ''
    desc_cmt = f'<!-- desc-source: {esc(href)} -->' if href else ''
    name_img = f'<p class="place-name">{esc(ja)}</p>{img}'
    if href:
        name_img = f'<a href="{esc(href)}">{name_img}</a>'
    return (
        f'<li>{name_img}'
        f'<p class="place-blurb">{esc(en)}</p>'
        f'<p class="place-meta">{esc(meta)}</p>'
        f'<p class="place-desc">{esc(desc)}</p>{desc_cmt}{src_cmt}</li>'
    )

def section(title: str, lis: list[str]) -> str:
    return f'<section class="place-section"><h2>{title}</h2><ul class="place-list">{"".join(lis)}</ul></section>'

def replace_or_insert_section(html: str, title: str, new_sec: str) -> str:
    pat = re.compile(rf'<section class="place-section"><h2>{re.escape(title)}</h2>.*?</section>', re.S)
    if pat.search(html):
        return pat.sub(new_sec, html, count=1)
    # insert before footer if possible
    if '</main>' in html:
        return html.replace('</main>', new_sec + '</main>', 1)
    if '</body>' in html:
        return html.replace('</body>', new_sec + '</body>', 1)
    return html + new_sec


def https_official_links(html: str) -> str:
    def repl(m):
        url=m.group(1)
        if url.startswith('http://') and not url.startswith('http://localhost'):
            url='https://'+url[len('http://'):]
        return f'<h2>Official</h2><p><a href="{url}"'
    return re.sub(r'<h2>Official</h2>\s*<p><a href="([^"]+)"', repl, html, count=1)

def strip_visible_brands(html: str) -> str:
    html = re.sub(r'\s*·\s*<a href="[^"]+">(Tabelog|TripAdvisor|Jalan|Ikkyu|食べログ|じゃらん|一休)</a>', '', html, flags=re.I)
    return html

def render_to_html(slug: str, pref: str, union: dict, roots: list[Path] | None = None) -> list[Path]:
    roots = roots or [CUTOVER]
    place_en = union.get('place_en') or slug.title()
    pref_en = union.get('pref_en') or pref.title()
    dining = list(union.get('dining') or [])
    stay = list(union.get('stay') or [])
    # sort: tabelog rank then ta
    def dkey(it):
        if it.get('tabelog_rank'):
            return (0, it['tabelog_rank'])
        return (1, it.get('ta_rank') or 9999)
    dining.sort(key=dkey)
    d_lis = [li_dining(it, place_en, pref_en, rank=i+1) for i, it in enumerate(dining)]
    s_lis = [li_stay(it, place_en, pref_en, rank=i+1) for i, it in enumerate(stay)]
    d_sec = section('Dining', d_lis) if d_lis else ''
    s_sec = section('Stay', s_lis) if s_lis else ''
    written = []
    for root in roots:
        path = root / pref / slug / 'index.html'
        if not path.exists():
            continue
        html = path.read_text(encoding='utf-8', errors='replace')
        if d_sec:
            html = replace_or_insert_section(html, 'Dining', d_sec)
        if s_sec:
            html = replace_or_insert_section(html, 'Stay', s_sec)
        html = strip_visible_brands(html)
        html = https_official_links(html)
        path.write_text(html, encoding='utf-8')
        written.append(path)
    return written
