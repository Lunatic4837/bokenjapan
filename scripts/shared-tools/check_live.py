#!/usr/bin/env python3
"""bokenjapan.com read-only live-page quality checker (v2, owner rule decisions 2026-10-08).

Fetches live pages (homepage, prefecture indexes, municipality pages), runs every
machine-checkable rule from SKILL-draft.md plus extra X-checks, and writes
report.md + report.json. Exit code: 0 = no FAIL, 1 = at least one FAIL, 2 = usage error.

READ-ONLY: GET/HEAD requests only. Nothing remote is ever written.

Examples:
  python3 check_live.py --pref miyagi                       # all munis linked from /miyagi/ + homepage
  python3 check_live.py --pref akita:3 --sample 5           # 3 random Akita + 5 random elsewhere
  python3 check_live.py --urls /miyagi/ohira/ --no-home
  python3 check_live.py --inventory live_pages.txt --pref miyagi --pref oita --check-pref-index
      (--inventory = gh-pages file list, one '<pref>/<slug>/index.html' per line; with it, --pref
       takes every inventory page of that prefecture and X10 compares index links vs inventory)
"""
import hashlib, argparse, io, json, os, random, re, sys, time
from collections import Counter, OrderedDict, defaultdict
from datetime import datetime
from urllib.parse import urljoin, urlparse

try:
    import requests
    from bs4 import BeautifulSoup, Comment
except ImportError:
    sys.stderr.write("needs requests + beautifulsoup4 (pip install requests beautifulsoup4 lxml)\n")
    sys.exit(2)
try:
    from PIL import Image, ImageStat
except Exception:  # pragma: no cover
    Image = None
try:
    import lxml  # noqa: F401
    PARSER = "lxml"
except Exception:
    PARSER = "html.parser"

LIVE = "https://bokenjapan.com"
BASE = os.environ.get("BJ_BASE", LIVE).rstrip("/")  # V2: preview base supported
UA = "bokenjapan-quality-check/2.0 (read-only; owner QA)"
RULES = OrderedDict([
    ("R1", "Dining: sourced (Tabelog ∪ TripAdvisor), Tabelog-first order, never empty"),
    ("R2", "Stay: sourced (Ikkyu ∪ Jalan), Ikkyu-first order; no thin sights-only page"),
    ("R3", "Every Dining/Stay facility has a real photo; credit in metadata; any photo source is kept"),
    ("R4", "Card format: EN headline / JA subtitle (lang=ja) / '#N ranked in {Municipality}' / English explanation; no labels/scores (legacy JA / EN order accepted, WARN)"),
    ("R5", "No visible source/data/licence credits or source-link chrome; every card clickable; English-first"),
    ("R6", "Tiny legal disclaimer at homepage bottom only"),
    ("R7", "Matches Ōhira reference template elements"),
    ("R8", "Images load (200, image/*, non-trivial size); links not broken"),
    ("X1", "No internal/draft notes leaked in public HTML comments"),
    ("X2", "Facility locality: listing URLs point at this municipality/prefecture"),
    ("X3", "No duplicate facilities (same name twice in a section / across Stay & Dining)"),
    ("X5", "No mojibake / Japanese leaking into English-only fields"),
    ("X6", "Cover photo: present, credited, adequate size, not reused across towns"),
    ("X7", "Locator map loads and highlights this town"),
    ("X8", "<head>: title, viewport, meta description, OG tags"),
    ("X9", "Breadcrumb/back links point to the right prefecture"),
    ("X10", "Prefecture index ↔ published pages consistent (no 404 links, no orphan towns)"),
    ("X11", "HTML structure sane (balanced containers, no nested links, unique ids)"),
    ("X12", "Page weight / card-count outliers"),
    ("X13", "Privacy/Terms reachable and linked from homepage"),
    ("X14", "Image markup: alt text, width/height, no mixed content"),
    ("X15", "Card photo belongs to the card's own venue ID (img/credit ID == link ID)"),  # V2
    ("X16", "EN names: no letter-by-letter romanised katakana loanwords (Gorufu->Golf)"),  # V2
    ("X17", "No duplicate card names within one page/list"),  # V2
    ("X18", "Town hub has See, Do and Day-to-day tiles"),  # V2
    ("X20", "Generator template blocks: Home crumb, '{Town}, {Pref}' title+H1, More in / Nearby in (+ Other towns on hub)"),  # V2.1
    ("X19", "House style: no macrons in EN text (Oita, not Ōita)"),  # V2
    ("X21", "Hub tiles: no tile image equal to the hero/cover image (same file, URL or bytes)"),  # V2.2
    ("X22", "Photo coverage per town: every Dining/Stay card has a photo unless a photo_search record (sources tried) is logged; % reported, FAIL below BJ_MIN_PHOTO_PCT"),  # AUDIT-47
    ("X23", "English-description coverage per town: every Dining/Stay card has an English place-desc; % reported, FAIL below BJ_MIN_DESC_PCT"),  # AUDIT-47
])
SEV = {"INFO": 0, "PASS": 0, "WARN": 1, "FAIL": 2, "SKIP": -1}
RANKED = ("Dining", "Stay")

CJK = re.compile(r"[\u3040-\u30fa\u30fc-\u30ff\u3400-\u9fff\uf900-\ufaff\uff66-\uff9f]")
FULLWIDTH_RE = re.compile(r"[\u30fb\uff01-\uff5e\u3000-\u303f]")
MOJIBAKE_RE = re.compile(r"\ufffd|Ã[\u0080-\u00bf]|â€|ã[\u0080-\u00bf]|ï¼|&amp;amp;|&#\d+;")
LISTING_WORDS = re.compile(r"\b(tabelog|tripadvisor|jalan|ikkyu)(\.com|\.net|\.jp)?\b|食べログ|トリップアドバイザー|一休\.com|じゃらん|楽天トラベル|rakuten travel|google maps", re.I)
LISTING_WORDS_STRICT = re.compile(r"tabelog|食べログ|tripadvisor|トリップアドバイザー|ikkyu|一休|jalan|じゃらん", re.I)
BLURB_LABEL_RE = re.compile(r"\b(tabelog|tripadvisor)\b|食べログ|じゃらん|jalan\.net|ikkyu\.com|一休\.com|\b[1-5]\.\d{2}\b|\breviews?\b|口コミ", re.I)
SCORE_RE = re.compile(r"[★☆]|\b[1-5]\.\d{1,2}\b|\breviews?\b|口コミ|点数|評価", re.I)
VISIBLE_CREDIT_RE = re.compile(
    r"(\bMLIT\b|国土交通省|国土数値情報|\bdataset\b|natural earth|openstreetmap|\bCC[ -]BY\b|creative commons|public domain|"
    r"\blicen[cs]e[ds]?\b|©|\bcopyright\b|\battribution\b|出典|写真提供|"
    r"\bphoto(?:\s*credit)?\s*[:：]|\bcredit\s*[:：]|\bsources?\s*[:：]|official\s*/\s*source\s*link|\bsource link\b|"
    r"\bboundaries from\b|\bdata from\b|\bmap data\b|"
    r"\bphoto\s+courtesy\b|\bCC0\b|\bCC[ -]BY(?:[ -](?:SA|NC|ND))*\b)", re.I)
# Photo-credits policy (2026-10-17): cards and sub-pages never carry credit rows or credit text; credits live on
# /photo-credits/ and /<pref>/photo-credits/ (author, licence, source), reachable from a footer "Photo credits" link.
CREDITS_PAGE_RE = re.compile(r"^/(?:[a-z0-9-]+/)?photo-credits/?(?:index\.html)?$")
FOOT_DATA_RE = re.compile(r"^Data:\s*©\s*OpenStreetMap contributors(?:\s*\(ODbL\))?$", re.I)  # allowed ODbL footer line (2026-10-17 decision)
CREDITS_LINK_RE = re.compile(r"^(?:https?://[^/]*bokenjapan\.com)?/(?:[a-z0-9-]+/)?photo-credits/?$")
CREDIT_CLASS_RE = re.compile(r"(?:^|[-_ ])(?:credit|credits|attribution|photo-credit|photocredit|source-credit)(?:$|[-_ ])", re.I)
SOURCE_LINK_TEXT_RE = re.compile(r"source|出典|\blink\b|tabelog|tripadvisor|jalan|ikkyu|じゃらん|食べログ|一休|terms of use|licen[cs]e", re.I)
LISTING_HOSTS = ("tabelog.com", "tripadvisor.", "jalan.net", "ikkyu.com", "ikyu.com", "travel.rakuten")
PLACEHOLDER_HOSTS = ("source.com", "www.source.com", "source.net", "www.source.net", "example.com", "example.org", "placeholder.com")
PLACEHOLDER_IMG_RE = re.compile(r"placeholder|dummy|no[-_]?image|noimg|sample|stock|generated|\bai[-_]|dall-?e|midjourney|stable-?diffusion", re.I)
INTERNAL_NOTE_RE = re.compile(r"unpublished draft|do not commit|\bTODO\b|\bFIXME\b|gated before public|local unpublished|not ready|WIP\b", re.I)
# Accepted state: a Dining/Stay card with no photo after the full search (official site, Tabelog listing
# incl. its /dtlphotolst/ photo tab, TripAdvisor, Jalan/Ikkyu) is fine IF it is logged in no-photo-found.csv.
NOPHOTO_LOG = os.environ.get("BJ_NOPHOTO_LOG", "/workspace/p1/photos-5pref/no-photo-found.csv")
_NOPHOTO = None
def nophoto_log():
    """{'pref/slug': {'urls': set, 'names': set}} from no-photo-found.csv (empty if the file is missing)."""
    global _NOPHOTO
    if _NOPHOTO is None:
        _NOPHOTO = {}
        try:
            import csv as _csv
            with open(NOPHOTO_LOG, encoding="utf-8") as fh:
                for r in _csv.DictReader(fh):
                    page = (r.get("card_key") or "").split("|")[0]
                    d = _NOPHOTO.setdefault(page, {"urls": set(), "names": set()})
                    if r.get("listing_url"): d["urls"].add(r["listing_url"].strip())
                    for k in ("name_ja", "card_name_on_page"):
                        if r.get(k): d["names"].add(re.sub(r"[\s\u3000]", "", r[k]))
        except OSError:
            pass
    return _NOPHOTO
def nophoto_logged(page, card):
    d = nophoto_log().get(page)
    if not d:
        return False
    if any(u and u.strip() in d["urls"] for u in card["sources"].values()):
        return True
    return re.sub(r"[\s\u3000]", "", card["name"] or "") in d["names"]

LODGING_HINT_RE = re.compile(r"ryokan|onsen|hot[- ]spring|hotel|\binn\b|minshuku|pension|guest ?house|旅館|温泉|ホテル|民宿|宿|ペンション|ゲストハウス", re.I)
SLUG_JUNK_RE = re.compile(r"\bPrefecture (Kyushu|Tohoku|Kanto|Chubu|Kinki|Kansai|Chugoku|Shikoku|Hokuriku|Koshinetsu|Tokai|Okinawa|Hokkaido)\b|_Prefecture_|Reviews-")
RANK_RE = re.compile(r"^#(\d+) ranked in (.+)$")
# PROPOSED PATCH: OSM/official dining cards carry a neutral (unranked) label instead of a fake rank
NEUTRAL_RE = re.compile(r"^Dining in (.+)$")
TABELOG_RE = re.compile(r"^https?://tabelog\.com/([a-z]+)/A\d{4}/A\d{6}/\d+/?$")
TA_RE = re.compile(r"^https?://(www\.)?tripadvisor\.[a-z.]+/(Restaurant_Review|Hotel_Review)-g\d+-d\d+-")
JALAN_RE = re.compile(r"^https?://(www\.)?jalan\.net/yad\d+/?")
IKKYU_RE = re.compile(r"^https?://(www\.)?ik?kyu\.com/\d+/?")
DESC_SEL = ".place-desc, .place-explain, .place-note"
LINE_CLASSES = ("place-name", "place-blurb", "place-meta", "place-desc")
# English-first cards (scripts/english_first_headings.py): p.place-name = English headline (inside the link), p.place-name-ja[lang=ja] = Japanese
# subtitle (takes the place of the old p.place-blurb), optional p.place-pron = small "Romaji: ..." line. They are mapped onto the legacy
# line model in parse_cards (name = Japanese identity, blurb = English headline) so every rule keyed on name/blurb keeps working.
EN_FIRST_EXTRA = ("place-name-ja", "place-pron")


class Budget:
    def __init__(self, pages, images, links):
        self.left = {"page": pages, "image": images, "link": links}
        self.used = Counter()

    def take(self, kind):
        if self.left[kind] is None:  # V2: unlimited
            self.used[kind] += 1
            return True
        if self.left[kind] <= 0:
            return False
        self.left[kind] -= 1
        self.used[kind] += 1
        return True


class _CachedResp:
    status_code = 200

    def __init__(self, text, url):
        self.text, self.url, self.content = text, url, text.encode("utf-8")
        self.headers = {}


