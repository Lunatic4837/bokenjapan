#!/usr/bin/env python3
from __future__ import annotations
import re, subprocess
from pathlib import Path
import os, sys
sys.path.insert(0, '/workspace/p1/partials-build/shared'); import bj_shared as BJS  # AUDIT-47 P5 photo gate
from common import curl, sleep_polite, RAW, MEDIA, UA, CUTOVER, disk_avail_gib
import os
MP = os.environ.get('FN_MEDIA_PREFIX', '')

def _download(url: str, dest: Path, kind: str = 'dining', alt: str = '') -> bool:
    """P5: images < 5 KB rejected everywhere; Stay photos also need >= 560 px, no food/promo alt/url and a CLIP judge pass."""
    ok = _download_raw(BJS.jalan_big(url) if kind == 'stay' else url, dest)
    if ok:
        why = BJS.photo_gate(dest, kind=kind, url=url, alt=alt)
        if why:
            dest.unlink(missing_ok=True)
            try: BJS.log_reject(str(RAW.parent / 'no-photo-found.csv'), dest.stem, '', url, why)
            except Exception: pass
            return False
    return ok

def _download_raw(url: str, dest: Path) -> bool:
    if not url or url.startswith('data:'):
        return False
    if dest.exists() and dest.stat().st_size >= BJS.env_int('BJ_MIN_IMG_BYTES', 5120):
        return True
    dest.parent.mkdir(parents=True, exist_ok=True)
    url2 = re.sub(r'/320x320_square_', '/640x640_rect_', url)
    for u in (url2, url):
        r = subprocess.run(
            ['curl', '-sL', '-A', UA, '-o', str(dest), '-w', '%{http_code}',
             '--max-time', '25', u],
            capture_output=True, text=True)
        code = (r.stdout or '').strip()
        if code == '200' and dest.exists() and dest.stat().st_size >= BJS.env_int('BJ_MIN_IMG_BYTES', 5120):
            return True
        if dest.exists():
            dest.unlink(missing_ok=True)
    return False

def extract_tabelog_list_images(html: str) -> dict[str, str]:
    img_map = {}
    # rst id near img
    for m in re.finditer(r'/(\d+)/[^"]*"[\s\S]{0,400}?src="(https://tblg\.k-img\.com/[^"]+)"', html):
        img_map[m.group(1)] = m.group(2).replace('&amp;', '&')
    for m in re.finditer(r'src="(https://tblg\.k-img\.com/[^"]+)"[\s\S]{0,400}?tabelog\.com/[a-z]+/A\d+/A\d+/(\d+)/', html):
        img_map[m.group(2)] = m.group(1).replace('&amp;', '&')
    return img_map

def extract_tabelog_detail_meta(html: str) -> dict:
    og = re.search(r'property="og:image"\s+content="([^"]+)"', html)
    home = re.search(r'ホームページ</th>\s*<td[^>]*>\s*<a[^>]+href="([^"]+)"', html)
    return {
        'og_image': (og.group(1).replace('&amp;', '&') if og else None),
        'homepage': home.group(1) if home else None,
    }

def fetch_official_og(homepage: str, dest: Path) -> tuple[bool, str]:
    code, html = curl(homepage, RAW / '_home_tmp.html', timeout=15)
    if code != 200:
        return False, homepage
    og = re.search(r'property="og:image"\s+content="([^"]+)"', html)
    if og and _download(og.group(1).replace('&amp;', '&'), dest, 'dining'):
        return True, homepage
    return False, homepage

def attach_dining_photos(slug: str, union: dict, tabelog: dict, prefer_list: bool = True) -> dict:
    img_map = {}
    rawdir = RAW / slug
    for p in sorted(list(rawdir.glob('tabelog-p*.html')) + list(rawdir.glob('tabelog-*-p*.html'))):
        img_map.update(extract_tabelog_list_images(p.read_text(encoding='utf-8', errors='replace')))
    for i, d in enumerate(union.get('dining') or []):
        if d.get('photo') and Path(CUTOVER, d['photo'].replace('../../', '')).exists():
            continue
        photo = credit = source_kind = None
        tb_url = d.get('tabelog_url')
        rid = d.get('rst_id')
        if not rid and tb_url:
            m = re.search(r'/(\d+)/?$', tb_url)
            rid = m.group(1) if m else None
        fname = f'{MP}{slug}-dining-{rid or ("ta"+str(d.get("ta_rank") or i+1))}.jpg'
        dest = MEDIA / fname
        if prefer_list and rid and rid in img_map:
            if _download(img_map[rid], dest):
                photo = f'../../media/{fname}'
                credit = f'source · Source {tb_url}'
                source_kind = 'tabelog'
        if not photo and tb_url:
            detail_path = rawdir / f'tabelog-detail-{rid}.html'
            if not detail_path.exists():
                code, html = curl(tb_url, detail_path, timeout=20)
                sleep_polite(0.15)
            else:
                html = detail_path.read_text(encoding='utf-8', errors='replace'); code = 200
            if code == 200 and html:
                meta = extract_tabelog_detail_meta(html)
                if meta.get('og_image') and _download(meta['og_image'], dest):
                    photo = f'../../media/{fname}'
                    credit = f'source · Source {tb_url}'
                    source_kind = 'tabelog'
        if not photo and d.get('ta_url') and disk_avail_gib() >= 10.0:
            ta_path = rawdir / f'ta-detail-{d.get("ta_rank")}.html'
            if not ta_path.exists():
                code, html = curl(d['ta_url'], ta_path, timeout=25)
                sleep_polite(0.2)
            else:
                html = ta_path.read_text(encoding='utf-8', errors='replace'); code = 200
            if code == 200:
                og = re.search(r'property="og:image"\s+content="([^"]+)"', html)
                if og and _download(og.group(1).replace('&amp;', '&'), dest, 'stay'):
                    photo = f'../../media/{fname}'
                    credit = f'source · Source {d["ta_url"]}'
                    source_kind = 'tripadvisor'
        d['photo'] = photo
        d['photo_credit'] = credit
        d['photo_source'] = source_kind
        if not photo:
            d['photo_missing'] = True
    return union

def attach_stay_photos(slug: str, union: dict, jalan: dict) -> dict:
    for i, s in enumerate(union.get('stay') or []):
        fname = f'{MP}{slug}-stay-{i+1}.jpg'
        dest = MEDIA / fname
        photo = credit = None
        img = s.get('image')
        if img and _download(img, dest, 'stay', s.get('image_alt') or ''):
            photo = f'../../media/{fname}'
            credit = 'source'
        if not photo and s.get('jalan_url'):
            yad = RAW / slug / f'jalan-yad-{i+1}.html'
            if not yad.exists():
                code, html = curl(s['jalan_url'], yad, timeout=25)
            else:
                html = yad.read_bytes().decode('cp932', errors='replace'); code = 200
            if code == 200:
                og = re.search(r'property="og:image"\s+content="([^"]+)"', html)
                if og and _download(og.group(1).replace('&amp;', '&'), dest, 'stay'):
                    photo = f'../../media/{fname}'
                    credit = 'source'
        s['photo'] = photo
        s['photo_credit'] = credit
        if not photo:
            s['photo_missing'] = True
    return union
