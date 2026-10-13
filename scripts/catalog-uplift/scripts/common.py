#!/usr/bin/env python3
from __future__ import annotations
import json, os, subprocess, time
from pathlib import Path

BASE = Path('/workspace/p1/data/catalog-uplift')  # runtime data/raw/out
REPO_HUBS = Path(__file__).resolve().parents[1] / 'hubs'
HUBS = BASE / 'hubs' / 'aomori-hub-codes.json'  # default
RAW = BASE / 'raw'
OUT = BASE / 'out'
# Site root to render into. Set BJ_SITE_ROOT to YOUR worktree; never render into another
# worker's checkout (CoS fix 2026-10-13).
CUTOVER = Path(os.environ.get('BJ_SITE_ROOT', '/workspace/p1/bokenjapan-cutover'))
MEDIA = CUTOVER / 'media'
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'

def load_hubs(pref: str | None = None) -> dict:
    name = 'aomori-hub-codes.json' if not pref else f'{pref}-hub-codes.json'
    if pref == 'miyagi':
        name = 'miyagi-hub-codes.json'
    for root in (Path(__file__).resolve().parents[1] / 'hubs', BASE / 'hubs'):
        path = root / name
        if path.exists():
            return json.loads(path.read_text(encoding='utf-8'))
    path = BASE / 'hubs' / name
    return json.loads(path.read_text(encoding='utf-8'))

def save_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')

def sleep_polite(sec: float = 0.25) -> None:
    time.sleep(sec)

def curl(url: str, dest: Path | None = None, timeout: int = 30, headers: list | None = None) -> tuple[int, str]:
    dest = dest or (RAW / '_tmp.html')
    dest.parent.mkdir(parents=True, exist_ok=True)
    cmd = ['curl', '-sL', '-A', UA, '-o', str(dest), '-w', '%{http_code}',
           '--max-time', str(timeout), '-H', 'Accept-Language: ja,en;q=0.8']
    if headers:
        for h in headers:
            cmd.extend(['-H', h])
    cmd.append(url)
    r = subprocess.run(cmd, capture_output=True, text=True)
    code = int((r.stdout or '0').strip() or '0')
    html = dest.read_text(encoding='utf-8', errors='replace') if dest.exists() else ''
    return code, html

def disk_avail_gib() -> float:
    import os
    st = os.statvfs('/workspace/p1')
    return (st.f_bavail * st.f_frsize) / (1024 ** 3)

def clean_raw_slug(slug: str) -> None:
    """Drop fat raw HTML for one slug after hubs are built (disk lean)."""
    d = RAW / slug
    if d.is_dir():
        import shutil
        shutil.rmtree(d, ignore_errors=True)
    # also clear orphan tmp
    for pat in ('_tmp.html', f'{slug}.html'):
        f = RAW / pat
        if f.exists():
            f.unlink(missing_ok=True)