class Fetcher:
    def __init__(self, budget, delay):
        self.s = requests.Session()
        self.s.headers["User-Agent"] = UA
        self.budget, self.delay = budget, delay
        self.head_cache, self.page_cache = {}, {}
        self.cache_dir = None

    def _cpath(self, url):
        p = urlparse(url).path.strip("/").replace("/", "__") or "home"
        return os.path.join(self.cache_dir, p + ("" if p.endswith((".svg", ".css", ".html")) else ".html"))

    def get_page(self, url):
        if url in self.page_cache:
            return self.page_cache[url]
        cpath = self._cpath(url) if self.cache_dir else None
        if cpath and os.path.exists(cpath):
            self.page_cache[url] = (_CachedResp(open(cpath, encoding="utf-8").read(), url), None)
            self.budget.used["page_cached"] += 1
            return self.page_cache[url]
        if not self.budget.take("page"):
            return None, "page budget exhausted"
        time.sleep(self.delay)
        try:
            r = self.s.get(url, timeout=30)
            r.encoding = "utf-8"
            res = (r, None)
            if cpath and r.status_code == 200:
                with open(cpath, "w", encoding="utf-8") as fh:
                    fh.write(r.text)
        except Exception as e:
            res = (None, f"{type(e).__name__}: {e}")
        self.page_cache[url] = res
        return res

    def head(self, url, kind, get_body=False):
        key = (url, get_body)
        if key in self.head_cache:
            return self.head_cache[key]
        if not self.budget.take(kind):
            return {"status": None, "err": f"{kind} budget exhausted", "skipped": True}
        time.sleep(self.delay / 3 if kind == "image" else self.delay)
        out = {"status": None, "ctype": "", "size": None, "final": url, "err": None, "etag": None}
        try:
            if get_body:
                r = self.s.get(url, timeout=25)
                out["body"] = r.content
            else:
                r = self.s.head(url, timeout=12, allow_redirects=True)
                if r.status_code in (403, 405, 501) or (r.status_code >= 400 and not url.startswith(BASE)):
                    r = self.s.get(url, timeout=15, stream=True, allow_redirects=True)
                    r.close()
            out.update(status=r.status_code, ctype=r.headers.get("content-type", ""), final=r.url,
                       etag=r.headers.get("etag"))
            cl = r.headers.get("content-length")
            out["size"] = int(cl) if cl and cl.isdigit() else (len(out["body"]) if get_body else None)
        except Exception as e:
            out["err"] = f"{type(e).__name__}: {str(e)[:120]}"
        self.head_cache[key] = out
        return out


class Result:
    def __init__(self):
        self.rules = OrderedDict((k, {"status": "PASS", "findings": []}) for k in RULES)

    def add(self, rule, sev, msg, code=None, n=None):
        r = self.rules[rule]
        if r["status"] == "SKIP":
            return
        f = {"sev": sev, "msg": msg}
        if code:
            f["code"] = code
        if n is not None:
            f["n"] = n
        r["findings"].append(f)
        if SEV[sev] > SEV.get(r["status"], 0):
            r["status"] = sev

    def skip(self, rule, msg):
        self.rules[rule] = {"status": "SKIP", "findings": [{"sev": "SKIP", "msg": msg}]}


def comments_of(tag):
    return [c.strip() for c in tag.find_all(string=lambda t: isinstance(t, Comment))]


def parse_kv_comment(comments, prefix):
    out = {}
    for c in comments:
        if c.startswith(prefix):
            for part in c[len(prefix):].split("|"):
                if "=" in part:
                    k, v = part.split("=", 1)
                    out[k.strip()] = v.strip()
    return out


def credit_of(comments):
    for c in comments:
        if c.startswith("photo-credit:"):
            m = re.search(r"Source\s+(\S+)", c)
            return {"raw": c, "url": m.group(1) if m else None}
    return None


def hidden_by_css_classes(css_text):
    hidden = {"visually-hidden", "sr-only"}
    for m in re.finditer(r"\.([a-zA-Z0-9_-]+)\s*\{[^}]*display\s*:\s*none", css_text or ""):
        hidden.add(m.group(1))
    return hidden


def visible_text_root(soup, hidden_classes):
    s = BeautifulSoup(str(soup), PARSER)
    for c in s.find_all(string=lambda t: isinstance(t, Comment)):
        c.extract()
    for t in s(["script", "style", "template", "head"]):
        t.decompose()
    doomed = []
    for t in s.find_all(True):
        cls = set(t.get("class") or [])
        style = (t.get("style") or "").replace(" ", "").lower()
        if cls & hidden_classes or t.has_attr("hidden") or "display:none" in style or "visibility:hidden" in style:
            doomed.append(t)
    for t in doomed:
        if t.parent is not None:
            t.extract()
    return s


def is_latin_first(text):
    text = (text or "").strip()
    return bool(text) and not CJK.match(text[0])


def short(u, n=90):
    u = str(u)
    return u if len(u) <= n else u[: n - 1] + "…"


def host_of(u):
    return urlparse(u or "").netloc.lower()


def is_external(u):
    h = host_of(u)
    return bool(h) and "bokenjapan.com" not in h and h != host_of(BASE) and h.split(":")[0] not in ("127.0.0.1", "localhost")  # V2


def strip_suffix(name):
    n = re.sub(r"[^a-z]", "", (name or "").lower())
    for suf in ("shi", "machi", "cho", "mura", "son", "city", "town", "village"):
        if n.endswith(suf) and len(n) - len(suf) >= 3:
            return n[: -len(suf)]
    return n


def r5_credits(res, body, url):
    """R5 photo-credits policy: credit text/rows/source links FAIL on cards and sub-pages; /photo-credits pages must give
    author, licence and source; the footer 'Photo credits' link is allowed."""
    is_credits = bool(CREDITS_PAGE_RE.match(urlparse(url).path or "/"))
    if is_credits:
        txt_all = body.get_text(" ", strip=True)
        missing = [lab for lab, rx in (("author", r"(\bauthor|\bphotographer|\bphoto by|\btaken by|©)"),
                                       ("licence", r"\b(licen[cs]e|CC0|CC[ -]BY|public domain|all rights reserved)"),
                                       ("source", r"\b(source|wikimedia|flickr|commons|unsplash|pixabay|original)"))
                   if not re.search(rx, txt_all, re.I)]
        if missing:
            res.add("R5", "FAIL", "photo-credits page lacks " + ", ".join(missing), "R5.credits-incomplete")
    else:
        rows = [e for e in body.find_all(True) if e.name != "a" and e.get_text(strip=True)
                and any(CREDIT_CLASS_RE.search(c) for c in (e.get("class") or []))
                and e.find_parent("footer") is None]
        if rows:
            res.add("R5", "FAIL", f"credit row on a card or sub-page ({len(rows)}): '{short(rows[0].get_text(' ', strip=True), 60)}'",
                    "R5.credit-row", len(rows))
    # R5 visible credits (text outside external anchors; anchors judged below)
    hits = []
    for t in ([] if is_credits else body.find_all(string=True)):
        txt = str(t).strip()
        if not txt:
            continue
        par = t.parent
        if par is not None and par.name == "a" and CREDITS_LINK_RE.match(par.get("href", "")) and par.find_parent("footer") is not None:
            continue  # the allowed footer "Photo credits" link
        fd = par.find_parent("p", class_="foot-data") if par is not None else None
        if fd is None and par is not None and par.name == "p" and "foot-data" in (par.get("class") or []):
            fd = par
        if fd is not None and fd.find_parent("footer") is not None and FOOT_DATA_RE.match(fd.get_text(" ", strip=True).replace("  ", " ")) \
                and all("openstreetmap.org" in (a.get("href") or "") for a in fd.find_all("a")):
            continue  # the allowed ODbL footer line "Data: © OpenStreetMap contributors"
        if par is not None and (par.find_parent(class_="foot-disclaimer") or "foot-disclaimer" in (par.get("class") or [])):
            continue
        a_par = par if (par is not None and par.name == "a") else (par.find_parent("a") if par is not None else None)
        if a_par is not None and is_external(urljoin(url, a_par.get("href", ""))):
            continue
        if VISIBLE_CREDIT_RE.search(txt):
            hits.append(txt)
    if hits:
        c = Counter(hits)
        res.add("R5", "FAIL", f"visible source/data/licence credit text ({len(hits)}): " +
                "; ".join(f"'{short(h, 60)}'×{n}" for h, n in c.most_common(3)), "R5.credit-text", len(hits))
    # R5 outbound source-link chrome: external anchors that do NOT wrap a facility name/photo
    bad_links = []
    for a in ([] if is_credits else body.find_all("a", href=True)):
        href = urljoin(url, a["href"])
        if not is_external(href) or re.search(r"(x\.com|instagram\.com|tiktok\.com)/", href):
            continue
        wraps_card = a.find(class_="place-name") or a.find("img") or (a.find_parent(class_="place-name") is not None)
        if wraps_card:
            continue
        txt = a.get_text(" ", strip=True)
        in_meta_block = a.find_parent(class_="meta-block") is not None
        if any(h in host_of(href) for h in LISTING_HOSTS) or SOURCE_LINK_TEXT_RE.search(txt) or (
                a.find_parent("main") is not None and not in_meta_block and a.find_parent("li") is not None):
            bad_links.append(f"'{short(txt, 30)}'→{host_of(href)}")
    if bad_links:
        c = Counter(bad_links)
        res.add("R5", "FAIL", f"visible outbound source-link chrome ({len(bad_links)} links): " +
                "; ".join(f"{k}×{n}" for k, n in c.most_common(3)), "R5.link-chrome", len(bad_links))


# ---------------------------------------------------------------- common checks
def check_common(res, soup, raw, url, page_type, ctx):
    hidden = ctx["hidden_classes"]
    vis = visible_text_root(soup, hidden)
    body = vis.body or vis

    # R6
    disc = soup.select(".foot-disclaimer")
    if page_type == "home":
        foot = soup.find("footer")
        if not disc:
            res.add("R6", "FAIL", "homepage has no .foot-disclaimer legal line", "R6.missing")
        else:
            d = disc[-1]
            if not foot or d not in foot.find_all(True):
                res.add("R6", "FAIL", "disclaimer is not inside the page footer", "R6.place")
            later = [t for t in d.find_all_next(["p", "div", "section", "nav"]) if t.get_text(strip=True)]
            if later:
                res.add("R6", "WARN", f"disclaimer is not the last visible block (followed by {later[0].name})", "R6.place")
            px = ctx.get("disclaimer_px")
            if px is None:
                res.add("R6", "WARN", "could not read disclaimer font-size from styles.css", "R6.size")
            elif px > 10:
                res.add("R6", "FAIL", f"disclaimer font-size {px}px is not 'tiny' (>10px)", "R6.size")
            res.add("R6", "PASS", f"disclaimer present ({px}px): '{short(d.get_text(' ', strip=True), 80)}'")
    elif disc:
        res.add("R6", "FAIL", "legal disclaimer (.foot-disclaimer) appears on a non-homepage page", "R6.elsewhere")
    foot = soup.find("footer")
    if foot:
        extra = [p.get_text(" ", strip=True) for p in foot.find_all("p", recursive=False)
                 if not set(p.get("class") or []) & {"foot-name", "foot-disclaimer", "foot-data"}]
        if extra:
            res.add("R6", "WARN", f"footer carries a visible sourcing statement (owner to decide if it counts as a credit): '{short(extra[0], 70)}'", "R6.footer-statement")

    r5_credits(res, body, url)
    brand_hits = []
    for t in body.find_all(string=True):
        par = t.parent
        if par is not None and set(par.get("class") or []) & {"place-name", "place-blurb", "place-desc", "place-name-ja", "place-pron"}:
            continue
        if par is not None and (par.find_parent(class_="foot-disclaimer") or "foot-disclaimer" in (par.get("class") or [])):
            continue
        if LISTING_WORDS.search(str(t)):
            brand_hits.append(str(t).strip())
    if brand_hits:
        res.add("R5", "FAIL", f"visible listing-site brand text ({len(brand_hits)}): '{short(brand_hits[0], 60)}'", "R5.brand", len(brand_hits))
    title = soup.title.get_text(strip=True) if soup.title else ""
    if title and not is_latin_first(title):
        res.add("R5", "FAIL", f"<title> not English-first: '{title}'", "R5.en-first")
    h1 = soup.select_one("h1")
    if h1 and not is_latin_first(h1.get_text(strip=True)):
        res.add("R5", "FAIL", f"h1 not English-first: '{h1.get_text(strip=True)}'", "R5.en-first")
    if (soup.html.get("lang") if soup.html else None) != "en":
        res.add("R5", "WARN", f"<html lang> is '{soup.html.get('lang') if soup.html else None}', expected 'en'", "R5.lang")

    # X1 leaked internal notes
    leaks = [c for c in comments_of(soup) if INTERNAL_NOTE_RE.search(c)]
    if leaks:
        m = INTERNAL_NOTE_RE.search(leaks[0])
        res.add("X1", "WARN", f"HTML comment contains internal/draft note: '…{short(leaks[0][max(0, m.start()-30): m.end()+40], 110)}…'", "X1.note")

    # X5 mojibake anywhere visible
    moj = [str(t).strip() for t in body.find_all(string=True) if MOJIBAKE_RE.search(str(t))]
    if moj:
        res.add("X5", "FAIL", f"mojibake/double-escaped text ({len(moj)}): '{short(moj[0], 60)}'", "X5.mojibake", len(moj))

    # X8 head
    if not title:
        res.add("X8", "FAIL", "missing <title>", "X8.title")
    if not soup.find("meta", attrs={"name": "viewport"}):
        res.add("X8", "FAIL", "missing mobile viewport meta", "X8.viewport")
    if not soup.find("meta", attrs={"name": "description"}):
        res.add("X8", "WARN", "missing meta description", "X8.description")
    og = {m.get("property") for m in soup.find_all("meta", attrs={"property": True})}
    miss = [p for p in ("og:title", "og:description", "og:image") if p not in og]
    if miss:
        res.add("X8", "WARN", "missing OG tags: " + ", ".join(miss), "X8.og")
    if not soup.find("link", rel=lambda v: v and "canonical" in v):
        res.add("X8", "WARN", "no canonical link", "X8.canonical")

    # X11 structure (raw HTML)
    raw_nc = re.sub(r"<!--.*?-->", "", raw, flags=re.S)
    raw_nc = re.sub(r"<script\b.*?</script>|<style\b.*?</style>|<svg\b.*?</svg>", "", raw_nc, flags=re.S | re.I)
    unbalanced = []
    for tag in ("main", "section", "ul", "li", "figure", "footer", "header", "nav", "a", "p", "div", "dl"):
        o = len(re.findall(rf"<{tag}\b", raw_nc, re.I))
        c = len(re.findall(rf"</{tag}\s*>", raw_nc, re.I))
        if o != c:
            unbalanced.append(f"<{tag}> {o} open / {c} close")
    if unbalanced:
        res.add("X11", "FAIL", "unbalanced tags: " + "; ".join(unbalanced[:4]), "X11.unbalanced")
    nested = [a for a in soup.find_all("a") if a.find_parent("a") is not None]
    if nested:
        res.add("X11", "FAIL", f"{len(nested)} nested <a> elements", "X11.nested-a")
    ids = Counter(t.get("id") for t in soup.find_all(id=True))
    dup = [i for i, n in ids.items() if n > 1]
    if dup:
        res.add("X11", "WARN", "duplicate ids: " + ", ".join(dup[:4]), "X11.dup-id")
    if len(soup.find_all("main")) > 1 or len(soup.find_all("h1")) > 1:
        res.add("X11", "WARN", f"{len(soup.find_all('main'))} <main>, {len(soup.find_all('h1'))} <h1>", "X11.landmarks")

    # X12 weight
    nbytes = len(raw.encode("utf-8"))
    if nbytes > 2 * 1024 * 1024:
        res.add("X12", "FAIL", f"HTML is {nbytes/1048576:.1f} MiB (>2 MiB; very heavy on mobile)", "X12.weight", nbytes)
    elif nbytes > 750 * 1024:
        res.add("X12", "WARN", f"HTML is {nbytes/1024:.0f} KiB (>750 KiB)", "X12.weight", nbytes)
    ncards = len(soup.select("ul.place-list > li"))
    if ncards > 500:
        res.add("X12", "WARN", f"{ncards} cards on one page (consider top-N + pagination)", "X12.cards", ncards)

    # X14 image markup
    imgs = soup.find_all("img")
    no_alt = [i for i in imgs if not (i.get("alt") or "").strip()]
    http_imgs = [i for i in imgs if (i.get("src") or "").startswith("http://")]
    no_dims = [i for i in imgs if "thumb" not in (i.get("class") or []) and not (i.get("width") and i.get("height"))]
    if http_imgs:
        res.add("X14", "FAIL", f"{len(http_imgs)} images over plain http (mixed content)", "X14.http")
    if no_alt:
        res.add("X14", "WARN", f"{len(no_alt)} <img> without alt text", "X14.alt", len(no_alt))
    if no_dims:
        res.add("X14", "WARN", f"{len(no_dims)} non-thumb images without width/height", "X14.dims", len(no_dims))

    check_links(res, soup, url, ctx)
    return nbytes


