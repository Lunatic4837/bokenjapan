#!/usr/bin/env python3
"""Normalize Official links to https; replace known-dead hosts with localgovjp URLs when available."""
from __future__ import annotations
import json, re, subprocess
from pathlib import Path
from common import CUTOVER, load_hubs, UA

PREF = CUTOVER / 'hokkaido'
LOCAL = Path('/workspace/p1/data/catalog-uplift/hubs/_localgovjp.json')

# Manual overrides when localgov URL also dead / better mirror known
OVERRIDES = {
  # try https first; overrides only if needed after HEAD
}

def head(url: str) -> int:
    r = subprocess.run(['curl','-sI','-L','-A',UA,'-o','/dev/null','-w','%{http_code}','--max-time','20',url],
                       capture_output=True, text=True)
    return int((r.stdout or '0').strip() or '0')

def main():
    hubs = load_hubs('hokkaido')['hubs']
    local = {x['city']: x for x in json.loads(LOCAL.read_text()) if x.get('pref')=='北海道'}
    report=[]
    for p in sorted(PREF.glob('*/index.html')):
        slug=p.parent.name
        html=p.read_text(encoding='utf-8', errors='replace')
        m=re.search(r'<h2>Official</h2>\s*<p><a href="([^"]+)"', html)
        if not m:
            report.append({'slug':slug,'status':'no_official'}); continue
        url=m.group(1)
        new=url
        if url.startswith('http://'):
            new='https://'+url[len('http://'):]
        h=hubs.get(slug) or {}
        name_ja=h.get('name_ja')
        # probe
        code=head(new)
        if code in (0,404,410) or code >= 500:
            alt=(local.get(name_ja) or {}).get('url') or ''
            if alt:
                alt = alt if alt.startswith('https') else alt.replace('http://','https://')
                code2=head(alt)
                if code2 and code2 < 400:
                    new=alt; code=code2
                else:
                    # leave https attempt; note fail
                    pass
        if new != url:
            html=html.replace(f'href="{url}"', f'href="{new}"', 1)
            p.write_text(html, encoding='utf-8')
        report.append({'slug':slug,'old':url,'new':new,'code':code})
        print(slug, code, new, flush=True)
    Path('/workspace/p1/data/catalog-uplift/out/hokkaido-official-report.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
