#!/usr/bin/env python3
"""Deepen a thin municipality's Dining from Tabelog (rating-ordered area list), then re-hub it with template_hub.py.
New cards: real name (official EN in 店名 parentheses when present, else natural_en), Tabelog genre line, og photo
(no photo -> skipped), address must contain the town's JA name (locality rule). Existing cards keep their ranks; new
ones continue the numbering. All cards are pooled back into a flat page and rebuilt with the Ohira hub template.
  python3 deepen_dining.py --root <site> --pref yamagata --muni yamagatashi --area https://tabelog.com/yamagata/A0601/A060101/ --target 150
"""
import re, os, io, sys, json, html, glob, shutil, argparse, subprocess, tempfile, time
from PIL import Image, ImageStat
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from en_natural import natural_en
src = open(os.path.join(HERE, 'cos_fix.py')).read(); exec(src[src.index('GENRE = {'):src.index('def esc(')])
UA = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36'
TB = '/workspace/p1/data/template4/tb.jsonl'
cl = lambda x: re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', x or ''))).strip()
def get(u): return subprocess.run(['curl', '-sL', '--compressed', '--max-time', '30', '-A', UA, u], capture_output=True).stdout
def row(s, k):
    m = re.search(k + r'</th>\s*<td[^>]*>(.*?)</td>', s, re.S); return cl(m.group(1)) if m else ''