def check_links(res, soup, url, ctx):
    f, cap_ext = ctx["fetcher"], ctx["ext_links_per_page"]
    internal, external = [], []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        absu = urljoin(url, href).split("#")[0]
        if BASE != LIVE and re.match(r"https?://(www\.)?bokenjapan\.com(/|$)", absu):  # (a) preview run: absolute live links are internal
            absu = BASE + re.sub(r"^https?://(www\.)?bokenjapan\.com", "", absu)
        (external if is_external(absu) else internal).append(absu)
    internal = list(OrderedDict.fromkeys(internal))
    external = [u for u in OrderedDict.fromkeys(external) if not re.search(r"(x\.com|instagram\.com|tiktok\.com)/", u)]
    broken, warned, skipped = [], [], 0
    for u in internal:
        if u in ctx["known_ok"]:
            continue
        r = f.head(u, "link")
        if r.get("skipped"):
            skipped += 1
            continue
        if r["status"] == 200:
            ctx["known_ok"].add(u)
        else:
            seg = urlparse(u).path.strip("/").split("/")[0]
            if urlparse(url).path in ("", "/") and len(ctx.get("prefs", [])) == 1 and seg and seg not in ctx["prefs"] and r["status"] == 404:
                warned.append(f"{short(u.replace(BASE, ''), 60)} (prefecture not in this checkout)")  # (d) single-prefecture run
            else:
                broken.append(f"{short(u.replace(BASE, ''), 60)} ({r['status'] or r['err']})")
    sample = external if len(external) <= cap_ext else ctx["rnd"].sample(external, cap_ext)
    for u in sample:
        r = f.head(u, "link")
        if r.get("skipped"):
            skipped += 1
            continue
        st = r["status"]
        if st is None:
            if r["err"] and re.search(r"NameResolution|getaddrinfo|Name or service", r["err"]):
                broken.append(f"{short(u)} (DNS fail)")
            else:
                warned.append(f"{short(u)} ({r['err'][:40] if r['err'] else 'error'})")
        elif st in (404, 410):
            broken.append(f"{short(u)} ({st})")
        elif st >= 400:
            warned.append(f"{short(u)} ({st}, may be bot-blocking)")
    if broken:
        res.add("R8", "FAIL", f"broken links ({len(broken)}): " + "; ".join(broken[:4]), "R8.link", len(broken))
    if warned:
        res.add("R8", "WARN", f"links not verifiable ({len(warned)}): " + "; ".join(warned[:3]), "R8.link-unverified")
    if skipped:
        res.add("R8", "WARN", f"{skipped} link checks skipped (budget)", "R8.skipped")


def check_images(res, imgs, url, ctx, label, info):
    f = ctx["fetcher"]
    fails, warns, checked = [], [], 0
    deep_left = ctx["deep_images_per_page"]
    for src, ctxname in imgs[: ctx["images_per_page"]]:
        absu = urljoin(url, src)
        is_svg = absu.lower().split("?")[0].endswith(".svg")
        deep = Image is not None and deep_left > 0 and not is_svg and ctxname in RANKED
        r = f.head(absu, "image", get_body=deep)
        if r.get("skipped"):
            continue
        checked += 1
        st, ct, size = r["status"], (r.get("ctype") or "").lower(), r.get("size")
        name = src.split("/")[-1]
        if ctxname == "cover":
            info["cover_head"] = {"size": size, "etag": r.get("etag"), "status": st}
        if st != 200:
            fails.append(f"{name} → {st or r['err']}")
            continue
        if not ct.startswith("image/"):
            fails.append(f"{name} content-type '{ct}'")
            continue
        if is_svg or "svg" in ct:
            if size is not None and size < 100:
                fails.append(f"{name} svg only {size} bytes")
        elif size is not None and size < 1000:
            fails.append(f"{name} only {size} bytes (placeholder-size)")
        elif size is not None and size < 5000:
            warns.append(f"{name} small ({size} B)")
        if not is_svg and Image is not None and size is not None and size < 3000 and not r.get("body"):
            rb = f.head(absu, "image", get_body=True)
            if rb.get("body"):
                r, deep = rb, True
                deep_left += 1
        if deep and r.get("body"):
            deep_left -= 1
            try:
                im = Image.open(io.BytesIO(r["body"]))
                w, h = im.size
                try:
                    ex = im.getexif()
                    has_credit = any(ex.get(t) for t in (270, 315, 33432))
                except Exception:
                    has_credit = False
                info.setdefault("exif_sample", []).append(bool(has_credit))
                g = im.convert("L").resize((64, 64))
                sd = ImageStat.Stat(g).stddev[0]
                light = sum(1 for v in g.tobytes() if v > 225) / 4096.0
                if min(w, h) < 120:
                    fails.append(f"{name} tiny {w}x{h}")
                elif sd < 6:
                    fails.append(f"{name} near-uniform (placeholder-like) image")
                elif size is not None and size < 3000 and light > 0.80 and sd < 25 and not any(x.startswith(name + " only") for x in fails):
                    fails.append(f"{name} mostly blank/white — looks like a 'NO PHOTO' placeholder")
            except Exception as e:
                warns.append(f"{name} not decodable ({type(e).__name__})")
    if fails:
        res.add("R8", "FAIL", f"{label}: images not loading/valid ({len(fails)}/{checked}): " + "; ".join(fails[:4]), "R8.image", len(fails))
    if warns:
        res.add("R8", "WARN", f"{label}: " + "; ".join(warns[:3]) + (f" (+{len(warns)-3})" if len(warns) > 3 else ""), "R8.image-small", len(warns))
    if len(imgs) > ctx["images_per_page"]:
        res.add("R8", "WARN", f"{label}: sampled first {ctx['images_per_page']} of {len(imgs)} images", "R8.sampled")
    info["images_checked"] = info.get("images_checked", 0) + checked
    return checked


# ---------------------------------------------------------------- cards
def parse_cards(section):
    cards = []
    ul = section.find("ul", class_="place-list")
    if not ul:
        return cards
    for li in ul.find_all("li", recursive=False):
        lines = [t for t in li.find_all(["p", "div", "span"]) if set(t.get("class") or []) & set(LINE_CLASSES + EN_FIRST_EXTRA)]
        cm = comments_of(li)
        img = li.find("img")
        name_el = li.select_one(".place-name")
        desc_el = li.select_one(DESC_SEL)
        click = []
        for a in li.find_all("a", href=True):
            if a.find(class_="place-name") or a.find("img") or (name_el is not None and a in name_el.find_all("a")):
                click.append(a["href"])
        extra = li.get_text(" ", strip=True)
        for t in lines:
            extra = extra.replace(t.get_text(" ", strip=True), "", 1)
        ja_el = li.select_one(".place-name-ja")
        en_first = ja_el is not None
        head_txt = name_el.get_text(" ", strip=True) if name_el else ""
        cards.append({
            "en_first": en_first,
            "headline": head_txt,
            "name_ja_lang": (ja_el.get("lang") if en_first else None),
            "name": (ja_el.get_text(" ", strip=True) if en_first else head_txt),
            "blurb": (head_txt if en_first else (li.select_one(".place-blurb").get_text(" ", strip=True) if li.select_one(".place-blurb") else None)),
            "meta": (li.select_one(".place-meta").get_text(" ", strip=True) if li.select_one(".place-meta") else None),
            "desc": desc_el.get_text(" ", strip=True) if desc_el else None,
            "desc_source": any(c.startswith("desc-source") for c in cm),
            "line_seq": [("place-blurb" if "place-name-ja" in (t.get("class") or []) else next(c for c in LINE_CLASSES if c in (t.get("class") or [])))
                         for t in lines if "place-pron" not in (t.get("class") or [])],
            "img": img.get("src") if img else None,
            "credit": credit_of(cm),
            "sources": parse_kv_comment(cm, "sources:"),
            "click": click,
            "extra_text": extra.strip(" ·|"),
        })
    return cards


def sections_by_title(main):
    out = OrderedDict()
    for sec in main.find_all("section", class_="place-section"):
        h = sec.find(["h2", "h3"])
        out.setdefault(h.get_text(" ", strip=True) if h else "?", sec)
    return out


def check_clickable(res, cards, kind, url, ctx, stats):
    n = len(cards)
    if not n:
        return
    noclick = [i for i, c in enumerate(cards, 1) if not c["click"]]
    bad_dest = []
    for i, c in enumerate(cards, 1):
        for h in c["click"]:
            absu = urljoin(url, h)
            if not is_external(absu):
                bad_dest.append(f"#{i} → internal '{short(h, 30)}'")
            elif host_of(absu) in PLACEHOLDER_HOSTS:
                bad_dest.append(f"#{i} → placeholder host {host_of(absu)}")
    stats["noclick"] += len(noclick)
    stats["noclick_" + ("ranked" if kind in RANKED else "other")] += len(noclick)
    if noclick:
        res.add("R5", "FAIL", f"{kind}: {len(noclick)}/{n} cards not clickable (photo/name must link to the facility's real destination)",
                "R5.not-clickable", len(noclick))
    if bad_dest:
        res.add("R5", "FAIL", f"{kind}: card links not to a real destination ({len(bad_dest)}): " + ", ".join(bad_dest[:3]), "R5.bad-destination", len(bad_dest))
    dests = [urljoin(url, h) for c in cards for h in c["click"] if is_external(urljoin(url, h))]
    for u in ctx["rnd"].sample(dests, min(len(dests), ctx["card_links_per_section"])):
        r = ctx["fetcher"].head(u, "link")
        if r.get("status") in (404, 410):
            res.add("R8", "FAIL", f"{kind}: card link 404: {short(u)}", "R8.card-link")



