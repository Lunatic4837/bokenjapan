#!/usr/bin/env python3
"""Build photos-5pref/no-photo-found.csv from origin/gh-pages Dining/Stay cards.

Streams `git archive origin/gh-pages` and emits one CSV row per place-list <li>
that has a photo_search comment/record and no <img class="thumb">.

Columns match the historical no-photo-found.csv header used by quality/check_live.py:
  card_key, name_ja, urls_tried, reason, group, card_name_on_page, listing_url

card_key page portion is pref/slug (first two path segments), matching check_live's
page_key = "/".join(urlparse(url).path.strip("/").split("/")[:2]).
"""
from __future__ import annotations

import csv
import html as htmlmod
import json
import os
import re
import subprocess
import sys
import tarfile
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path

REPO = Path(os.environ.get("BJ_GH_PAGES_REPO", "/workspace/p1/gh-pages-pub"))
REF = os.environ.get("BJ_GH_PAGES_REF", "origin/gh-pages")
OUT = Path(os.environ.get("BJ_NOPHOTO_OUT", "/workspace/p1/photos-5pref/no-photo-found.csv"))

HEADER = [
    "card_key",
    "name_ja",
    "urls_tried",
    "reason",
    "group",
    "card_name_on_page",
    "listing_url",
]

PATH_RE = re.compile(
    r"^(?P<pref>[a-z0-9-]+)/(?P<slug>[a-z0-9-]+)/(?P<section>eat|stay)(?:/|$)"
)
LI_RE = re.compile(r"<li\b[^>]*>(.*?)</li>", re.I | re.S)
THUMB_RE = re.compile(r"<img\b[^>]*\bclass\s*=\s*[\"'][^\"']*\bthumb\b", re.I)
PHOTO_SEARCH_RE = re.compile(r"<!--\s*photo_search:\s*(.*?)-->", re.I | re.S)
HREF_RE = re.compile(r"<a\b[^>]*\bhref\s*=\s*[\"']([^\"']+)[\"']", re.I)
NAME_RE = re.compile(
    r"<p\b[^>]*\bclass\s*=\s*[\"'][^\"']*\bplace-name\b[^\"']*[\"'][^>]*>(.*?)</p>",
    re.I | re.S,
)
TAG_RE = re.compile(r"<[^>]+>")


def kind_for(section: str) -> str:
    return "Dining" if section == "eat" else "Stay"


def clean_text(s: str) -> str:
    s = TAG_RE.sub("", s)
    s = htmlmod.unescape(s)
    return re.sub(r"\s+", " ", s).strip()


def urls_tried_from_comment(body: str) -> tuple[str, str]:
    """Return (urls_tried, reason) from photo_search comment body."""
    body = body.strip()
    if body.startswith("{"):
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            return body, "no usable photo after photo_search"
        tried = data.get("tried") or []
        notes = data.get("notes") or {}
        parts = []
        if isinstance(tried, list):
            parts.append("tried:" + ",".join(str(x) for x in tried))
        if isinstance(notes, dict):
            for k, v in notes.items():
                parts.append(f"{k}:{v}")
        result = data.get("result")
        if result is None:
            reason = "no usable photo after photo_search (result=null)"
        else:
            reason = f"no usable photo after photo_search (result={result!r})"
        return " | ".join(parts) if parts else body, reason
    # free-text drop / pending notes
    return body, "no usable photo after photo_search"


def interesting_path(name: str) -> re.Match | None:
    if not name.endswith("index.html"):
        return None
    # skip non-facility sections
    return PATH_RE.match(name)


def parse_li(li_html: str) -> dict | None:
    if not PHOTO_SEARCH_RE.search(li_html):
        return None
    if THUMB_RE.search(li_html):
        return None
    m = PHOTO_SEARCH_RE.search(li_html)
    urls_tried, reason = urls_tried_from_comment(m.group(1))
    href_m = HREF_RE.search(li_html)
    listing_url = href_m.group(1).strip() if href_m else ""
    name_m = NAME_RE.search(li_html)
    name = clean_text(name_m.group(1)) if name_m else ""
    if not name and not listing_url:
        return None
    return {
        "name_ja": name,
        "card_name_on_page": name,
        "listing_url": listing_url,
        "urls_tried": urls_tried,
        "reason": reason,
        "group": "A",
    }


def stream_archive(repo: Path, ref: str):
    cmd = ["git", "-C", str(repo), "archive", ref]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert proc.stdout is not None
    try:
        with tarfile.open(fileobj=proc.stdout, mode="r|") as tar:
            for member in tar:
                if not member.isfile():
                    continue
                m = interesting_path(member.name)
                if not m:
                    continue
                f = tar.extractfile(member)
                if f is None:
                    continue
                raw = f.read()
                try:
                    text = raw.decode("utf-8", errors="replace")
                except Exception:
                    continue
                yield member.name, m, text
    finally:
        proc.stdout.close()
        err = proc.stderr.read().decode("utf-8", errors="replace") if proc.stderr else ""
        rc = proc.wait()
        if rc != 0:
            raise SystemExit(f"git archive failed ({rc}): {err[:500]}")


def main() -> int:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT.with_suffix(OUT.suffix + ".tmp")
    per_pref: Counter[str] = Counter()
    seq: Counter[str] = Counter()  # key = page|kind
    n_files = 0
    n_rows = 0

    with tmp.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=HEADER, lineterminator="\n")
        w.writeheader()
        for path, m, text in stream_archive(REPO, REF):
            n_files += 1
            pref = m.group("pref")
            slug = m.group("slug")
            section = m.group("section")
            kind = kind_for(section)
            page = f"{pref}/{slug}"
            sk = f"{page}|{kind}"
            for li_m in LI_RE.finditer(text):
                row = parse_li(li_m.group(1))
                if not row:
                    continue
                seq[sk] += 1
                row["card_key"] = f"{sk}|{seq[sk]}"
                w.writerow(row)
                per_pref[pref] += 1
                n_rows += 1
            if n_files % 500 == 0:
                print(f"... files={n_files} rows={n_rows}", file=sys.stderr)

    os.replace(tmp, OUT)
    print(f"Wrote {OUT} rows={n_rows} files_scanned={n_files}", file=sys.stderr)
    for pref, n in sorted(per_pref.items()):
        print(f"{pref}: {n}")
    print(f"TOTAL: {n_rows}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
