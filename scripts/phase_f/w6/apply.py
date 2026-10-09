import re,glob,json,csv,requests,html
FLAG={'t-museum.jp':'hijacked: adult dating ("パパ活") blog',
 'hakata.or.jp':'hijacked: redirects to rotating spam domains (fake bot-check pages)',
 'saiki-kankou.com':'expired: redirects to unrelated domain hotels-fukuoka.com',
 'toho-iwayacamp.com':'compromised: hidden casino/betting spam links',
 'kourataisya.or.jp':'compromised: hidden slot/judi gambling spam links',
 'xn--u9j140gtlqj7aq8v.com':'parked: domain for sale (nicsell auction redirect)',
 'namiha.jp':'dead: hosting DOMAIN ERROR page',
 'sekibutukankocenter.com':'repurposed: redirects to a different business (usarayama.com)'}
def dom_of(u): return (re.match(r'https?://([^/]+)',u) or [0,''])[1].lower()
def flagged(u):
    h=dom_of(u)
    for k in FLAG:
        if h==k or h.endswith('.'+k): return k
S=requests.Session();S.headers['User-Agent']='Mozilla/5.0 (Windows NT 10.0) Chrome/129.0'
rows=[]
pages=[p for p in glob.glob('*/*/index.html') if p.split('/')[0] in ('miyagi','akita','fukuoka','yamaguchi','oita')]
for p in pages:
    t=open(p).read(); orig=t
    def fix(m):
        li=m.group(0); a=re.match(r'<li><a href="([^"]+)"',li)
        if not a: return li
        k=flagged(a.group(1))
        if not k: return li
        new=None
        s=re.search(r'<!-- sources: ([^>]*)-->',li)
        if s:
            for key in ('jalan_url','ikyu_url','tabelog_url','tb_url'):
                mm=re.search(key+r'=(\S+)',s.group(1))
                if mm: new=mm.group(1); break
        if not new:
            mm=re.search(r'photo-credit: [^>]*?· Source (https?://\S+)',li)
            if mm: new=mm.group(1)
        if not new:
            mm=re.search(r'<!-- photo: 宮城まるごと探訪 id=(\d+)',li)
            if mm: new=f'https://www.miyagi-kankou.or.jp/theme/detail.php?id={mm.group(1)}'
        assert new,(p,li[:200])
        name=re.search(r'class="place-name">([^<]*)',li).group(1)
        rows.append(dict(page=p.rsplit('/',1)[0],card=html.unescape(name),old_url=a.group(1),new_url=new,domain=html.unescape(k.encode().decode('idna') if k.startswith('xn--') else k),reason=FLAG[k]))
        li=li.replace(f'<li><a href="{a.group(1)}"',f'<li><a href="{new}"',1)
        return li.replace('</li>',f'<!-- link-replaced-w6: {k} ({FLAG[k].split(":")[0]}) -->'+'</li>',1) if li.endswith('</li>') else li
    t=re.sub(r'<li><a href="[^"]+">.*?</li>',fix,t,flags=re.S)
    # any remaining href to flagged domain (non-card)
    for m in re.finditer(r'href="([^"]+)"',t):
        if flagged(m.group(1)): print('REMAINING',p,m.group(1))
    if t!=orig: open(p,'w').write(t)
for r in rows:
    x=S.get(r['new_url'],timeout=25); ti=(re.search(r'<title[^>]*>(.*?)</title>',x.text,re.S) or [0,''])[1].strip()[:50]
    r['new_status']=x.status_code; r['new_title']=ti
    print(r['page'],'|',r['card'],'|',r['domain'],'->',r['new_url'],x.status_code,ti)
with open('/workspace/p1/phase-d/w6/links-replaced-w6.csv','w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
print(len(rows))