def check_dining_town_locality(res, soup, url):
    """X2: Dining cards with locality-addr must include this page's muni-ja (out-of-town padding)."""
    muni_ja = None
    for c in soup.find_all(string=lambda t: isinstance(t, Comment)):
        s = str(c).strip()
        if s.startswith("muni-ja:"):
            muni_ja = s.split(":", 1)[1].strip()
            break
    if not muni_ja:
        return
    sec = None
    for s in soup.select("section.place-section"):
        h = s.find(["h2", "h3"])
        if h and h.get_text(strip=True) == "Dining":
            sec = s
            break
    if not sec:
        return
    bad = []
    for i, li in enumerate(sec.select("ul.place-list > li"), 1):
        addr = None
        for c in li.find_all(string=lambda t: isinstance(t, Comment)):
            s = str(c).strip()
            if s.startswith("locality-addr:"):
                addr = s.split(":", 1)[1].strip()
                break
        if addr is None:
            continue
        if muni_ja not in addr:
            nm = li.select_one(".place-name")
            bad.append(f"#{i} {(nm.get_text(strip=True) if nm else '?')} ({short(addr, 40)})")
    if bad:
        res.add("X2", "FAIL", f"Dining: {len(bad)} cards address outside this municipality ({muni_ja}): " + ", ".join(bad[:3]), "X2.town-locality", len(bad))

def check_facility_cards(res, cards, kind, muni, pref, url, ctx, stats):
    srule = "R1" if kind == "Dining" else "R2"
    primary, secondary = ("tabelog_url", "ta_url") if kind == "Dining" else ("ikkyu_url", "jalan_url")
    prim_re, sec_re = (TABELOG_RE, TA_RE) if kind == "Dining" else (IKKYU_RE, JALAN_RE)
    n = len(cards)
    st = stats[kind]
    st["cards"] += n
    unsourced, badfmt, wrongpref, order_bad, dupes = [], [], [], None, []
    seen = Counter()
    secondary_only_seen = False
    for i, c in enumerate(cards, 1):
        src = c["sources"]
        p, s = src.get(primary), src.get(secondary)
        # STAY-FALLBACK (2026-10-14): Stay may be sourced from Rakuten Travel or an official facility/municipal site
        if kind == "Stay" and not p and not s and (src.get("rakuten_url") or src.get("official_url")):
            continue
        # PROPOSED PATCH: Dining may be sourced from OSM or an official/municipal page
        if kind == "Dining" and not p and not s and (src.get("osm_url") or src.get("official_url")):
            continue
        if not p and not s:
            unsourced.append(f"#{i} {c['name']}")
            continue
        for u, rx in ((p, prim_re), (s, sec_re)):
            if u and not rx.search(u):
                badfmt.append(f"#{i} {short(u, 60)}")
        if p and kind == "Dining":
            m = TABELOG_RE.match(p)
            if m and pref and m.group(1) != pref:
                wrongpref.append(f"#{i} {c['name']} (tabelog/{m.group(1)})")
        key = p or s
        seen[key] += 1
        if seen[key] >= 2:
            dupes.append(f"#{i} {c['name']}")
        if not p:
            secondary_only_seen = True
        elif secondary_only_seen and order_bad is None:
            order_bad = f"#{i} {c['name']} has {primary} after a {secondary}-only entry"
    st["unsourced"] += len(unsourced)
    st["dupe_entries"] += len(dupes)
    st["wrong_pref"] += len(wrongpref)
    lab = "Tabelog/TripAdvisor" if kind == "Dining" else "Ikkyu/Jalan"
    if unsourced:
        res.add(srule, "FAIL", f"{kind}: {len(unsourced)}/{n} entries have no {lab} source in metadata: " + ", ".join(unsourced[:4]), f"{srule}.unsourced", len(unsourced))
    if badfmt:
        res.add(srule, "FAIL", f"{kind}: malformed source URLs ({len(badfmt)}): " + ", ".join(badfmt[:3]), f"{srule}.bad-url", len(badfmt))
    if wrongpref:
        res.add(srule, "FAIL", f"{kind}: Tabelog entries from another prefecture ({len(wrongpref)}): " + ", ".join(wrongpref[:3]), f"{srule}.wrong-pref", len(wrongpref))
    if order_bad:
        res.add(srule, "FAIL", f"{kind}: order not {primary.split('_')[0]}-first: {order_bad}", f"{srule}.order")
    if dupes:
        res.add(srule, "FAIL", f"{kind}: {len(dupes)} duplicate entries (same source URL repeated): " + ", ".join(dupes[:3]), f"{srule}.dupe", len(dupes))
    if not (unsourced or badfmt or wrongpref or order_bad or dupes):
        cp = sum(1 for c in cards if c["sources"].get(primary))
        res.add(srule, "PASS", f"{kind}: {n} entries, all sourced ({cp} {primary.split('_')[0]}, {n-cp} {secondary.split('_')[0]}-only), order OK")
    if kind == "Stay" and n and not any(c["sources"].get("ikkyu_url") for c in cards):
        res.add("R2", "WARN", "Stay: no Ikkyu entries at all (Jalan-only) — Ikkyu ∪ Jalan union not achieved", "R2.no-ikkyu")

    # X2 locality via TripAdvisor geo slug
    ta_places = []
    for i, c in enumerate(cards, 1):
        u = c["sources"].get("ta_url") or ""
        if "-Reviews-" in u:
            ta_places.append((i, c["name"], u.rsplit("-", 1)[-1].replace(".html", "")))
    if ta_places:
        def _vn(x):
            x = x.lower().replace("_", "").replace("-", "")
            for a, b in (("ō", "o"), ("ū", "u"), ("ou", "o")):
                x = x.replace(a, b)
            return re.sub(r"([aiueo])\1+", r"\1", x)
        pref_root = (pref or "").replace("-", "")
        root = _vn(strip_suffix(muni))
        if pref_root and root.startswith(_vn(pref_root)) and len(root) > len(_vn(pref_root)) + 2:
            root = root[len(_vn(pref_root)):]          # e.g. Miyagimisato -> misato
        off_muni, off_pref, trunc = [], [], 0
        for i, nm, pl in ta_places:
            if "_Prefecture" not in pl:
                trunc += 1                              # truncated geo slug: locality unknown, not a FAIL
            elif pref_root and _vn(pref_root) not in _vn(pl):
                off_pref.append((i, nm, pl))
            if root and root not in _vn(pl):
                off_muni.append((i, nm, pl))
        st["ta_off_muni"] += len(off_muni)
        st["ta_off_pref"] += len(off_pref)
        st["ta_trunc"] = st.get("ta_trunc", 0) + trunc
        if off_pref:
            res.add("X2", "FAIL", f"{kind}: {len(off_pref)} TripAdvisor entries geo-tagged to another prefecture: " + ", ".join(f"#{i} {short(nm,20)} ({pl})" for i, nm, pl in off_pref[:3]), "X2.ta-other-pref", len(off_pref))
        if off_muni:
            res.add("X2", "WARN", f"{kind}: {len(off_muni)}/{len(ta_places)} TripAdvisor entries geo-tagged to a place other than '{muni}': " + ", ".join(f"#{i} ({pl})" for i, nm, pl in off_muni[:3]), "X2.ta-other-muni", len(off_muni))
        if trunc:
            res.add("X2", "WARN", f"{kind}: {trunc} TripAdvisor URLs have a truncated geo slug (locality not verifiable from URL)", "X2.ta-truncated", trunc)

    # X3 duplicate names within section
    names = Counter(re.sub(r"[\s\u3000]", "", c["name"]) for c in cards if c["name"])
    dn = [k for k, v in names.items() if v > 1]
    if dn:
        res.add("X3", "WARN", f"{kind}: same facility name listed more than once ({len(dn)} names): " + ", ".join(short(x, 20) for x in dn[:4]), "X3.same-name", sum(names[k] - 1 for k in dn))

    # R3 photos
    page_key = "/".join(urlparse(url).path.strip("/").split("/")[:2])
    accepted = [f"#{i} {c['name']}" for i, c in enumerate(cards, 1) if not c["img"] and nophoto_logged(page_key, c)]
    nophoto = [f"#{i} {c['name']}" for i, c in enumerate(cards, 1) if not c["img"] and not nophoto_logged(page_key, c)]
    stale = [f"#{i} {c['name']}" for i, c in enumerate(cards, 1) if not c["img"] and c["credit"]]
    st["nophoto"] += len(nophoto)
    st["nophoto_accepted"] += len(accepted)
    st["nophoto_but_credit"] += len(stale)
    if accepted:
        res.add("R3", "PASS", f"{kind}: {len(accepted)}/{n} cards have no photo after the full search — accepted text cards, logged in no-photo-found.csv",
                f"R3.{kind.lower()}-nophoto-accepted", len(accepted))
    if nophoto:
        res.add("R3", "FAIL", f"{kind}: {len(nophoto)}/{n} facilities without photo and not logged in no-photo-found.csv (first: {', '.join(nophoto[:2])})",
                f"R3.{kind.lower()}-nophoto", len(nophoto))
    if stale:
        res.add("R3", "WARN", f"{kind}: {len(stale)} photo-less cards still carry a photo-credit comment (stale metadata; first: {', '.join(stale[:2])})",
                "R3.stale-credit", len(stale))
    nocredit = [f"#{i} {c['name']}" for i, c in enumerate(cards, 1) if c["img"] and not (c["credit"] and c["credit"]["url"])]
    st["nocredit"] += len(nocredit)
    if nocredit:
        res.add("R3", "FAIL", f"{kind}: {len(nocredit)} photos have no photo-credit metadata (first: {', '.join(nocredit[:3])})", "R3.no-credit", len(nocredit))
    fake, ta_photo, wrongtype, ph = [], [], [], []
    for i, c in enumerate(cards, 1):
        cu = (c["credit"] or {}).get("url") or ""
        host = host_of(cu)
        if host in PLACEHOLDER_HOSTS:
            fake.append(f"#{i} {c['name']} ({host})")
        if not c["img"]:
            continue
        if PLACEHOLDER_IMG_RE.search(c["img"].split("/")[-1]):
            ph.append(f"#{i} {c['img'].split('/')[-1]}")
        if "tripadvisor" in host:
            ta_photo.append(f"#{i} {c['name']}")
        elif kind == "Stay" and "tabelog.com" in host:
            wrongtype.append(f"#{i} {c['name']} (Tabelog photo on lodging)")
        elif kind == "Dining" and any(h in host for h in ("jalan.net", "ikkyu.com")):
            wrongtype.append(f"#{i} {c['name']} (Jalan/Ikkyu photo on restaurant)")
    st["fake_credit"] += len(fake)
    st["ta_photo"] += len(ta_photo)
    if ph:
        res.add("R3", "FAIL", f"{kind}: placeholder/AI-looking image filenames: " + ", ".join(ph[:3]), "R3.placeholder-name")
    if fake:
        res.add("R3", "FAIL", f"{kind}: {len(fake)} photo credits point to placeholder domains (credit metadata broken): " + ", ".join(fake[:3]), "R3.fake-credit", len(fake))
    if ta_photo:
        # 2026-10-17 Michael: keep all photos regardless of source unless a takedown is requested; source is informational only
        res.add("R3", "INFO", f"{kind}: {len(ta_photo)} photos credited to TripAdvisor (kept; source is not a quality flag)", "R3.ta-photo", len(ta_photo))
    if wrongtype:
        res.add("R3", "INFO", f"{kind}: {len(wrongtype)} photos from another source type (kept; source is not a quality flag)", "R3.type-mismatch", len(wrongtype))
    srcs = Counter(c["img"] for c in cards if c["img"])
    reused = [s.split("/")[-1] for s, k in srcs.items() if k > 1]
    if reused:
        res.add("R3", "WARN", f"{kind}: same image used for several facilities: " + ", ".join(reused[:3]), "R3.reused")
    if not nophoto and not nocredit and not fake:
        res.add("R3", "PASS", f"{kind}: all {n} facilities have a photo with credit metadata")

    # R4 4-line format
    other, fw_warn, ja_headline = [], [], []
    nodesc = noen = 0
    for i, c in enumerate(cards, 1):
        probs = []
        seq = c["line_seq"]
        if seq not in (list(LINE_CLASSES), list(LINE_CLASSES[:3])):
            probs.append(f"line structure {seq}")
        if not c["name"]:
            probs.append("empty JA name")
        b = c["blurb"]
        if c["en_first"]:
            # English-first card: line 1 = English headline (no Japanese), line 2 = Japanese subtitle with lang="ja"
            if CJK.search(c["headline"]):
                probs.append("English-first card but headline has Japanese")
            if not CJK.search(c["name"]) or (c["name_ja_lang"] or "").lower() != "ja":
                probs.append("Japanese subtitle missing or lacks lang=\"ja\"")
        elif c["name"] and CJK.search(c["name"]):
            ja_headline.append(i)
        if not b or CJK.search(b):
            noen += 1
        elif FULLWIDTH_RE.search(b):
            fw_warn.append(f"#{i} '{short(b, 30)}'")
        if SLUG_JUNK_RE.search(c["name"] + " | " + (b or "")):
            probs.append(f"name derived from URL slug: '{short(c['name'], 45)}'")
        m = RANK_RE.match(c["meta"] or "")
        nm = NEUTRAL_RE.match(c["meta"] or "") if kind == "Dining" else None
        if nm:
            if muni and nm.group(1) != muni:
                probs.append(f"neutral label '{nm.group(1)}' ≠ page '{muni}'")
        elif not m:
            probs.append(f"line 3 '{short(c['meta'] or '', 40)}' ≠ '#N ranked in {muni}'")
        else:
            if int(m.group(1)) != i:
                probs.append(f"rank #{m.group(1)} at position {i}")
            if muni and m.group(2) != muni:
                probs.append(f"ranked in '{m.group(2)}' ≠ page '{muni}'")
        d = c["desc"]
        if not d:
            nodesc += 1
        else:
            if CJK.search(d):
                probs.append("line 4 not English")
            if len(d) < 15 or d.strip().lower() == (b or "").strip().lower():
                probs.append("line 4 too short / just the name")
            if LISTING_WORDS_STRICT.search(d) or SCORE_RE.search(d):
                probs.append("line 4 has listing label/score")
        if c["extra_text"]:
            probs.append(f"extra visible text '{short(c['extra_text'], 40)}'")
        if LISTING_WORDS_STRICT.search(c["meta"] or "") or SCORE_RE.search(c["meta"] or "") or BLURB_LABEL_RE.search(b or ""):
            probs.append("listing label/score visible")
        if re.search(r"tabelog|食べログ|tripadvisor|じゃらん|jalan\.net|ikkyu\.com", c["name"], re.I):
            probs.append("listing label in name")
        if probs:
            other.append(f"#{i} {short(c['name'], 20)}: {'; '.join(probs)}")
    st["nodesc"] += nodesc
    st["noen"] += noen
    st["other_format"] += len(other)
    if nodesc:
        res.add("R4", "WARN", f"{kind}: {nodesc}/{n} cards omit line 4 (no filler; real explanation preferred)", "R4.no-line4", nodesc)
    if noen:
        res.add("R4", "FAIL", f"{kind}: {noen}/{n} cards whose line 2 (English name) is missing or Japanese", "R4.line2-not-en", noen)
    if other:
        res.add("R4", "FAIL", f"{kind}: {len(other)} cards with other format problems, e.g. " + " | ".join(other[:3]), "R4.other", len(other))
    if fw_warn:
        res.add("R4", "WARN", f"{kind}: full-width JP punctuation in English line ({len(fw_warn)}): " + ", ".join(fw_warn[:3]), "R4.fullwidth", len(fw_warn))
    desc_vals = [c["desc"] for c in cards if c["desc"]]
    if desc_vals:
        boiler = [d for d, k in Counter(desc_vals).items() if k > 3]
        if boiler:
            res.add("R4", "WARN", f"{kind}: identical explanation reused on >3 cards (template filler?): '{short(boiler[0], 50)}'", "R4.boilerplate")
        nosrc = sum(1 for c in cards if c["desc"] and not c["desc_source"])
        if nosrc:
            res.add("R4", "WARN", f"{kind}: {nosrc} explanations lack desc-source metadata (cannot verify 'sourced, not invented')", "R4.desc-unsourced", nosrc)
    if ja_headline:
        # Michael 2026-10-17: English everywhere. Legacy layout (Japanese headline, English on line 2) is WARN until the tree is converted; BJ_ENGLISH_FIRST_STRICT=1 makes it FAIL.
        res.add("R4", "FAIL" if os.environ.get("BJ_ENGLISH_FIRST_STRICT") == "1" else "WARN",
                f"{kind}: {len(ja_headline)}/{n} cards headline the Japanese name (run scripts/english_first_headings.py)", "R4.ja-headline", len(ja_headline))
    if not (nodesc or noen or other):
        res.add("R4", "PASS", f"{kind}: all {n} cards match the 4-line format (English headline + Japanese subtitle, or legacy)")


