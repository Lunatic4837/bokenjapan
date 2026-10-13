#!/usr/bin/env python3
"""Backfill missing Hokkaido covers from Wikipedia/Commons (ja.wikipedia page summary), sourced only."""
from __future__ import annotations
import json, re, subprocess, time, urllib.parse
from pathlib import Path
from common import MEDIA, CUTOVER, load_hubs, UA, disk_avail_gib

PREF = CUTOVER / 'hokkaido'
CREDIT = 'Wikimedia Commons via Japanese Wikipedia'

def curl_bytes(url: str, dest: Path, timeout: int = 40) -> int:
    dest.parent.mkdir(parents=True, exist_ok=True)
    cmd = ['curl','-sL','-A',UA,'-o',str(dest),'-w','%{http_code}','--max-time',str(timeout),
           '-H','Accept-Language: ja,en;q=0.8', url]
    r = subprocess.run(cmd, capture_output=True, text=True)
    return int((r.stdout or '0').strip() or '0')

def wiki_image(name_ja: str) -> tuple[str,str,str] | None:
    if not name_ja: return None
    # Prefer 「市/町/村」 page
    title = urllib.parse.quote(name_ja, safe='')
    url = f'https://ja.wikipedia.org/api/rest_v1/page/summary/{title}'
    dest = Path('/tmp/wiki_sum.json')
    code = curl_bytes(url, dest, timeout=25)
    if code != 200 or not dest.exists():
        return None
    try:
        d = json.loads(dest.read_text(encoding='utf-8'))
    except Exception:
        return None
    img = (d.get('originalimage') or {}).get('source') or (d.get('thumbnail') or {}).get('source')
    if not img:
        return None
    # strip tracking params
    img = img.split('?')[0]
    page = d.get('content_urls',{}).get('desktop',{}).get('page') or f'https://ja.wikipedia.org/wiki/{title}'
    alt = d.get('titles',{}).get('display') or name_ja
    return img, alt, page

def inject_cover(html: str, file_name: str, alt: str, source_url: str) -> str:
    alt = re.sub(r'[<>\"]', '', alt)[:80]
    fig = (
        f'<figure class="cover"><img src="../../media/{file_name}" alt="{alt}" width="1280" height="853" loading="lazy">'
        f'<!-- photo-credit: {CREDIT} · Source {source_url} --></figure>'
    )
    if 'figure class="cover"' in html:
        return re.sub(r'<figure class="cover">.*?</figure>', fig, html, count=1, flags=re.S)
    if '<section class="meta-block">' in html:
        return html.replace('<section class="meta-block">', fig + '<section class="meta-block">', 1)
    return html.replace('</main>', fig + '</main>', 1)

def main(slugs: list[str] | None = None):
    hubs = load_hubs('hokkaido')['hubs']
    if not slugs:
        slugs = []
        for p in sorted(PREF.glob('*/index.html')):
            slug = p.parent.name
            if slug.startswith('jis01'):
                continue
            html = p.read_text(encoding='utf-8', errors='replace')
            if 'figure class="cover"' not in html:
                slugs.append(slug)
    report = {'ok': [], 'fail': []}
    for slug in slugs:
        if disk_avail_gib() < 8.0:
            print('PAUSE_DISK'); break
        h = hubs.get(slug) or {}
        html_path = PREF / slug / 'index.html'
        html = html_path.read_text(encoding='utf-8', errors='replace')
        if 'figure class="cover"' in html:
            report['ok'].append(slug); continue
        name_ja = h.get('name_ja') or ''
        print('cover', slug, name_ja, flush=True)
        hit = wiki_image(name_ja)
        time.sleep(0.2)
        if not hit:
            report['fail'].append(slug); print('  FAIL'); continue
        img_url, alt, page = hit
        ext = Path(urllib.parse.urlparse(img_url).path).suffix.lower() or '.jpg'
        if ext not in ('.jpg','.jpeg','.png','.webp','.gif'):
            ext = '.jpg'
        fname = f'{slug}-cover-wiki{ext}'
        dest = MEDIA / fname
        code = curl_bytes(img_url, dest)
        if code != 200 or not dest.exists() or dest.stat().st_size < 2000:
            report['fail'].append(slug); print('  FAIL img', code); continue
        html2 = inject_cover(html, fname, alt or h.get('name_en') or slug, page)
        html_path.write_text(html2, encoding='utf-8')
        report['ok'].append(slug)
        print('  OK', fname, dest.stat().st_size, flush=True)
    Path('/workspace/p1/data/catalog-uplift/out/hokkaido-cover-report.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2))
    print('done ok', len(report['ok']), 'fail', len(report['fail']))
    if report['fail']:
        print('fail slugs', report['fail'][:40])

if __name__ == '__main__':
    import sys
    main(sys.argv[1:] or None)
