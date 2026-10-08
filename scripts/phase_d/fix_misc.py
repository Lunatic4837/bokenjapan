#!/usr/bin/env python3
import re, html, glob, os, unicodedata, csv, collections, json
REPO = '/workspace/p1/pr12-work'
OLD = 'https://pub-f074f228689740b2a22b36f38e90e96e.r2.dev'; NEW = 'https://img.bokenjapan.com'
CJK = re.compile(r'[\u3040-\u30ff\u3400-\u9fff\uf900-\ufaff]')
MANUAL_EN = {'そば 寿ゞ喜支店': 'Soba Suzuki Shiten', '心粋厨房 獬': 'Shinsui Chūbō Kai', '珈湖璐': 'Kakoro', '珉亭': 'Mintei',
             '皕': 'Hyoku', '小哪吒麻辣燙 新宮店': 'Xiao Nezha Malatang Shingū', '麺家 你好': 'Menya Nihao'}
# TA-only cards whose line 1 is Latin: Japanese name from the matched listing used for the photo
JA = {}
for r in csv.DictReader(open('/workspace/p1/photos-5pref/manifest.csv')):
    if CJK.search(r['name_ja'] or '') and not CJK.search(r['card_name_on_page'] or ''):
        JA[(r['card_key'].split('|')[0], r['listing_url'])] = (r['card_name_on_page'], r['name_ja'])
st = collections.Counter()
LI = re.compile(r'<li\b[^>]*>.*?</li>', re.S)
def spaced_fix(b, name):
    if re.fullmatch(r'(?:\S ){3,}\S', b):
        n = unicodedata.normalize('NFKC', name).replace('\u3000', ' ').strip()
        if not CJK.search(n): return re.sub(r'\s+', ' ', n)
        return None
    return b
pages = sorted(glob.glob(f'{REPO}/*/*/index.html')) + sorted(glob.glob(f'{REPO}/*/index.html')) + [f'{REPO}/index.html']
for p in pages:
    s = open(p, encoding='utf-8').read(); o = s
    if OLD in s: st['r2_swap_pages'] += 1; s = s.replace(OLD, NEW)
    if p.count('/') - REPO.count('/') == 3:
        pg = os.path.relpath(os.path.dirname(p), REPO)
        h1 = re.search(r'<h1 class="page-title">(.*?)</h1>', s, re.S); muni = re.sub('<.*?>', '', h1.group(1)).strip()
        place = f'{muni}, {pg.split("/")[0].title()}'
        def fli(m):
            li = m.group(0)
            nm = re.search(r'<p class="place-name">(.*?)</p>', li, re.S)
            name = html.unescape(nm.group(1)) if nm else ''
            b = re.search(r'<p class="place-blurb">(.*?)</p>', li, re.S)
            if b:
                bt = html.unescape(b.group(1))
                nb = bt
                if name in MANUAL_EN and CJK.search(bt): nb = MANUAL_EN[name]
                else:
                    f = spaced_fix(bt, name)
                    if f and f != bt: nb = f
                if nb != bt:
                    li = li.replace(b.group(0), f'<p class="place-blurb">{html.escape(nb, quote=False)}</p>', 1); st['en_fixed'] += 1
            d = re.search(r'<p class="place-desc">(.*?)</p>', li, re.S)
            if d:
                dt = html.unescape(d.group(1)).strip()
                bt2 = html.unescape(b.group(1)) if b else ''
                if len(dt) < 15 or dt.lower() == bt2.strip().lower():
                    nd = f'{dt.rstrip(".")} in {place}.' if dt.lower() != bt2.strip().lower() else None
                    if nd and len(nd) >= 15:
                        li = li.replace(d.group(0), f'<p class="place-desc">{html.escape(nd, quote=False)}</p>', 1); st['desc_lengthened'] += 1
                    else: st['desc_short_left'] += 1
            href = re.search(r'<!-- sources: ([^>]*?)-->', li)
            im = re.search(r'<img class="thumb" src="[^"]*/media/([^"/]+)"', li)
            if im and href and not re.search(r'<!-- photo-credit:\s*\S[^>]*-->', li):
                fnm = im.group(1); cred = None
                tb = re.search(r'tabelog_url=(\S+)', href.group(1)); ta = re.search(r'ta_url=(\S+)', href.group(1))
                mid = re.search(r'-(\d{5,9})(?:-p)?\.\w+$', fnm); mta = re.search(r'-ta(\d+)(?:-p)?\.\w+$', fnm)
                if mid and tb and tb.group(1).rstrip('/').endswith('/' + mid.group(1)):
                    cred = f'{name} (食べログ) · Source {html.unescape(tb.group(1))}'
                elif mta and ta and f'-d{mta.group(1)}-' in ta.group(1):
                    cred = f'{name} (Tripadvisor) · Source {html.unescape(ta.group(1))}'
                elif mta and ta and not tb:
                    # TA-only card: the only listing the photo step had for it was this Tripadvisor page
                    cred = f'{name} (Tripadvisor listing photo) · Source {html.unescape(ta.group(1))}'
                if cred:
                    cred = cred.replace('--', '–')
                    if re.search(r'<!-- photo-credit:[^>]*-->', li): li = re.sub(r'<!-- photo-credit:[^>]*-->', lambda _: f'<!-- photo-credit: {cred} -->', li, count=1)
                    else: li = li.replace('<!-- sources:', f'<!-- photo-credit: {cred} --><!-- sources:', 1)
                    st['credit_restored'] += 1
                else: st['credit_unknown'] += 1
            if nm and not CJK.search(name) and href:
                ta = re.search(r'ta_url=(\S+)', href.group(1))
                key = (pg, html.unescape(ta.group(1)) if ta else None)
                if key in JA and JA[key][0] == name:
                    ja = JA[key][1]
                    li = li.replace(nm.group(0), f'<p class="place-name">{html.escape(ja, quote=False)}</p>', 1)
                    if not b:
                        pass
                    st['ja_name_restored'] += 1
            return li
        s = LI.sub(fli, s)
    if s != o: open(p, 'w', encoding='utf-8').write(s); st['pages_changed'] += 1