def check_other_rows(res, cards, title, stats):
    """Non-ranked rows (Sights/Clinics/Shop/Onsen…): English explanation (line 4) required."""
    n = len(cards)
    st = stats["Other"]
    st["cards"] += n
    nodesc, legacy, jpfirst, jp_expl = [], 0, [], []
    for i, c in enumerate(cards, 1):
        d, b = c["desc"], c["blurb"] or ""
        explanatory_blurb = bool(b) and (" — " in b or len(b.split()) >= 6)
        if not d:
            if explanatory_blurb and not CJK.search(b):
                legacy += 1
            else:
                nodesc.append(f"#{i} {short(c['name'], 25)}")
        if c["name"] and not is_latin_first(c["name"]) and not c["blurb"]:
            jpfirst.append(short(c["name"], 25))
        for txt in (d, b if explanatory_blurb else None):
            if txt and CJK.search(txt):
                jp_expl.append(short(txt, 30))
        addr = (c["meta"] or "").split("·")[0]
        if CJK.search(addr):
            jpfirst.append(f"address {short(addr, 25)}")
    st["nodesc"] += len(nodesc)
    st["legacy"] += legacy
    if nodesc:
        res.add("R4", "WARN", f"{title}: {len(nodesc)}/{n} rows omit English explanation (no filler; real text preferred): " + ", ".join(nodesc[:3]), "R4.other-no-line4", len(nodesc))
    if legacy:
        res.add("R4", "WARN", f"{title}: {legacy}/{n} rows use the legacy layout (explanation in line 2; no p.place-desc / JA-name line)", "R4.other-legacy", legacy)
    if jpfirst:
        res.add("R5", "FAIL", f"{title}: {len(jpfirst)} names/addresses not English-first: " + "; ".join(jpfirst[:3]), "R5.en-first", len(jpfirst))
    if jp_expl:
        res.add("X5", "FAIL", f"{title}: Japanese text in English explanation ({len(jp_expl)}): '{jp_expl[0]}'", "X5.jp-in-en", len(jp_expl))


# ---------------------------------------------------------------- page types
def get_map(map_url, ctx):
    if map_url in ctx["maps"]:
        return ctx["maps"][map_url]
    r, err = ctx["fetcher"].get_page(map_url)
    out = {"ok": False, "names": {}, "err": err}
    if r is not None and r.status_code == 200 and "<svg" in r.text[:5000]:
        out["ok"] = True
        for m in re.finditer(r"<a\b[^>]*>", r.text):
            tag = m.group(0)
            nm = re.search(r'data-name="([^"]*)"', tag)
            hr = re.search(r'href="([^"]*)"', tag)
            if nm:
                out["names"][nm.group(1)] = hr.group(1) if hr else None
    elif r is not None:
        out["err"] = f"HTTP {r.status_code}"
    ctx["maps"][map_url] = out
    return out



# ---- AUDIT-47 (2026-10-15) shared-fix rules: R1.cap, R2.neighbour-unlabelled, R3.stay-food-photo, R4.rough-romaji,
#      X12.title-as-name, X22 photo coverage %, X23 English-description coverage % ----
sys.path.insert(0, "/workspace/p1/partials-build/shared")
try:
    import bj_shared as BJS
except Exception:  # pragma: no cover
    BJS = None
MIN_PHOTO_PCT = float(os.environ.get("BJ_MIN_PHOTO_PCT", "100"))
MIN_DESC_PCT = float(os.environ.get("BJ_MIN_DESC_PCT", "100"))
NEIGH_RE = re.compile(r"\bin [^,;.]{1,40}, ([A-Z][A-Za-z' -]{2,30}?)(?: with| and|;|\.|,|$)")
def _pct(a, b): return 100.0 if not b else round(100.0 * a / b, 1)

def shared_checks(res, main, secs, dining, stay, muni, pref, url, info):
    if BJS is None:
        for k in ("X22", "X23"): res.skip(k, "bj_shared not importable")
        return
    slug = urlparse(url).path.strip("/").split("/")[-1]
    page = f"{pref}/{slug}"
    # --- R1.cap: exactly 24 (Dining) / 12 (Stay) and below the population target, or max rank below min(target, source total)
    pop = BJS.town_pop(pref, slug)
    td, ts = BJS.target_dining(pop), BJS.target_stay(pop)
    exhausted_d = bool(main.find(string=lambda t: isinstance(t, Comment) and "source-exhausted: dining" in t))
    exhausted_s = bool(main.find(string=lambda t: isinstance(t, Comment) and "source-exhausted: stay" in t))
    nd, ns = len(dining), len(stay)
    info.update(pop=pop, dining_target=td, stay_target=ts)
    if pop is not None:
        if nd in (24, 12) and nd < td and not exhausted_d:
            res.add("R1", "FAIL", f"Dining stops at exactly {nd} but the population target is {td} (pop {pop:,}) — hard cap suspected", "R1.cap", 1)
        elif nd < td and not exhausted_d:
            res.add("R1", "FAIL" if os.environ.get("BJ_CAP_STRICT", "1") == "1" else "WARN", f"Dining {nd} < target {td} (pop {pop:,}) and no 'source exhausted' marker", "R1.below-target", 1)
        if ns == 12 and ns < ts and not exhausted_s:
            res.add("R2", "FAIL", f"Stay stops at exactly 12 but the population target is {ts} (pop {pop:,}) — hard cap suspected", "R2.cap", 1)
        mr = max([int(m.group(1)) for c in dining for m in [re.match(r"#(\d+) ranked", c.get("meta") or "")] if m] or [0])
        if dining and mr < min(td, nd + 0) and mr != nd and not any(NEUTRAL_RE.match(c.get("meta") or "") for c in dining):
            res.add("R1", "WARN", f"Dining max rank #{mr} below target {td}", "R1.max-rank", 1)
    # --- R2.neighbour-unlabelled
    near_page = main.select_one("p.stay-none, p.stay-near") is not None or "Stays near" in (main.get_text(" ", strip=True)[:400])
    unl = []
    for c in stay:
        m = NEIGH_RE.search(c.get("desc") or "")
        if m and muni and m.group(1).strip().lower() != muni.lower() and not re.search(r"neighbou?ring|nearby", c.get("desc") or "", re.I):
            if not near_page: unl.append(f"{c['name']} (in {m.group(1).strip()})")
    if unl:
        res.add("R2", "FAIL", f"{len(unl)} Stay cards describe a hotel in another town without an 'In neighbouring X' label: " + ", ".join(unl[:3]), "R2.neighbour-unlabelled", len(unl))
    # --- R4.rough-romaji / X12.title-as-name
    rough = [c["blurb"] for c in dining + stay if BJS.rough_romaji(c.get("blurb") or "")]
    if rough:
        sev = "FAIL" if len(rough) > max(2, 0.05 * (nd + ns)) else "WARN"
        res.add("R4", sev, f"{len(rough)} EN names with romaji artefacts (e.g. '{short(rough[0], 40)}')", "R4.rough-romaji", len(rough))
    allcards = []
    for t, sec in secs.items():
        allcards += parse_cards(sec)
    tn = [c["name"] for c in allcards if BJS.title_as_name(c["name"])]
    if tn:
        res.add("X12", "FAIL", f"{len(tn)} cards use a scraped SEO page title as the place name: '{short(tn[0], 50)}'", "X12.title-as-name", len(tn))
    # --- R3.stay-food-photo (judge; local CLIP, opt-in: BJ_CHECK_JUDGE=1) + tiny/promo urls
    if os.environ.get("BJ_CHECK_JUDGE") == "1":
        bad = []
        for c in stay:
            if c.get("img") and "/media/" in c["img"]:
                lp = os.path.join(os.environ.get("BJ_MEDIA_ROOT", "/workspace/p1/quality/audit47/site"), c["img"].lstrip("/"))
                v = BJS.judge(lp) if os.path.exists(lp) else None
                if v and v.get("reject"): bad.append(f"{c['name']} ({v['reject']})")
        if bad:
            res.add("R3", "FAIL", f"{len(bad)} Stay photos show food/promo/pet/people: " + ", ".join(bad[:3]), "R3.stay-food-photo", len(bad))
    # --- X22 / X23 coverage
    cards = dining + stay
    nlog = 0; nph = 0
    for c in cards:
        if c.get("img"): nph += 1
        elif nophoto_logged(page, c) or any("photo_search" in x for x in (c.get("credit") or "",)): nlog += 1
    pct_raw, pct_ok = _pct(nph, len(cards)), _pct(nph + nlog, len(cards))
    nd_ok = sum(1 for c in cards if (c.get("desc") or "").strip() and not CJK.search(c.get("desc") or ""))
    dpct = _pct(nd_ok, len(cards))
    info.update(photo_pct=pct_raw, photo_pct_justified=pct_ok, desc_pct=dpct, cards=len(cards))
    msg = f"photo coverage {pct_raw}% ({nph}/{len(cards)}; {nlog} logged no-photo after full search)"
    res.add("X22", "FAIL" if pct_ok < MIN_PHOTO_PCT else "PASS", msg + (f" < {MIN_PHOTO_PCT:g}%" if pct_ok < MIN_PHOTO_PCT else ""), "X22.photo-coverage", len(cards) - nph - nlog)
    res.add("X23", "FAIL" if dpct < MIN_DESC_PCT else "PASS", f"English description coverage {dpct}% ({nd_ok}/{len(cards)})" + (f" < {MIN_DESC_PCT:g}%" if dpct < MIN_DESC_PCT else ""), "X23.desc-coverage", len(cards) - nd_ok)

