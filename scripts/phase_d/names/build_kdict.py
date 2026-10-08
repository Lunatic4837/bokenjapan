import gzip, re, json
s = gzip.open('JMdict_e.gz','rt',encoding='utf-8').read()
KATA = re.compile(r'^[\u30a0-\u30ffー]+$')
d = {}
for e in re.finditer(r'<entry>(.*?)</entry>', s, re.S):
    b = e.group(1)
    if '<k_ele>' in b: continue
    rebs = re.findall(r'<reb>(.*?)</reb>', b)
    sense = re.search(r'<sense>(.*?)</sense>', b, re.S)
    if not sense: continue
    sb = sense.group(1)
    if re.search(r'<misc>&(arch|obs|vulg|derog|sl|abbr);</misc>', sb): continue
    if re.search(r'<lsource xml:lang="(?!eng)', sb): pass  # non-English loans still have English gloss; keep
    gl = re.findall(r'<gloss[^>]*>(.*?)</gloss>', sb)
    if not gl: continue
    g = re.sub(r'\s*\(.*?\)\s*', ' ', gl[0]).strip()
    if not g or not re.fullmatch(r"[A-Za-z][A-Za-z' &.-]*", g) or len(g.split()) > 3: continue
    pri = 1 if '<re_pri>' in b else 0
    for r in rebs:
        r = r.replace('・', '')
        if KATA.match(r) and len(r) >= 2:
            if r not in d or pri > d[r][1]: d[r] = (g, pri)
out = {k: v[0] for k, v in d.items()}
json.dump(out, open('kdict.json','w'), ensure_ascii=False)
print(len(out), [ (k,out.get(k)) for k in ['ホテル','ステーション','グランド','プラザ','レディース','ニュー','サンライズ','イン','ジャーマン','ベーカリー','ミッション','バレー','ゴルフ','クラブ','ライトアップ','グランピング','ラーメン','カフェ','レストラン','スナック','バー','パン','ハウス','ゲスト','ビジネス','リゾート','スーパー','センター','ショッピング','ガイア','ドミトリー','パレス','キッチン','ダイニング','ベーカリー','ピザ','カレー','そば']])
