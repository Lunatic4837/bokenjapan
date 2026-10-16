#!/usr/bin/env python3
"""Repair garbled station names in stay descriptions ("Jrgobo Station" -> "JR Gobo Station").

Cause: the stay generator (fn_lib.access_en) captured the text before 駅 including marketing
copy, then romanised and .title()-cased it, so "令和6年4月開業）JR御坊駅" became
"Wa6Nen4Gatsukaigyo)Jrgobo Station". The helper is fixed at source; this script repairs pages
already published. Deterministic and idempotent. Names it cannot repair confidently
(digits or marketing words left in the name) lose the whole "; N-minute walk from X Station" clause.

  python3 scripts/fix_station_names.py --root . [--check] [--files list.txt] [--report out.tsv]
"""
import argparse, html, os, re, sys

TOK = r"(?:&#?\w+;|[^\s;\"<>&]|&(?!#?\w+;))+?"
RX = re.compile(r"(?P<pre>; )?(?P<n>\d+)-minute (?P<mode>walk|drive|bus ride|taxi ride) from (?P<tok>" + TOK + r") (?P<kind>Station|IC)\b")
DELIM = re.compile(r"[)!>~(:&,\\]")
JUNK = re.compile(r"bbq|hotel|muryo|sabisu|kuruma|kara$|made$|kangei|opun|kaigyo", re.I)
APOS = re.compile(r"&#x27;|&#39;|\\'")


def needs_fix(t):
    return bool(re.match(r"Jr(?=[a-z])", t) or re.search(r"[0-9!>~()\\&,]", t))


def clean(tok):
    """Return repaired name or None if it cannot be repaired."""
    t = html.unescape(tok)
    jr = False
    m = re.match(r"^(.*?)\(([^()]+)\)$", t)
    if m:
        jr = bool(re.search(r"(?:^|[)!>~:&,\\])Jr(?=[a-z])", m.group(1)))
        t = m.group(2)
    t = DELIM.split(t)[-1]
    if re.match(r"Jr(?=[a-z])", t):
        jr, t = True, t[2:]
    t = re.sub(r"ekikara\d*$", "", t)
    if not t or re.search(r"[0-9]", t) or JUNK.search(t):
        return None
    t = re.sub(r"(^|-)([a-z])", lambda x: x.group(1) + x.group(2).upper(), t)
    t = re.sub(r"'([A-Z])", lambda x: "'" + x.group(1).lower(), t)
    return ("JR " if jr else "") + t


def fix_text(s, log=None):
    def sub(m):
        tok = m.group("tok")
        if not needs_fix(tok):
            return m.group(0)
        new = clean(tok)
        if new is None:
            if m.group("pre"):
                if log is not None: log.append(("dropped", tok, ""))
                return ""
            if log is not None: log.append(("unfixed", tok, ""))
            return m.group(0)
        if log is not None: log.append(("fixed", tok, new))
        return f"{m.group('pre') or ''}{m.group('n')}-minute {m.group('mode')} from {new} {m.group('kind')}"
    return RX.sub(sub, s)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--files")
    ap.add_argument("--report")
    ap.add_argument("--skip", default="tokyo")
    a = ap.parse_args()
    skip = set(x for x in a.skip.split(",") if x)
    if a.files:
        paths = [os.path.join(a.root, l.strip()) for l in open(a.files) if l.strip()]
    else:
        paths = []
        for r, ds, fs in os.walk(a.root):
            rel = os.path.relpath(r, a.root).split(os.sep)
            if rel[0] in skip or rel[0] == ".git":
                ds[:] = []
                continue
            if "index.html" in fs and (rel[-1] == "stay" or "stay" in rel):
                paths.append(os.path.join(r, "index.html"))
    changed = 0; rows = []
    for p in paths:
        if not os.path.exists(p):
            continue
        s = open(p, encoding="utf8").read()
        log = []
        n = fix_text(s, log)
        for k, a_, b_ in log:
            rows.append((os.path.relpath(p, a.root), k, a_, b_))
        if n != s:
            changed += 1
            if not a.check:
                open(p, "w", encoding="utf8").write(n)
    if a.report:
        with open(a.report, "w", encoding="utf8") as f:
            for r in rows: f.write("\t".join(r) + "\n")
    kinds = {}
    for r in rows: kinds[r[1]] = kinds.get(r[1], 0) + 1
    print(f"files scanned {len(paths)}, changed {changed}, actions {kinds}")
    return 1 if (a.check and changed) else 0


if __name__ == "__main__":
    sys.exit(main())