def check_municipality(res, soup, url, ctx):
    main = soup.find("main") or soup.body
    path = urlparse(url).path.strip("/").split("/")
    pref = path[0] if path else ""
    h1 = soup.select_one("h1.page-title")
    muni = re.split(r",| in |:", h1.get_text(strip=True))[0].strip() if h1 else ""  # R4 short town name
    secs = sections_by_title(main)
    titles = list(secs.keys())
    stats = {"Dining": Counter(), "Stay": Counter(), "Other": Counter()}
    click = Counter()
    dining = parse_cards(secs["Dining"]) if "Dining" in secs else []
    stay = parse_cards(secs["Stay"]) if "Stay" in secs else []
    other_text = " ".join(secs[t].get_text(" ", strip=True) for t in titles if t not in RANKED)

    if not dining:
        res.add("R1", "FAIL", "no Dining section" if "Dining" not in secs else "Dining section is empty", "R1.no-dining")
    if not dining and not stay:
        res.add("R2", "FAIL", f"thin page: no Dining and no Stay (sections: {titles or 'none'})", "R2.thin")
    elif not stay and "Stay" in secs and secs["Stay"].select_one("p.stay-none a[href]"):
        a = secs["Stay"].select_one("p.stay-none a[href]")
        txt = secs["Stay"].select_one("p.stay-none").get_text(" ", strip=True)
        target = urljoin(url, a["href"])
        if is_external(target) or not re.match(r"^/[a-z-]+/[a-z0-9-]+/$", urlparse(target).path):
            res.add("R2", "FAIL", f"Stay: no-lodging line must link to a bokenjapan.com municipality page (got {short(a['href'], 50)})", "R2.no-stay-badlink")
        elif not txt.startswith("No bookable places to stay found in"):
            res.add("R2", "FAIL", f"Stay: unexpected no-lodging wording: '{short(txt, 60)}'", "R2.no-stay-wording")
        else:
            res.add("R2", "PASS", f"Stay: documented no-lodging state — '{short(txt, 80)}'", "R2.no-stay-documented")
    elif not stay:
        hint_src = other_text + " " + " ".join(c["name"] + " " + (c["blurb"] or "") for c in dining)
        m = LODGING_HINT_RE.search(hint_src)
        if m:
            res.add("R2", "FAIL", f"Stay missing/empty but page mentions lodging ('{m.group(0)}')", "R2.no-stay-lodging")
        else:
            res.add("R2", "WARN", "Stay=0 — needs human confirmation that no local lodging/ryokan/onsen exists", "R2.no-stay")
    for kind, cards in (("Dining", dining), ("Stay", stay)):
        if cards:
            check_facility_cards(res, cards, kind, muni, pref, url, ctx, stats)
            check_clickable(res, cards, kind, url, ctx, click)
    for t in titles:
        if t in RANKED:
            continue
        oc = parse_cards(secs[t])
        if oc:
            check_other_rows(res, oc, t, stats)
            check_clickable(res, oc, t, url, ctx, click)
    sn = {re.sub(r"[\s\u3000]", "", c["name"]) for c in stay}
    both = [c["name"] for c in dining if re.sub(r"[\s\u3000]", "", c["name"]) in sn]
    if both:
        res.add("X3", "WARN", f"{len(both)} facilities appear in both Stay and Dining (ok if hotel restaurant): " + ", ".join(short(x, 20) for x in both[:3]), "X3.stay-dining", len(both))

    for dt in main.select(".meta-block dt"):
        if dt.get_text(strip=True).lower() == "address":
            dd = dt.find_next_sibling("dd")
            if dd and CJK.search(dd.get_text()):
                res.add("R5", "FAIL", f"address not English-first: '{short(dd.get_text(strip=True), 50)}'", "R5.en-first")
    for sel in (".page-sub", ".locator-label", ".locator-note"):
        el = main.select_one(sel)
        if el and CJK.search(el.get_text()):
            res.add("X5", "FAIL", f"Japanese in English field {sel}: '{short(el.get_text(strip=True), 40)}'", "X5.jp-in-en")

    # R7 template
    missing = []
    for sel, lab in ((".crumb", "breadcrumb"), ("h1.page-title", "h1.page-title"), (".page-sub", "page-sub"),
                     (".locator .map-wrap", "locator map"), ("figure.cover img", "cover photo"),
                     (".meta-block", "Official meta-block")):
        if not main.select_one(sel):
            missing.append(lab)
    mb = main.select_one(".meta-block")
    if mb:
        dts = [d.get_text(strip=True).lower() for d in mb.select("dt")]
        if not mb.find("a", href=True):
            missing.append("official link")
        if "address" not in dts:
            missing.append("address")
        if "phone" not in dts:
            res.add("R7", "WARN", "meta-block has no Phone", "R7.phone")
    if missing:
        res.add("R7", "FAIL", "missing Ōhira-template elements: " + ", ".join(missing), "R7.missing")
    order = [t for t in titles if t in RANKED]
    if order and (titles[: len(order)] != ["Stay", "Dining"][: len(order)] or (len(order) == 2 and order != ["Stay", "Dining"])):
        res.add("R7", "WARN", f"section order {titles} differs from Ōhira (Stay, Dining first)", "R7.order")
    if not missing:
        res.add("R7", "PASS", "Ōhira template elements present")

    info = {"muni": muni, "pref": pref, "sections": titles, "dining": len(dining), "stay": len(stay),
            "dining_photos": sum(1 for c in dining if c["img"]), "stay_photos": sum(1 for c in stay if c["img"]),
            "stats": {k: dict(v) for k, v in stats.items()}, "click": dict(click)}

    shared_checks(res, main, secs, dining, stay, muni, pref, url, info)  # AUDIT-47 P10 + standing quality bar
    # X6 cover
    cover = main.select_one("figure.cover")
    cimg = cover.find("img") if cover else None
    if not cimg:
        res.add("X6", "FAIL", "no cover photo", "X6.missing")
    else:
        info["cover_src"] = cimg.get("src")
        if not credit_of(comments_of(cover)):
            res.add("X6", "WARN", "cover photo has no photo-credit metadata", "X6.no-credit")
        w = int(re.sub(r"\D", "", cimg.get("width") or "0") or 0)
        if w and w < 800:
            res.add("X6", "WARN", f"cover declared width {w}px (<800)", "X6.small")
        alt = cimg.get("alt") or ""
        if not alt.strip() or CJK.search(alt):
            res.add("X6", "WARN", f"cover alt missing/not English: '{short(alt, 30)}'", "X6.alt")

    # X7 locator map
    mw = main.select_one(".locator .map-wrap")
    if mw is None:
        res.add("X7", "FAIL", "no locator map", "X7.missing")
    elif not mw.get("data-map"):
        if not mw.find("svg"):
            res.add("X7", "FAIL", "map-wrap has neither data-map nor inline svg", "X7.missing")
    else:
        murl = urljoin(url, mw["data-map"])
        here = mw.get("data-here") or ""
        mp = get_map(murl, ctx)
        if not mp["ok"]:
            res.add("X7", "FAIL", f"map {short(murl.replace(BASE, ''))} does not load ({mp['err']})", "X7.load")
        elif here not in mp["names"]:
            res.add("X7", "FAIL", f"town '{here}' not found in prefecture map (no highlight)", "X7.not-highlighted")
        else:
            href = mp["names"][here] or ""
            if href and href not in ("./", ".") and urljoin(murl, href).rstrip("/") != url.rstrip("/"):
                res.add("X7", "WARN", f"map shape for '{here}' links to {href}, not this page", "X7.wrong-link")
        if here != muni:
            res.add("X7", "WARN", f"map data-here '{here}' ≠ h1 '{muni}'", "X7.name-mismatch")

    # X9 crumb / nav
    crumb = main.select_one(".crumb")
    if crumb:
        links = [urljoin(url, a["href"]) for a in crumb.find_all("a", href=True)]
        exp_pref = f"{BASE}/{pref}/"
        if exp_pref not in links:
            res.add("X9", "FAIL", f"breadcrumb has no link to /{pref}/ (links: {[l.replace(BASE, '') for l in links]})", "X9.crumb")
        if BASE + "/" not in links:
            res.add("X9", "WARN", "breadcrumb has no link to the homepage", "X9.crumb-home")
        if muni and muni not in crumb.get_text():
            res.add("X9", "WARN", f"breadcrumb does not name '{muni}'", "X9.crumb-name")
    nav = [urljoin(url, a["href"]) for a in soup.select(".mast-nav a[href]")]
    if nav and f"{BASE}/{pref}/" not in nav:
        res.add("X9", "FAIL", f"header nav lacks a link back to /{pref}/", "X9.nav")

    # R8 images
    imgs = []
    if cimg is not None:
        imgs.append((cimg.get("src"), "cover"))
    for kind, cards in (("Stay", stay), ("Dining", dining)):
        imgs += [(c["img"], kind) for c in cards if c["img"]]
    for t in titles:
        if t not in RANKED:
            imgs += [(i.get("src"), t) for i in secs[t].find_all("img") if i.get("src")]
    empty_src = [i for i in main.find_all("img") if not (i.get("src") or "").strip()]
    if empty_src:
        res.add("R8", "FAIL", f"{len(empty_src)} <img> without src", "R8.no-src")
    n = check_images(res, imgs, url, ctx, "page images", info)
    if not any(f["sev"] == "FAIL" for f in res.rules["R8"]["findings"]):
        res.add("R8", "PASS", f"{n} images loaded OK")
    return info


def check_home(res, soup, url, ctx):
    for r in ("R1", "R2", "R3", "R4", "R7", "X2", "X3", "X6", "X7", "X9", "X10"):
        res.skip(r, "n/a on homepage")
    info = {}
    imgs = [(i.get("src"), "home") for i in soup.find_all("img") if i.get("src") and not i["src"].startswith("data:")]
    for m_ in soup.find_all("meta", attrs={"property": "og:image"}):
        if m_.get("content"):
            imgs.append((m_["content"], "og"))
    for l_ in soup.find_all("link", rel=lambda v: v and any("icon" in x for x in v)):
        if l_.get("href"):
            imgs.append((l_["href"], "icon"))
    imgs = list(OrderedDict.fromkeys(imgs))
    n = check_images(res, imgs, url, ctx, "homepage images", info)
    if not any(f["sev"] == "FAIL" for f in res.rules["R8"]["findings"]):
        res.add("R8", "PASS", f"{n} images loaded OK; all homepage links checked")
    hrefs = {urljoin(url, a["href"]).split("#")[0] for a in soup.find_all("a", href=True)}
    for p in ("privacy.html", "terms.html"):
        u = f"{BASE}/{p}"
        r = ctx["fetcher"].head(u, "link")
        if r.get("status") != 200:
            res.add("X13", "FAIL", f"/{p} not reachable ({r.get('status') or r.get('err')})", "X13.unreachable")
        if u not in hrefs and u.replace(".html", "") not in hrefs:
            res.add("X13", "WARN", f"homepage does not link /{p}", "X13.unlinked")
    info["pref_links"] = len({a["href"] for a in soup.find_all("a", href=True) if re.fullmatch(r"/[a-z]+/", a["href"])})
    return info


def check_pref_index(res, soup, url, ctx):
    for r in ("R1", "R2", "R3", "R4", "R7", "X2", "X3", "X6", "X9", "X13"):
        res.skip(r, "n/a on prefecture index")
    pref = urlparse(url).path.strip("/")
    links = [urljoin(url, a["href"]).split("#")[0] for a in (soup.find("main") or soup).find_all("a", href=True)]
    munis = sorted({u for u in links if re.fullmatch(re.escape(url) + r"[a-z0-9-]+/", u)})
    info = {"muni_links": len(munis)}
    inv = ctx.get("inventory")
    if inv is not None:
        expected = {f"{BASE}/{p.replace('index.html', '')}" for p in inv if p.startswith(pref + "/")}
        orphans = sorted(expected - set(munis))
        dead = sorted(set(munis) - expected)
        info.update(inventory=len(expected), orphans=len(orphans), not_in_inventory=len(dead))
        if orphans:
            res.add("X10", "FAIL", f"{len(orphans)} published towns not linked from this index: " + ", ".join(o.replace(BASE, '') for o in orphans[:5]), "X10.orphan", len(orphans))
        for d in dead:
            r = ctx["fetcher"].head(d, "link")
            if r.get("status") != 200:
                res.add("X10", "FAIL", f"index links to missing page {d.replace(BASE, '')} ({r.get('status')})", "X10.dead")
    mw = (soup.find("main") or soup).select_one(".map-wrap")
    if mw is not None and mw.get("data-map"):
        mp = get_map(urljoin(url, mw["data-map"]), ctx)
        if not mp["ok"]:
            res.add("X7", "FAIL", f"prefecture map does not load ({mp['err']})", "X7.load")
        else:
            info["map_shapes"] = len(mp["names"])
            unlinked = [nm for nm, h in mp["names"].items() if not h]
            if unlinked:
                res.add("X7", "WARN", f"{len(unlinked)} map shapes without a link", "X7.unlinked-shape")
            if len(mp["names"]) != len(munis):
                res.add("X7", "WARN", f"map has {len(mp['names'])} shapes but index lists {len(munis)} towns", "X7.count")
    elif mw is None:
        res.add("X7", "WARN", "prefecture index has no map", "X7.missing")
    return info