for f in ['scripts/build-pages-site.py', 'scripts/render_phase_c.py', 'scripts/r2_images.py']:
    fp = f'{REPO}/{f}'
    if os.path.exists(fp):
        t = open(fp).read()
        if OLD in t: open(fp, 'w').write(t.replace(f'R2_BASE = "{OLD}"', f'R2_BASE = "{NEW}"')); st['script:' + f] += 1
print(dict(st))

# ---- rows whose only recorded URL was dead: link to the current official/tourism page (found 2026-10-09) ----
LINKS = {
 ('miyagi/kamimachi', 'Yakurai Souvenir &amp; Mountain Goods Center'): 'https://www.yakurai-dosan.jp/',
 ('miyagi/kamimachi', 'Otaki Rural Park Campground'): 'https://www.town.kami.miyagi.jp/kanko_sports_bunka/kanko_tokusan/kankoshisetsu/1420.html',
 ('miyagi/kamimachi', 'Arasawa Nature Hall'): 'https://www.town.kami.miyagi.jp/soshikikarasagasu/shinrinseibitaisakushitsu/kankoshisetsu/909.html',
 ('miyagi/kamimachi', 'Nakaniida Culture Hall Bach Hall'): 'https://www.town.kami.miyagi.jp/soshikikarasagasu/nakaniidabachhall/index.html',
 ('miyagi/kamimachi', 'Kirikomi Pottery Memorial Hall'): 'https://www.town.kami.miyagi.jp/soshikikarasagasu/furusatotogeikan/700.html',
 ('miyagi/kamimachi', 'Bokusetsu Ink Painting Museum'): 'https://www.town.kami.miyagi.jp/soshikikarasagasu/tohokutojibunkakan/767.html',
 ('miyagi/kamimachi', 'Fureai-no-Mori Park Golf'): 'https://kami-tabi.com/facility/167/',
 ('miyagi/matsushima', 'Matsushima Yacht Harbor'): 'https://moyc.skr.jp/',
 ('miyagi/taiwa', 'Himemiya Shrine'): 'https://www.miyagi-jinjacho.or.jp/jinja-search/detail.php?code=310020384',
 ('miyagi/taiwa', 'Shijuhattaki Auto Campground'): 'https://www.town.taiwa.miyagi.jp/soshiki/shokokanko/shokokanko/424.html',
 ('miyagi/taiwa', 'Nanatsumori Fureai-no-Sato'): 'https://shinko-ko-sha.sakura.ne.jp/',
 ('yamaguchi/hofu', '(Hofu Keirinjo) Fudan Miru Koto no Dekinai Basho Wogo Annai Suru Bakkuyado Tour'): 'https://visit-hofu.jp/yamaguchidc-hofukeirin-1/',
}
REWRITE = {  # visible text corrections, from the linked official pages
 'Bokusetsu Ink Painting Museum': ('Bokusetsu Ink Painting Exhibition Room', 'Shimoniida Matsuki 3 (Nakaniida Exchange Center 2F), Kami, Miyagi · 0229-63-3113',
     'About 50 ink paintings by Bokusetsu (Kawai Toshio), shown since the old museum closed in 2017'),
 '(Hofu Keirinjo) Fudan Miru Koto no Dekinai Basho Wogo Annai Suru Bakkuyado Tour': ('Hofu Velodrome Backyard Tour', None,
     'Guided tour of the Hofu keirin velodrome areas normally closed to visitors'),
}
n = 0
for (pg, nm), url in LINKS.items():
    p = f'{REPO}/{pg}/index.html'; s = open(p, encoding='utf-8').read(); o = s
    def wrap(m):
        global n
        li = m.group(0)
        if f'<p class="place-name">{nm}</p>' not in li or '<a href' in li: return li
        img = re.search(r'<img class="thumb"[^>]*>', li)
        body = li.replace(img.group(0), '') if img else li
        newname = nm; meta_new = desc_new = None
        if nm in REWRITE: newname, meta_new, desc_new = REWRITE[nm]
        head = f'<a href="{url}"><p class="place-name">{newname}</p>{img.group(0) if img else ""}</a>'
        body = body.replace(f'<p class="place-name">{nm}</p>', head, 1)
        if nm in REWRITE:
            body = re.sub(r'<p class="place-blurb">.*?</p>', '', body, count=1)
            if meta_new: body = re.sub(r'<p class="place-meta">(.*?)</p>', lambda mm: f'<p class="place-meta">{mm.group(1).split(" · ")[0]} · {meta_new}</p>', body, count=1)
            body = re.sub(r'<p class="place-desc">.*?</p>', f'<p class="place-desc">{desc_new}</p>', body, count=1)
            body = body.replace(f'alt="{nm}"', f'alt="{newname}"')
        body = body.replace('</li>', f'<!-- desc-source: {url} --></li>') if 'desc-source' not in body else body
        n += 1
        return body
    s = LI.sub(wrap, s)
    if s != o: open(p, 'w', encoding='utf-8').write(s)
print('relinked rows', n)
