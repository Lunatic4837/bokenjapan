#!/usr/bin/env python3
import json, re, html, os, sys, collections, glob
REPO = '/workspace/p1/pr12-work'
D = json.load(open('/workspace/p1/phase-d/line4_all.json'))
SEC = re.compile(r'(<section class="place-section">\s*<h2>([^<]+)</h2>)(.*?)(</section>)', re.S)
LI = re.compile(r'<li\b[^>]*>.*?</li>', re.S)
st = collections.Counter(); left = []
for p in sorted(glob.glob(f'{REPO}/*/*/index.html')):
    pg = os.path.relpath(os.path.dirname(p), REPO)
    s = open(p, encoding='utf-8').read(); orig = s
    def fix(m):
        sec = m.group(2).strip(); body = m.group(3); out = []; last = 0
        for i, lm in enumerate(LI.finditer(body), 1):
            li = lm.group(0)
            if 'class="place-desc"' not in li:
                ck = f'{pg}|{sec}|{i}'; r = D.get(ck)
                nm = re.search(r'<p class="place-name">(.*?)</p>', li, re.S)
                name = html.unescape(nm.group(1)) if nm else ''
                if r and r['name_ja'] == name:
                    ins = f'<p class="place-desc">{html.escape(r["line"], quote=False)}</p>' + (f'<!-- desc-source: {r["src"]} -->' if r.get('src') else '')
                    mm = list(re.finditer(r'<p class="place-meta">.*?</p>', li, re.S))
                    if mm: li = li[:mm[-1].end()] + ins + li[mm[-1].end():]
                    else:
                        lp = list(re.finditer(r'</p>', li)); li = li[:lp[-1].end()] + ins + li[lp[-1].end():]
                    st['applied', r['kind'], sec] += 1
                else:
                    st['left', sec, 'mismatch' if r else 'nokey'] += 1; left.append((ck, name, r['name_ja'] if r else None))
            out.append(body[last:lm.start()]); out.append(li); last = lm.end()
        out.append(body[last:]); return m.group(1) + ''.join(out) + m.group(4)
    s = SEC.sub(fix, s)
    if s != orig: open(p, 'w', encoding='utf-8').write(s); st['pages'] += 1
for k, v in sorted(st.items(), key=str): print(k, v)
json.dump(left, open('/workspace/p1/phase-d/line4_left.json', 'w'), ensure_ascii=False, indent=0)
print('left sample', left[:10])
