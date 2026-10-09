import json,re,requests,concurrent.futures as cf,urllib.parse as U,html
dom=json.load(open('ext_links.json'))
TRUST=re.compile(r'(tiktok\.com|\.lg\.jp|\.go\.jp|\.ed\.jp|\.ac\.jp)$')
KW=re.compile(r'casino|カジノ|オンラインカジノ|slot\s?gacor|スロット|gambl|baccarat|バカラ|sportsbook|ブックメーカー|betting|\bjudi\b|togel|gacor|slot online|poker|ポーカー|porn|アダルト|av女優|出会い系|セフレ|xxx|hentai|escort|domain (?:is )?for sale|buy this domain|this domain (?:may be|is) for sale|parkingcrew|sedoparking|bodis|domain parking|ドメインパーキング|このドメインは.{0,20}(?:販売|売却|取得)|お名前\.com.{0,30}(?:ドメイン)|sponsored listings|related searches|竞彩|体育|博彩|娱乐城|bet365|1xbet|クイーンカジノ|ベラジョン|vera.?john|ミスティーノ|パチスロ|オンカジ|入金不要',re.I)
def reg(h):
    p=(h or '').lower().split('.')
    if len(p)>=3 and p[-2] in ('co','or','ne','ac','go','lg','ed','gr','com','net','org'): return '.'.join(p[-3:])
    return '.'.join(p[-2:])
S=requests.Session(); S.headers.update({'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/129.0 Safari/537.36','Accept-Language':'ja,en;q=0.8'})
def chk(h):
    if TRUST.search(h): return dict(host=h,status='trusted')
    u=dom[h][0][1]; tries=[u]
    if u.startswith('http://'): tries=['https://'+u[7:],u]
    last=None
    for t in tries:
        try:
            r=S.get(t,timeout=(8,20),allow_redirects=True)
            txt=r.content[:400000].decode(r.encoding or 'utf-8',errors='ignore')
            title=html.unescape((re.search(r'<title[^>]*>(.*?)</title>',txt,re.S|re.I) or [0,''])[1]).strip()[:120]
            vis=re.sub(r'<script.*?</script>|<style.*?</style>','',txt,flags=re.S|re.I)
            hits=sorted(set(m.group(0).lower() for m in KW.finditer(vis)))[:10]
            # meta refresh / js redirect
            js=re.findall(r'(?:location\.(?:href|replace)\s*[=(]\s*["\']|http-equiv=["\']refresh["\'][^>]*url=)(https?://[^"\'> ]+)',txt,re.I)
            fh=U.urlsplit(r.url).hostname or ''
            return dict(host=h,url=t,final=r.url,code=r.status_code,title=title,hits=hits,offsite=reg(fh)!=reg(h),js=[j for j in js if reg(U.urlsplit(j).hostname)!=reg(h)][:3],n=len(dom[h]),size=len(r.content))
        except Exception as e: last=str(e)[:120]
    return dict(host=h,url=u,err=last,n=len(dom[h]))
with cf.ThreadPoolExecutor(24) as ex: res=list(ex.map(chk,sorted(dom)))
json.dump(res,open('scan.json','w'),ensure_ascii=False,indent=0)
print('done',len(res),sum(1 for r in res if r.get('hits')),sum(1 for r in res if r.get('offsite')),sum(1 for r in res if r.get('err')))