# ---------------------------------------------------------------- driver
def finalize(res):
    for k, r in res.rules.items():
        if r["status"] == "PASS" and not r["findings"]:
            r["findings"].append({"sev": "PASS", "msg": "no issues found"})
    return res


# ---- V2 checks (bj-pref-check v2, 2026-10-14) ----
MACRON_RE = re.compile(r"[ĀāĒēĪīŌōŪū]")
_LOAN = None
def v2_loans():
    """romaji -> english for katakana loanwords (loan_jm.json), cached."""
    global _LOAN
    if _LOAN is not None:
        return _LOAN
    cache = "/tmp/bj_loan_romaji.json"
    src = os.environ.get("BJ_LOAN_JSON", "/workspace/p1/romaji/loan_jm.json")
    try:
        if os.path.exists(cache) and os.path.getmtime(cache) >= os.path.getmtime(src):
            _LOAN = json.load(open(cache)); return _LOAN
        import pykakasi
        kk = pykakasi.kakasi(); _LOAN = {}
        for ja, en in json.load(open(src)).items():
            r = "".join(x["hepburn"] for x in kk.convert(ja)).lower()
            if len(ja) >= 4 and len(r) >= 5 and r.isalpha() and r != str(en).lower().replace(" ", ""):
                _LOAN.setdefault(r, str(en))
        json.dump(_LOAN, open(cache, "w"))
    except Exception as e:
        print("V2 loan list unavailable:", e, file=sys.stderr); _LOAN = {}
    for r, en in {"gorufu": "golf", "hairando": "highland", "ritchimondo": "Richmond", "kantorikurabu": "country club",
                  "soreiyu": "Soleil", "raimu": "lime", "kantori": "country", "kurabu": "club", "hoteru": "hotel"}.items():
        _LOAN.setdefault(r, en)
    return _LOAN

def v2_loan_hit(tok):
    L = v2_loans(); t = tok.lower()
    if len(t) >= 5 and t in L:
        return L[t]
    for i in range(5, len(t) - 4):  # two glued loanwords, e.g. Kantorikurabu
        if t[:i] in L and t[i:] in L:
            return L[t[:i]] + " " + L[t[i:]]
    return None

# V2.2: romaji-looking katakana spellings (Faibuddo, Naporipittsua, Sukaiparesu, Furaipan) and 'Kankoku' (= Korean)
LOAN_PAT = re.compile(r"\b[A-Za-z]*(?:ddo|ppu|ttsu|kku|ggu|bbu|ffu|ddu)\b|\b[A-Za-z]*(?:pittsu|tsua\b|faib|furai|furansu|sukai|daburu|hapinesu|paresu|sutoro|jiera|pasuta|aruka|mauntoin)[A-Za-z]*", re.I)
KANKOKU = re.compile(r"\bKankoku\b")

X15_CAP = 8  # build-pages-site.py THUMB_CAPS (Stay/Dining = 8)

def _vid(u):
    m = re.search(r"(\d{4,})/?(?:[.?#]|$)", u or "") or re.search(r"[-_/](?:s)?(\d{4,})\.(?:jpe?g|png|webp)", u or "")
    return m.group(1) if m else None

def v2_page_checks(res, sub, u):
    path = short(urlparse(u).path, 50)
    names, wrong, loans, mac = Counter(), [], [], []
    # (b) mirror build-pages-site.py cap_facility_thumbs: only the first X15_CAP distinct thumbs per section are published
    capped = set()
    for ul in sub.select("ul.place-list"):
        kept = set()
        for li in ul.find_all("li", recursive=False):
            im = li.find("img")
            if im is None or not im.get("src") or "/media/" not in im["src"]:
                continue
            nm_ = im["src"].rsplit("/", 1)[-1]
            if nm_ in kept:
                continue
            if len(kept) >= X15_CAP:
                capped.add(id(li))
            else:
                kept.add(nm_)
    for li in sub.select("ul.place-list > li"):
        a = li.find("a", href=True); img = li.find("img")
        nm = li.select_one(".place-name"); en = li.select_one(".place-blurb") or li.select_one(".place-name-ja")
        ja_t = nm.get_text(" ", strip=True) if nm else ""; en_t = en.get_text(" ", strip=True) if en else ""
        if ja_t or en_t:
            names[(ja_t, en_t)] += 1
        link_id = _vid(a["href"]) if a and re.search(r"tabelog\.com|jalan\.net|ikk?yu\.com|tripadvisor|travel\.rakuten", a["href"]) else None  # venue-ID hosts only
        if link_id and img is not None and id(li) not in capped:
            im = re.search(r"-(\d{4,})\.(?:jpe?g|png|webp)", img.get("src", ""))
            cr = credit_of(comments_of(li)); cid = _vid(cr["url"]) if cr and cr.get("url") and re.search(r"tabelog\.com|jalan\.net|ikk?yu\.com|tripadvisor|travel\.rakuten", cr["url"]) else None  # official-site page numbers are not venue IDs (Ohira Manyo Chaya 1373.html)
            bad = [x for x in ((im.group(1) if im else None), cid) if x and x != link_id]
            if bad:
                wrong.append(f"{short(en_t or ja_t, 25)} link {link_id} photo {bad[0]}")
        if re.search(r"[\u30a0-\u30ff]{2,}", ja_t):
            for tok in re.findall(r"[A-Za-z]{4,}", en_t):
                h = v2_loan_hit(tok)
                if h:
                    loans.append(f"{tok}->{h}")
                elif LOAN_PAT.fullmatch(tok) or LOAN_PAT.match(tok):
                    loans.append(f"{tok}->(romaji katakana?)")  # V2.2 pattern flag
        _d = li.select_one(".place-desc")
        if KANKOKU.search(en_t + " " + (_d.get_text(" ", strip=True) if _d else "")):
            loans.append("Kankoku->Korean")
        if MACRON_RE.search(en_t):
            mac.append(en_t)
    for el in sub.select("title, h1, h2, .place-desc, .hub-tile-name, .lede, .bj-crumbs"):
        t = el.get_text(" ", strip=True)
        if MACRON_RE.search(t):
            mac.append(t)
    dup = [f"{e or j}x{c}" for (j, e), c in names.items() if c > 1]
    if wrong:
        res.add("X15", "FAIL", f"{path}: {len(wrong)} card photos from another venue ID: " + "; ".join(wrong[:3]), "X15.photo-venue", len(wrong))
    if loans:
        res.add("X16", "WARN", f"{path}: {len(loans)} letter-by-letter loanwords in EN names: " + ", ".join(loans[:4]), "X16.loanword", len(loans))
    if dup:
        res.add("X17", "WARN", f"{path}: {len(dup)} duplicate card names: " + ", ".join(dup[:3]), "X17.dup-name", len(dup))
    if mac:
        res.add("X19", "WARN", f"{path}: {len(mac)} EN strings with macrons: '{short(mac[0], 40)}'", "X19.macron", len(mac))

def v2_template(res, sub, u, hub=False):
    """X20 (V2.1): blocks emitted by generator-template 743c6acde (ai_friendly.py); markers from live /miyagi/ohira/."""
    parts = urlparse(u).path.strip("/").split("/")
    pref = parts[0].replace("-", " ").title() if parts and parts[0] else ""
    head_t = sub.head.find("title") if sub.head else sub.find("title")
    t = head_t.get_text(" ", strip=True) if head_t else ""
    h1 = sub.select_one("h1.page-title") or sub.find("h1")
    h = h1.get_text(" ", strip=True) if h1 else ""
    more = sub.select_one(".bj-more")
    mt = more.get_text(" ", strip=True) if more else ""
    pat = re.compile(r"[A-Z][^,]*, " + re.escape(pref))
    miss = []
    if not any(a.get_text(strip=True) == "Home" for a in sub.select("a[href]")): miss.append("Home crumb")
    if not (pat.search(t) and t.endswith("BokenJapan")): miss.append("title")
    if not pat.search(h): miss.append("H1")
    if not more: miss.append(".bj-more")
    if "More in" not in mt: miss.append("More in")
    if f"Nearby in {pref}" not in mt: miss.append("Nearby in")
    if hub and "Other towns" not in mt: miss.append("Other towns")
    if miss:
        res.add("X20", "FAIL", f"{short(urlparse(u).path, 50)}: missing template blocks: " + ", ".join(miss), "X20.template", 1)

def v2_hub_tiles(res, tiles):
    labels = {re.sub(r"[^a-z]", "", (t.select_one(".hub-tile-name") or t).get_text(" ", strip=True).lower()) for t in tiles}
    hrefs = {t["href"] for t in tiles}
    miss = [lab for lab, key, h in (("See", "see", "see/"), ("Do", "do", "do/"), ("Day-to-day", "daytoday", "day-to-day/"))
            if not any(key == x or x.startswith(key) for x in labels) and not any(h in x for x in hrefs)]
    if miss:
        res.add("X18", "FAIL", "hub missing tiles: " + ", ".join(miss), "X18.hub-tiles", len(miss))


def v2_hero_tiles(res, soup, url, tiles, ctx):
    """X21 (V2.2): FAIL any hub tile whose image is the hero/cover image (same file name, same URL, or byte-identical)."""
    cimg = soup.select_one("figure.cover img")
    if not cimg or not cimg.get("src"):
        return
    cu = urljoin(url, cimg["src"]); cb = None; bad = []
    def body(u):  # direct GET (not counted against the image budget: at most 1 + #tiles small files per hub)
        c = ctx.setdefault("_x21_body", {})
        if u not in c:
            try:
                r = ctx["fetcher"].s.get(u, timeout=25); c[u] = r.content if r.status_code == 200 else b""
            except Exception:
                c[u] = b""
        return c[u]
    for t in tiles:
        im = t.find("img")
        if not im or not im.get("src"):
            continue
        tu = urljoin(url, im["src"]); lab = (t.select_one(".hub-tile-name") or t).get_text(" ", strip=True)
        same = tu == cu or tu.rsplit("/", 1)[-1] == cu.rsplit("/", 1)[-1]
        if not same:
            if cb is None:
                cb = body(cu)
            tb = body(tu)
            same = bool(cb) and hashlib.sha256(tb).digest() == hashlib.sha256(cb).digest()
        if same:
            bad.append(f"{lab}={tu.rsplit('/', 1)[-1]}")
    if bad:
        res.add("X21", "FAIL", f"hub tile repeats the hero image ({cu.rsplit('/', 1)[-1]}): " + ", ".join(bad), "X21.hero-tile", len(bad))
    else:
        res.add("X21", "PASS", "no hub tile repeats the hero image", "X21.hero-tile")

def hub_merged_soup(res, soup, url, ctx):
    """Municipality hub layout: tiles link to sub-pages holding the ranked lists.
    Fetch them (2 levels), pool the cards, and rebuild Stay / Dining / Sights sections
    so the usual municipality checks run on the full card set."""
    tiles = soup.select("ul.hub-tiles a.hub-tile[href]")
    v2_template(res, soup, url, hub=True)  # V2.1 X20 (also tile-less towns)
    if not tiles:
        return soup
    v2_hub_tiles(res, tiles)  # V2
    v2_hero_tiles(res, soup, url, tiles, ctx)  # V2.2 X21
    v2_page_checks(res, soup, url)  # V2
    seen, lis, queue = set(), [], [(urljoin(url, a["href"]), 1) for a in tiles]
    while queue:
        u, depth = queue.pop(0)
        if u in seen:
            continue
        seen.add(u)
        r, err = ctx["fetcher"].get_page(u)
        if r is None or r.status_code != 200:
            res.add("R8", "FAIL", f"hub sub-page fetch failed: {short(u, 60)} ({err or r.status_code})", "R8.hub-sub")
            continue
        sub = BeautifulSoup(r.text, PARSER)
        for li in sub.select("section.place-section ul.place-list > li"):
            if "/stay/" in urlparse(u).path:
                li["data-bj-stay"] = "1"  # STAY-FALLBACK: card came from a Stay sub-page
            elif "/day-to-day/" in urlparse(u).path:
                li["data-bj-sights"] = "1"  # day-to-day cards (town office, post office...) carry official_url but are not Dining
            lis.append(li)
        v2_page_checks(res, sub, u)  # V2
        v2_template(res, sub, u)  # V2.1 X20
        town = urlparse(url).path
        for a in sub.select("a[href]"):  # V2: crawl EVERY page under the town, no depth cap
            v = urljoin(u, a["href"]).split("#")[0].split("?")[0]
            if v.startswith(BASE) and urlparse(v).path.startswith(town) and v != url and v not in seen \
               and not re.search(r"\.(jpg|png|webp|svg|json|xml|pdf)$", v):
                queue.append((v, depth + 1))
    res.add("R8", "PASS", f"hub: {len(seen)} sub-pages fetched, {len(lis)} cards pooled", "R8.hub")
    groups = {"Stay": [], "Dining": [], "Sights": []}
    for li in lis:
        raw = str(li)
        if li.get("data-bj-sights"):
            groups["Sights"].append(li)
        elif re.search(r"sources: [^>]*(jalan_url|ikk?yu_url)=", raw) or li.get("data-bj-stay"):
            groups["Stay"].append(li)
        elif re.search(r"sources: [^>]*(tabelog_url|ta_url|osm_url|official_url)=", raw):
            groups["Dining"].append(li)
        else:
            groups["Sights"].append(li)
    def rank(li):
        m = re.search(r"#(\d+) ranked", li.get_text(" ", strip=True))
        return int(m.group(1)) if m else 10**9
    html = ""
    for t in ("Stay", "Dining", "Sights"):
        items = sorted(groups[t], key=rank) if t != "Sights" else groups[t]
        if items:
            html += f'<section class="place-section"><h2>{t}</h2><ul class="place-list">' + "".join(str(x) for x in items) + "</ul></section>"
    merged = BeautifulSoup(str(soup), PARSER)
    main = merged.find("main") or merged.body
    frag = BeautifulSoup(html, PARSER)
    for sec in list(frag.find_all("section", recursive=True)):
        main.append(sec)
    return merged