def lis_in(f): return re.findall(r'<li><a href="https?://.*?</li>', open(f).read(), re.S)
def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--root', required=True); ap.add_argument('--pref', required=True); ap.add_argument('--muni', required=True)
    ap.add_argument('--area', required=True); ap.add_argument('--target', type=int, default=150); ap.add_argument('--pages', type=int, default=12); A = ap.parse_args()
    base = f'{A.root}/{A.pref}/{A.muni}'; hub = open(f'{base}/index.html').read()
    muni_ja = re.search(r'<!-- muni-ja: ([^ ]+) -->', hub).group(1)
    town = html.unescape(re.search(r'<h1 class="page-title">([^<]+)</h1>', hub).group(1))
    P = html.unescape(re.search(r'<p class="crumb"><a href="/">Japan</a> / <a href="[^"]*">([^<]+)</a>', hub).group(1))
    stay, dining, sights, seen = [], [], [], set()
    for f in sorted(glob.glob(f'{base}/*/**/index.html', recursive=True)):
        sec = f[len(base) + 1:].split('/')[0]
        for li in lis_in(f):
            href = re.search(r'<a href="([^"]+)"', li).group(1)
            if href in seen: continue
            seen.add(href)
            if sec == 'stay': stay.append(li)
            elif re.search(r'sources: [^>]*(tabelog_url|ta_url)=', li): dining.append(li)
            else: sights.append(li)
    rk = lambda li: int((re.search(r'#(\d+) ranked', li) or [0, 10**6])[1])
    dining.sort(key=rk); nxt = max([rk(l) for l in dining if rk(l) < 10**6] or [0]) + 1
    have = {re.search(r'tabelog\.com/[^"\s]+?/(\d+)/', l).group(1) for l in dining if re.search(r'tabelog\.com/[^"\s]+?/(\d+)/', l)}
    added, tbf = 0, open(TB, 'a')
    for pg in range(1, A.pages + 1):
        if len(dining) >= A.target: break
        lst = get(f'{A.area.rstrip("/")}/rstLst/{pg}/?SrtT=rt').decode('utf-8', 'ignore')
        urls = list(dict.fromkeys(re.findall(r'href="(' + re.escape(A.area.rstrip('/')) + r'/(\d+)/)"', lst)))
        if not urls: break
        for u, rid in urls:
            if rid in have or len(dining) >= A.target: continue
            have.add(rid); s = get(u).decode('utf-8', 'ignore'); time.sleep(0.4)
            addr = row(s, '住所').replace(' ', ''); g = row(s, 'ジャンル'); nm = row(s, '店名')
            if muni_ja not in addr or not nm: continue
            og = html.unescape((re.search(r'og:image" content="([^"]+)', s) or [0, ''])[1])
            tbf.write(json.dumps({'u': u, 'code': '200', 'genre': g, 'og': og}, ensure_ascii=False) + '\n'); tbf.flush()
            if not og or re.search(r'no_?photo|no_?image|/images/', og.split('?')[0].replace('/restaurant/images/', '/r/')): continue
            dest = f'{A.root}/media/{A.muni}-dining-{rid}.webp'
            if not os.path.exists(dest):
                try:
                    im = Image.open(io.BytesIO(get(og))).convert('RGB')
                    if min(im.size) < 200 or ImageStat.Stat(im.convert('L').resize((64, 64))).stddev[0] < 15: continue
                    if im.width > 480: im = im.resize((480, round(im.height * 480 / im.width)))
                    im.save(dest, 'WEBP', quality=72, method=5)
                except Exception: continue
            with Image.open(dest) as im: w, h = im.size
            m = re.match(r'(.*?)\s*[（(]([A-Za-z][^）)]*)[）)]\s*$', nm)
            ja, en = (m.group(1), m.group(2)) if m else (nm, natural_en(nm, muni_ja, town))
            gs = [x.strip() for x in re.split(r'[、,]', g) if x.strip()]
            lab = next((GENRE[x] for x in gs if x in GENRE), None)
            desc = f'<p class="place-desc">{html.escape(f"{lab} in {town}, {P}.")}</p><!-- desc-source: {u} -->' if lab else ''
            dining.append(f'<li><a href="{u}"><p class="place-name">{html.escape(ja)}</p><img class="thumb" src="../../media/{os.path.basename(dest)}" alt="{html.escape(ja)}" width="{w}" height="{h}" loading="lazy"><!-- photo-credit: 食べログ · Source {u} --></a>'
                          f'<p class="place-blurb">{html.escape(en)}</p><p class="place-meta">#{nxt} ranked in {html.escape(town)}</p>{desc}<!-- locality-addr: {html.escape(addr)} --><!-- sources: tabelog_url={u} --></li>')
            nxt += 1; added += 1
    print(A.muni, 'existing+new dining', len(dining), 'added', added, flush=True)
    sec = lambda t, l: f'<section class="place-section"><h2>{t}</h2><ul class="place-list">{"".join(l)}</ul></section>'
    fix = lambda l: l.replace('src="/media/', 'src="../../media/')
    flat = re.sub(r'<section class="hub">.*?</section>', lambda m: sec('Stay', map(fix, stay)) + sec('Dining', map(fix, dining)) + sec('Sights', map(fix, sights)), hub, count=1, flags=re.S)
    flat = flat.replace('<body class="hubbed">', '<body>', 1)
    tmp = tempfile.mkdtemp(prefix='rehub-', dir='/workspace/p1')
    os.makedirs(f'{tmp}/{A.pref}/{A.muni}'); os.symlink(os.path.abspath(f'{A.root}/media'), f'{tmp}/media')
    open(f'{tmp}/{A.pref}/{A.muni}/index.html', 'w').write(flat)
    r = subprocess.run([sys.executable, os.path.join(HERE, 'template_hub.py'), '--root', tmp, '--pref', A.pref], capture_output=True, text=True); print(r.stdout[-600:], r.stderr[-1500:])
    if r.returncode == 0:
        for d in glob.glob(f'{base}/*/'): shutil.rmtree(d)
        for item in os.listdir(f'{tmp}/{A.pref}/{A.muni}'):
            s2, d2 = f'{tmp}/{A.pref}/{A.muni}/{item}', f'{base}/{item}'
            (shutil.copytree if os.path.isdir(s2) else shutil.copy)(s2, d2)
    os.unlink(f'{tmp}/media'); shutil.rmtree(tmp)
main()
