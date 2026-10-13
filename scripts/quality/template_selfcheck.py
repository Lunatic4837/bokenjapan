#!/usr/bin/env python3
"""Self-check: municipality hub + eat genre tiles + list pages use the same markup as Miyagi/Ohira. Usage: template_selfcheck.py ROOT pref..."""
import re,sys,glob,collections
root=sys.argv[1]
def sig(h):
    return (('<body class="hubbed">' in h), bool(re.search(r'<section class="hub"><h2 class="visually-hidden">Explore [^<]+</h2><ul class="hub-tiles"><li><a class="hub-tile" href="',h)),
            'place-section"><h2>Dining' not in h)
ref=open(f'{root}/miyagi/ohira/index.html').read(); refe=open(f'{root}/miyagi/ohira/eat/index.html').read()
R=sig(ref); EAT=re.compile(r'<ul class="hub-tiles hub-tiles-sm"><li><a class="hub-tile hub-tile-sm" href="[a-z-]+/">'); RE=bool(EAT.search(refe))
tile_re=re.compile(r'<li><a class="hub-tile( hub-tile-sm)?" href="[^"]+">(<img src="[^"]+" alt="[^"]*" width="\d+" height="\d+"\s+(loading="lazy" )?decoding="async">)?<span class="hub-tile-label"><span class="hub-tile-name">[^<]+</span><span class="hub-tile-count">[\d,]+ places?</span></span></a></li>')
ref_tiles=[t for t in re.findall(r'<li><a class="hub-tile.*?</a></li>',ref+refe)]
assert ref_tiles and all(tile_re.fullmatch(t) for t in ref_tiles), 'reference tiles do not match pattern'
fails=collections.Counter(); tot=collections.Counter()
for pref in sys.argv[2:]:
    for f in glob.glob(f'{root}/{pref}/*/index.html'):
        h=open(f).read(); tot[pref]+=1
        if sig(h)!=R: fails[pref+':hub']+=1; print('HUB',f)
        for t in re.findall(r'<li><a class="hub-tile.*?</a></li>',h):
            if not tile_re.fullmatch(t): fails[pref+':tile']+=1; print('TILE',f,t[:120])
        if 'href="eat/"' in h:
            e=f.replace('index.html','eat/index.html'); eh=open(e).read()
            if bool(EAT.search(eh))!=RE: fails[pref+':eat']+=1; print('EAT',e)
            for t in re.findall(r'<li><a class="hub-tile.*?</a></li>',eh):
                if not tile_re.fullmatch(t): fails[pref+':eattile']+=1
            for c in re.findall(r'class="hub-tile hub-tile-sm" href="([a-z-]+)/"',eh):
                lh=open(e.replace('index.html',f'{c}/index.html')).read()
                if not ('<body class="hubbed">' in lh and '<section class="place-section"><h2 class="visually-hidden">' in lh): fails[pref+':list']+=1
print('pages',dict(tot),'fails',dict(fails) or 0)
sys.exit(1 if fails else 0)
