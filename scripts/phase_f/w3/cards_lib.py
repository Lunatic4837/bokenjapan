import re, html, glob
REPO='/workspace/p1/pr12-work'
SEC=lambda t: re.compile(r'(<section class="place-section"><h2>'+t+r'</h2>)(.*?)(</section>)', re.S)
def parse_li(li):
    g=lambda r: (lambda m: html.unescape(m.group(1)) if m else None)(re.search(r,li,re.S))
    src=g(r'<!-- sources: (.*?) -->') or ''
    tb=re.search(r'tabelog_url=(\S+)',src); ta=re.search(r'ta_url=(\S+)',src)
    return dict(name=g(r'<p class="place-name">(.*?)</p>'), en=g(r'<p class="place-blurb">(.*?)</p>'),
        meta=g(r'<p class="place-meta">(.*?)</p>'), desc=g(r'<p class="place-desc">(.*?)</p>'),
        href=g(r'<a href="([^"]+)"'), tb=tb.group(1) if tb else None, ta=ta.group(1) if ta else None, li=li)
def section_cards(s, t):
    m=SEC(t).search(s)
    if not m: return None, []
    return m, [parse_li(li) for li in re.findall(r'<li\b.*?</li>', m.group(2), re.S)]
def pages():
    for p in sorted(glob.glob(f'{REPO}/*/*/index.html')):
        yield p.split(REPO+'/')[1].rsplit('/',1)[0], p
nk=lambda n: re.sub(r'[\s\u3000]','',n or '')
