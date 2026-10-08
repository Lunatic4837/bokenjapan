import re,glob,html,json
REPO='/workspace/p1/pr12-work'
SEC=re.compile(r'<section class="place-section"><h2>(.*?)</h2>(.*?)</section>',re.S)
gen=re.compile(r'^(?:An? )?[A-Za-z\'\- ]+ in [A-Za-z\-ōū\' ]+, [A-Za-z]+(?: prefecture)?\.$')
cards=[]
for p in sorted(glob.glob(f'{REPO}/*/*/index.html')):
    pref,slug=p.split('/')[-3:-1]
    if pref not in ('miyagi','akita','fukuoka','yamaguchi','oita'): continue
    s=open(p,encoding='utf-8').read()
    for m in SEC.finditer(s):
        if m.group(1)!='Stay': continue
        for i,li in enumerate(re.findall(r'<li\b.*?</li>',m.group(2),re.S)):
            d=re.search(r'<p class="place-desc">(.*?)</p>',li); d=html.unescape(d.group(1)) if d else ''
            if gen.match(d):
                j=re.search(r'jalan_url=(\S+)',li); nm=re.search(r'<p class="place-name">(.*?)</p>',li)
                cards.append(dict(page=f'{pref}/{slug}',idx=i,old=d,jalan=html.unescape(j.group(1)) if j else None,name=html.unescape(nm.group(1)) if nm else ''))
json.dump(cards,open('cards.json','w'),ensure_ascii=False,indent=0)
print(len(cards),len({c['jalan'] for c in cards}))
