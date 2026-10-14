import re,json,subprocess,time,html as H,os,sys
pref=sys.argv[1]; SH,N=int(sys.argv[2]),int(sys.argv[3])
UA='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36'
CJK=re.compile(r"[\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af]")
urls=[u.strip() for u in open(f'sights/{pref}/en-urls.txt') if u.strip()]
out=f'sights/{pref}/site-{SH}.json'; db=json.load(open(out)) if os.path.exists(out) else {}
for k,u in enumerate(urls):
    if k%N!=SH or u in db: continue
    r=subprocess.run(['curl','-sL','-A',UA,'--max-time','25','-w','\n%{http_code}',u],capture_output=True,text=True)
    b,_,c=r.stdout.rpartition('\n'); rec={'code':c}
    if c=='200':
        t=re.search(r'<title>(.*?)</title>',b,re.S); h1=re.search(r'<h1[^>]*>(.*?)</h1>',b,re.S); og=re.search(r'og:title" content="([^"]+)"',b)
        import sys as _s; _s.path.insert(0,'/workspace/p1/partials-build/shared'); import bj_shared as _S  # AUDIT-47 P8
        rec['name']=_S.clean_title(H.unescape(t.group(1)).strip() if t else '', h1=re.sub(r'<[^>]+>','',h1.group(1)).strip() if h1 and len(re.sub(r'<[^>]+>','',h1.group(1)).strip())<40 else None, og_title=H.unescape(og.group(1)) if og else None)
        d=re.search(r'<meta property="og:description" content="([^"]*)"',b); rec['desc']=H.unescape(d.group(1)) if d else ''
        txt=re.sub(r'<script.*?</script>|<style.*?</style>','',b,flags=re.S)
        L=[l.strip() for l in H.unescape(re.sub(r'<[^>]+>','\n',txt)).split('\n') if l.strip()]
        rec['addr']=[l for l in L if re.search(r'(Ibaraki|Tochigi)\b',l) and len(l)<120 and re.search(r'\d',l) and '©' not in l][:3]
        imgs=[i for i in re.findall(r'(https://[^"\' )]+/wp-content/uploads/[^"\' )]+\.(?:jpe?g|png|webp))',b) if 'logo' not in i.lower()]
        rec['imgs']=list(dict.fromkeys(imgs))[:3]
        if CJK.search(rec['name']+rec['desc']): rec['cjk']=True
    db[u]=rec; json.dump(db,open(out,'w'),ensure_ascii=False); time.sleep(1.0)
print('DONE',len(db))
