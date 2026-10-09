#!/usr/bin/env python3
"""Item 3 step 5: append confirmed inns to Stay (after the existing cards, in Jalan listing order), 4-line cards."""
import sys, re, json, html, csv, collections
sys.path.insert(0, '/workspace/p1/phase-d/w3')
from cards_lib import *
EN = {'354300': 'Shin-Tamagawa Onsen', '314054': 'Kakunodate Onsen Machiyado Neko no Suzu', '399180': 'Kakunodate Onsen Kayokan',
 '343740': 'Harazuru Onsen Ryokan Satoso', '323138': 'Tabist Business Ryokan Duck Ishinomaki Hebita', '355965': 'Yumoto Fubokaku',
 '317413': 'Sankei no Yado Ryusen', '389391': 'Oyado Hanabusa', '312522': 'Ryusen Bettei Kanzan Chogetsu', '338447': 'Minshuku Okimiya',
 '365176': 'Kesennuma Oshima Ryokan Akemiso', '379961': 'Ryokan Kuroshio', '329817': 'Minshuku Sakinoya', '330066': 'Minshuku Hamanasu',
 '304896': 'Kesennuma Oshima Ryokan Kameyamaso', '303442': 'Ryokan Tsubakiso Kagetsu', '336928': 'Heilsam Kurikoma',
 '304322': 'Matsushima Onsen Matsushima Ichinobo', '374328': 'Matsushima Sakan Shoan', '398377': 'Matsushima Onsen Palace Matsushima',
 '318480': 'Minamisanriku Manabi no Sato Iriyado', '381154': 'Gyoka Minshuku Yasuragi', '322547': 'Unagiyu no Yado Shunjuan Takuhide',
 '375215': 'Ryokan Sannojoyu', '395907': 'Ryokan Nanbuya', '391225': 'Ryokan Higashitaga no Yu', '344900': 'Pension Morinko',
 '312096': 'Todoroki Ryokan', '366316': 'Nakayamadaira Onsen Naruko Yasuragiso', '380000': 'Nakayamadaira Onsen Asuka Ryokan',
 '339147': 'Ryokan Bentenkaku', '324996': 'Pension Soramame', '335731': 'Pension Rainbow Hills', '305202': 'Pension Hidamari',
 '361526': 'Ryoan Fukinoto', '351358': 'Miwa to Sora', '311885': 'Kokonoe Kanko Hotel', '346611': 'Kabeyu Onsen Fukumotoya',
 '332454': 'Hosenji Onsen Kinosato Yamanoyu', '337728': 'Ryokan Nanakamado', '312591': 'Minshuku Hekiunso',
 '312794': 'Yama no Yado Reisen Kannojigoku Ryokan', '342615': 'Ryokan Meizan', '300892': 'Shukubo Hanashinobu',
 '305646': 'Keikoku no Yado Nihiki no Oni', '323942': 'Oita Kokonoe Kuoritei', '321921': 'Ryokan Kakuoya', '303518': 'Wa no Yado Kappo Mikuniya',
 '330841': 'Nagayu Onsen Daimaru Ryokan', '305294': 'Kuju Kogen Ginga no Yado Kinoko Niseigo', '382450': 'Yufu no Iyashi Yuri',
 '312931': 'Oyado Kaikatei', '324644': 'Yufuin Onsen Ryokan Fukinoya', '321091': 'Iyashi no Sato Kanputei', '375414': 'Yufuin Lamp no Yado',
 '342312': 'Yufuin Hoteiya', '333628': 'Yufuin Onsen Yufuri no Yado Ikkoten', '373325': 'Yufuin Onsen Hasuwa Inn'}
cards = json.load(open('i3_cards_photo.json'))
by = collections.defaultdict(list)
for c in cards: by[c['page']].append(c)
rows = []; st = collections.Counter()
for page, p in pages():
    if page not in by: continue
    s = open(p).read(); m, d = section_cards(s, 'Stay')
    body = m.group(2)
    metas = [x['meta'] for x in d]; muni = re.match(r'#\d+ ranked in (.+)$', metas[0]).group(1)
    have = set(re.findall(r'jalan_url=(\S+)', body))
    new = sorted([c for c in by[page] if c['jalan_url'] not in have], key=lambda c: (c['order'] is None, c['order'] or 0))
    st['skipped already in Stay'] += len(by[page]) - len(new)
    n = len(d); add = ''
    for c in new:
        n += 1; ph = c['photo']; ja = html.escape(c['disp'], quote=False); en = EN[c['yid']]
        add += (f'<li><a href="{c["jalan_url"]}"><p class="place-name">{ja}</p>'
                f'<img class="thumb" src="https://img.bokenjapan.com/{ph["key"]}" alt="{html.escape(c["disp"], quote=True)}" loading="lazy" decoding="async" width="{ph["w"]}" height="{ph["h"]}"></a>'
                f'<p class="place-blurb">{html.escape(en, quote=False)}</p><p class="place-meta">#{n} ranked in {muni}</p><p class="place-desc">{html.escape(c["line4"], quote=False)}</p>'
                f'<!-- desc-source: {c["jalan_url"]} --><!-- photo-credit: source · Source {ph["page"]} --><!-- sources: jalan_url={c["jalan_url"]} --></li>')
        rows.append(dict(page=page, rank=n, name_ja=c['disp'], name_en=en, jalan_url=c['jalan_url'], tabelog_url=c['tabelog_url'], match=c.get('how', ''),
                         line4=c['line4'], photo_kind=ph['kind'], photo_src=ph['src'], photo_page=ph['page'], r2_key=ph['key']))
        st['added'] += 1
    assert body.rstrip().endswith('</li></ul>')
    i = m.start(2) + len(body.rstrip()) - len('</ul>')
    s = s[:i] + add + s[i:]
    open(p, 'w').write(s); st['pages'] += 1
with open('inns-added-w5.csv', 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
print(dict(st))