def run_page(url, page_type, ctx):
    res = Result()
    r, err = ctx["fetcher"].get_page(url)
    rec = {"url": url, "type": page_type}
    if r is None or r.status_code != 200:
        for k in RULES:
            if k == "R8":
                res.add(k, "FAIL", f"page fetch failed: {err or r.status_code}", "R8.page")
            else:
                res.skip(k, "page not fetched")
        rec.update(http=(r.status_code if r is not None else None), rules=finalize(res).rules, info={})
        return rec
    ctx["known_ok"].add(url)
    soup = BeautifulSoup(r.text, PARSER)
    if page_type == "municipality":
        for k in ("X10", "X13"):
            res.skip(k, "n/a on municipality page")
    nbytes = check_common(res, soup, r.text, url, page_type, ctx)
    if page_type == "home":
        info = check_home(res, soup, url, ctx)
    elif page_type == "prefecture":
        info = check_pref_index(res, soup, url, ctx)
    else:
        info = check_municipality(res, hub_merged_soup(res, soup, url, ctx), url, ctx)
    info["html_bytes"] = nbytes
    rec.update(http=200, info=info)
    rec["_res"] = res
    return rec


def post_process(records):
    """Cross-page checks (cover reuse / small cover files), then finalize."""
    by_key = defaultdict(list)
    for rec in records:
        info = rec.get("info") or {}
        if rec["type"] != "municipality" or not info.get("cover_src") or "_res" not in rec:
            continue
        ch = info.get("cover_head") or {}
        key = ch.get("etag") or info["cover_src"].split("/")[-1]
        by_key[key].append(rec)
        if info["cover_src"].split("/")[-1] != key:
            by_key[info["cover_src"].split("/")[-1]].append(rec)
        if ch.get("size") is not None and ch["size"] < 30000:
            rec["_res"].add("X6", "WARN", f"cover file only {ch['size']} bytes", "X6.small-file")
    flagged = set()
    for key, recs in by_key.items():
        towns = sorted({r["url"] for r in recs})
        if len(towns) > 1:
            for r in recs:
                if (id(r), tuple(towns)) in flagged:
                    continue
                flagged.add((id(r), tuple(towns)))
                others = [t.replace(BASE, "") for t in towns if t != r["url"]]
                r["_res"].add("X6", "FAIL", f"same cover photo used on {len(towns)} towns (also: {', '.join(others[:3])})", "X6.reused")
    for rec in records:
        if "_res" in rec:
            rec["rules"] = finalize(rec.pop("_res")).rules


def pref_munis(pref, ctx):
    inv = ctx.get("inventory")
    if inv is not None:
        return sorted(f"{BASE}/{p.replace('index.html', '')}" for p in inv if p.startswith(pref + "/"))
    url = f"{BASE}/{pref}/"
    r, _ = ctx["fetcher"].get_page(url)
    if r is None or r.status_code != 200:
        return []
    soup = BeautifulSoup(r.text, PARSER)
    out = []
    for a in (soup.find("main") or soup).find_all("a", href=True):
        u = urljoin(url, a["href"]).split("#")[0]
        if re.fullmatch(re.escape(url) + r"[a-z0-9-]+/", u):
            out.append(u)
    return list(OrderedDict.fromkeys(out))


def norm_url(u):
    if u.startswith("/"):
        u = BASE + u
    if not u.startswith("http"):
        u = BASE + "/" + u
    if not u.endswith("/") and not os.path.splitext(urlparse(u).path)[1]:
        u += "/"
    return u


def classify(u):
    p = urlparse(u).path.strip("/")
    if not p or p == "index.html":
        return "home"
    return "prefecture" if p.count("/") == 0 else "municipality"


def write_reports(records, meta, out_dir):
    counts = OrderedDict((k, Counter()) for k in RULES)
    for rec in records:
        for k, r in rec["rules"].items():
            counts[k][r["status"]] += 1
    summary = {k: dict(v) for k, v in counts.items()}
    any_fail = any(r["status"] == "FAIL" for rec in records for r in rec["rules"].values())
    data = {"meta": meta, "rules": RULES, "summary": summary, "overall": "FAIL" if any_fail else "PASS", "pages": records}
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "report.json"), "w") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1)
    L = ["# bokenjapan live quality report\n",
         f"- Run: {meta['started']} → {meta['finished']} (Asia/Tokyo)  ·  overall: **{data['overall']}**",
         f"- Pages checked: {len(records)} ({', '.join(f'{k}: {v}' for k, v in Counter(r['type'] for r in records).items())})",
         f"- Requests: {meta['requests']}  ·  args: `{meta['argv']}`\n",
         "## Summary per rule (pages)\n", "| Rule | Description | PASS | WARN | FAIL | SKIP |", "|---|---|---|---|---|---|"]
    for k, d in RULES.items():
        c = counts[k]
        L.append(f"| {k} | {d} | {c['PASS']} | {c['WARN']} | {c['FAIL']} | {c['SKIP']} |")
    L += ["\n## Page matrix\n", "| Page | Type | " + " | ".join(RULES) + " | Dining (photos) | Stay (photos) |",
          "|---|---|" + "---|" * len(RULES) + "---|---|"]
    icon = {"PASS": "PASS", "WARN": "WARN", "FAIL": "**FAIL**", "SKIP": "–"}
    for rec in records:
        info = rec.get("info") or {}
        d = f"{info['dining']} ({info['dining_photos']})" if "dining" in info else ""
        s = f"{info['stay']} ({info['stay_photos']})" if "stay" in info else ""
        L.append(f"| [{urlparse(rec['url']).path}]({rec['url']}) | {rec['type']} | " +
                 " | ".join(icon[rec['rules'][k]['status']] for k in RULES) + f" | {d} | {s} |")
    L.append("\n## Findings (FAIL and WARN)\n")
    for rec in records:
        bad = [(k, f) for k, r in rec["rules"].items() for f in r["findings"] if f["sev"] in ("FAIL", "WARN")]
        if not bad:
            continue
        L.append(f"### {urlparse(rec['url']).path}\n")
        for k, f in sorted(bad, key=lambda x: (-SEV[x[1]['sev']], list(RULES).index(x[0]))):
            L.append(f"- **{f['sev']}** {k}: {f['msg']}")
        L.append("")
    L.append("## Not machine-checked (needs human / second-model review)\n")
    L += [f"- {x}" for x in meta["not_checked"]]
    with open(os.path.join(out_dir, "report.md"), "w") as fh:
        fh.write("\n".join(L) + "\n")
    return data


NOT_CHECKED = [
    "R1/R2 'no invented entries' and rank fidelity: metadata URLs are validated (format, prefecture, order, duplicates) but Tabelog/TripAdvisor/Ikkyu/Jalan are not opened.",
    "R2 whether lodging truly exists locally when Stay=0 (WARN for human).",
    "R3 photo shows the actual store (not chain/brand/stock/AI) and official-site-first was honoured: visual review.",
    "R4 line 4 is sourced and accurate (checker flags missing/Japanese/label/boilerplate/no desc-source metadata only).",
    "R5 card link goes to the *right* facility (checker validates host and HEADs a random sample).",
    "R7 visual match to Ōhira; external links beyond the per-page sample.",
]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--urls", nargs="*", default=[])
    ap.add_argument("--pref", action="append", default=[], help="'slug' = all towns, 'slug:N' = N random")
    ap.add_argument("--sample", type=int, default=0)
    ap.add_argument("--sample-exclude", default="")
    ap.add_argument("--inventory", default=None, help="gh-pages file list (pref/slug/index.html per line)")
    ap.add_argument("--no-home", action="store_true")
    ap.add_argument("--check-pref-index", action="store_true")
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--delay", type=float, default=0.4)
    ap.add_argument("--max-pages", type=int, default=0, help="0 = unlimited (V2)")
    ap.add_argument("--max-images", type=int, default=1500)
    ap.add_argument("--max-links", type=int, default=600)
    ap.add_argument("--images-per-page", type=int, default=60)
    ap.add_argument("--deep-images-per-page", type=int, default=2)
    ap.add_argument("--ext-links-per-page", type=int, default=3)
    ap.add_argument("--card-links-per-section", type=int, default=2)
    ap.add_argument("--html-cache", default=None)
    ap.add_argument("--out-dir", default=os.path.dirname(os.path.abspath(__file__)))
    a = ap.parse_args()

    seed = a.seed if a.seed is not None else int(time.time())
    rnd = random.Random(seed)
    budget = Budget(a.max_pages or None, a.max_images, a.max_links)
    f = Fetcher(budget, a.delay)
    if a.html_cache:
        os.makedirs(a.html_cache, exist_ok=True)
        f.cache_dir = a.html_cache
    inventory = None
    if a.inventory:
        inventory = [l.strip() for l in open(a.inventory) if l.strip().endswith("/index.html") and l.strip().count("/") == 2 and "/photo-credits/" not in "/" + l.strip()]
    ctx = {"fetcher": f, "known_ok": set(), "images_per_page": a.images_per_page, "rnd": rnd,
           "deep_images_per_page": a.deep_images_per_page, "ext_links_per_page": a.ext_links_per_page,
           "card_links_per_section": a.card_links_per_section, "inventory": inventory, "maps": {},
           "prefs": sorted({x.split(":")[0] for x in a.pref})}
    started = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    css_r, _ = f.get_page(BASE + "/styles.css")
    ctx["css"] = css_r.text if css_r is not None and css_r.status_code == 200 else ""
    ctx["hidden_classes"] = hidden_by_css_classes(ctx["css"])
    m = re.search(r"\.foot-disclaimer\s*\{[^}]*font-size\s*:\s*([\d.]+)px", ctx["css"])
    ctx["disclaimer_px"] = float(m.group(1)) if m else None

    muni_t, pref_t, named = [], [], set()
    for spec in a.pref:
        slug, _, n = spec.partition(":")
        named.add(slug)
        munis = pref_munis(slug, ctx)
        if not munis:
            print(f"warn: no municipality pages found for {slug}", file=sys.stderr)
        pick = munis if not n or n == "all" else rnd.sample(munis, min(int(n), len(munis)))
        if a.check_pref_index:
            pref_t.append((f"{BASE}/{slug}/", "prefecture"))
        muni_t += [(u, "municipality") for u in pick]
    if a.sample:
        hr, _ = f.get_page(BASE + "/")
        prefs = []
        if hr is not None:
            hs = BeautifulSoup(hr.text, PARSER)
            prefs = sorted({x["href"].strip("/") for x in hs.find_all("a", href=True) if re.fullmatch(r"/[a-z]+/", x["href"])})
        excl = named | set(filter(None, a.sample_exclude.split(",")))
        pool = [p for p in prefs if p not in excl]
        rnd.shuffle(pool)
        got = 0
        for p in pool:
            if got >= a.sample:
                break
            munis = pref_munis(p, ctx)
            if munis:
                if a.check_pref_index:
                    pref_t.append((f"{BASE}/{p}/", "prefecture"))
                muni_t.append((rnd.choice(munis), "municipality"))
                got += 1
    extra = [(norm_url(u), classify(norm_url(u))) for u in a.urls]
    targets = ([] if a.no_home else [(BASE + "/", "home")]) + muni_t + [t for t in extra if t[1] == "municipality"] + \
        pref_t + [t for t in extra if t[1] != "municipality"]
    targets = list(OrderedDict.fromkeys(targets))
    if not targets:
        ap.error("nothing to check")
    records = []
    for i, (u, t) in enumerate(targets, 1):
        rec = run_page(u, t, ctx)
        st = Counter(r["status"] for r in (rec.get("_res").rules if rec.get("_res") else rec["rules"]).values())
        print(f"[{i}/{len(targets)}] {t:12s} {urlparse(u).path:40s} FAIL={st['FAIL']} WARN={st['WARN']} PASS={st['PASS']}", flush=True)
        records.append(rec)
    post_process(records)
    meta = {"started": started, "finished": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "seed": seed,
            "argv": " ".join(sys.argv[1:]), "requests": dict(budget.used), "base": BASE, "not_checked": NOT_CHECKED}
    data = write_reports(records, meta, a.out_dir)
    print(f"\noverall {data['overall']} · report: {os.path.join(a.out_dir, 'report.md')}")
    for k, c in data["summary"].items():
        print(f"  {k}: " + " ".join(f"{s}={c.get(s, 0)}" for s in ("PASS", "WARN", "FAIL", "SKIP")))
    sys.exit(1 if data["overall"] == "FAIL" else 0)


if __name__ == "__main__":
    main()
