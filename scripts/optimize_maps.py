#!/usr/bin/env python3
"""Shrink <pref>/_map.svg (and inline <svg class="pref-map"> in hub index.html): absolute M/L/Z polygons at
2 decimals -> 1 decimal (--dec N), relative 'l' deltas, duplicate points dropped (rings that collapse to <3 points dropped).
0.1px at the 720px map width is invisible: standalone _map.svg renders pixel-identical; inline hub maps differ by
anti-aliasing only (<=0.02% of pixels); transfer drops ~80-90%.
Idempotent: files already carrying data-opt="1" are skipped.
Usage: optimize_maps.py [--root DIR] [--check]   (--check: report only, write nothing)"""
import argparse, glob, os, re

NUM = re.compile(r'-?\d+(?:\.\d+)?')
RING = re.compile(r'M([^M]*?)Z')

DEC = 1   # decimals kept (--dec N); 1 = 0.1px at the 720px map width

def fmt(v):
    s = ('%.*f' % (DEC, v)).rstrip('0').rstrip('.')
    if s in ('-0', ''): s = '0'
    if s.startswith('0.'): s = s[1:]
    elif s.startswith('-0.'): s = '-' + s[2:]
    return s

def ring(body):
    n = [float(x) for x in NUM.findall(body)]
    pts = []
    for x, y in zip(n[0::2], n[1::2]):
        p = (round(x, DEC), round(y, DEC))
        if not pts or p != pts[-1]: pts.append(p)
    if len(pts) > 1 and pts[0] == pts[-1]: pts.pop()
    if len(pts) < 3: return ''
    s = ''
    for a, b in zip(pts, pts[1:]):
        dx, dy = fmt(round(b[0] - a[0], DEC)), fmt(round(b[1] - a[1], DEC))
        t = dx + ('' if dy.startswith('-') else ' ') + dy
        s += (' ' if s and not t.startswith('-') else '') + t
    return 'M%s %sl%sz' % (fmt(pts[0][0]), fmt(pts[0][1]), s)

def opt_d(m):
    return 'd="' + ''.join(ring(r) for r in RING.findall(m.group(1))) + '"'

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', default='.'); ap.add_argument('--check', action='store_true')
    ap.add_argument('--dec', type=int, default=1, help='decimals to keep (default 1)')
    a = ap.parse_args()
    global DEC; DEC = a.dec
    files = sorted(glob.glob(os.path.join(a.root, '*', '_map.svg')))
    files += sorted(glob.glob(os.path.join(a.root, '*', 'index.html')))  # hubs with an inline map
    tb = ta = n = 0
    for f in files:
        s = open(f, encoding='utf-8').read()
        if 'data-opt="1"' in s or '<svg class="pref-map"' not in s: continue
        o = re.sub(r'd="(M[^"]*)"', opt_d, s)
        o = o.replace('<svg class="pref-map"', '<svg class="pref-map" data-opt="1"', 1)
        tb += len(s); ta += len(o); n += 1
        if not a.check: open(f, 'w', encoding='utf-8').write(o)
    print('%d files: %d -> %d bytes (%.0f%%)' % (n, tb, ta, 100.0 * ta / tb if tb else 0))

if __name__ == '__main__': main()
