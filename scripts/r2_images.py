"""Rewrite in-scope image URLs onto the Cloudflare R2 allow-list.

The public host lives in ``R2_BASE`` inside ``build-pages-site.py``. This module
takes that string as an argument so the host is not copied here.
"""
from __future__ import annotations

import csv
import hashlib
import re
from pathlib import Path

from PIL import Image

Image.MAX_IMAGE_PIXELS = None

IMAGE_EXT_RE = re.compile(
    r"\.(?:jpe?g|png|webp|gif|svg|ico)(?:[?#].*)?$",
    re.I,
)
ATTR_RE = re.compile(
    r"""(?P<attr>\b(?:src|srcset|data-src|href|content|poster))"""
    r"""(?P<eq>\s*=\s*)(?P<q>["'])(?P<val>.*?)(?P=q)""",
    re.I | re.S,
)
CSS_URL_RE = re.compile(
    r"""url\(\s*(?P<q>['"]?)(?P<val>[^'")]+?)(?P=q)\s*\)""",
    re.I,
)
IMG_RE = re.compile(r"<img\b[^>]*>", re.I)
THUMB_RE = re.compile(
    r"<img\b(?=[^>]*\bclass\s*=\s*[\"'][^\"']*\bthumb\b)[^>]*>",
    re.I,
)
SRC_RE = re.compile(r"""\bsrc\s*=\s*(["'])(.*?)\1""", re.I | re.S)
SITE_ORIGINS = (
    "https://bokenjapan.com/",
    "http://bokenjapan.com/",
)

_SIZES: dict[str, tuple[int, int] | None] = {}

# Byte-identical copies of the TripAdvisor logo PNG and the Tabelog
# "NO PHOTO" GIF. Many are stored under a .jpg name. Identified by hash,
# not by filename. Do not publish either as a facility photo.
TA_LOGO_SHA256 = "a3d03f490a85b1e50b66bafb3ecb95b7651209ab6ba89ded90926cb1d12abc2e"
TABELOG_NO_PHOTO_SHA256 = "a59e570e505113b85a0fa4e608aefdc99e41f6da3e3de25c6b478637d88e3ef4"
PLACEHOLDER_SHA256 = frozenset({TA_LOGO_SHA256, TABELOG_NO_PHOTO_SHA256})
# Same-size filter so the scan does not hash the rest of media/.
PLACEHOLDER_SIZES = frozenset({30229, 3027})


def load_manifest_keys(path: Path) -> set[str]:
    keys: set[str] = set()
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            key = (row.get("key") or "").strip()
            if key:
                keys.add(key)
    return keys


def load_missing_keys(path: Path) -> set[str]:
    keys: set[str] = set()
    with path.open(encoding="utf-8") as handle:
        next(handle, None)
        for line in handle:
            key = line.split("\t", 1)[0].strip()
            if key:
                keys.add(key)
    return keys


def looks_like_image_ref(value: str) -> bool:
    token = value.strip().split()[0] if value.strip() else ""
    if not token or token.startswith("#") or token.startswith("data:"):
        return False
    path = token.split("?", 1)[0].split("#", 1)[0]
    return bool(IMAGE_EXT_RE.search(path))


def resolve_key(value: str, html_path: Path, root: Path, r2_base: str) -> str | None:
    """Map an image URL to a repo-relative key, or None when it is not a file ref."""
    raw = value.strip()
    if not raw or raw.startswith("#") or raw.startswith("data:"):
        return None
    if raw.startswith(r2_base + "/"):
        return raw[len(r2_base) + 1 :].split("?", 1)[0].split("#", 1)[0]
    if "://" in raw:
        for origin in SITE_ORIGINS:
            if raw.startswith(origin):
                return raw[len(origin) :].split("?", 1)[0].split("#", 1)[0].lstrip("/")
        return None
    path = raw.split("?", 1)[0].split("#", 1)[0]
    if not path or path.startswith("//"):
        return None
    if path.startswith("/"):
        return path.lstrip("/")
    try:
        resolved = (html_path.parent / path).resolve()
        return resolved.relative_to(root.resolve()).as_posix()
    except (ValueError, OSError):
        return None


def r2_url(r2_base: str, key: str) -> str:
    return f"{r2_base}/{key}"


def _rewrite_one(
    value: str,
    html_path: Path,
    root: Path,
    r2_base: str,
    manifest: set[str],
) -> str:
    key = resolve_key(value, html_path, root, r2_base)
    if key and key in manifest:
        return r2_url(r2_base, key)
    return value


def _rewrite_srcset(
    value: str,
    html_path: Path,
    root: Path,
    r2_base: str,
    manifest: set[str],
) -> str:
    parts: list[str] = []
    for piece in value.split(","):
        stripped = piece.strip()
        if not stripped:
            parts.append(piece)
            continue
        bits = stripped.split()
        url = _rewrite_one(bits[0], html_path, root, r2_base, manifest)
        parts.append(" ".join([url, *bits[1:]]))
    return ", ".join(parts)


def load_placeholder_names(media_dir: Path) -> set[str]:
    """Basenames in media/ whose bytes match the TA logo or Tabelog NO PHOTO."""
    names: set[str] = set()
    if not media_dir.is_dir():
        return names
    for path in media_dir.iterdir():
        if not path.is_file():
            continue
        try:
            size = path.stat().st_size
        except OSError:
            continue
        if size not in PLACEHOLDER_SIZES:
            continue
        try:
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError:
            continue
        if digest in PLACEHOLDER_SHA256:
            names.add(path.name)
    return names


def image_size(root: Path, key: str) -> tuple[int, int] | None:
    path = (root / key)
    cache_key = str(path)
    if cache_key in _SIZES:
        return _SIZES[cache_key]
    if not path.is_file():
        _SIZES[cache_key] = None
        return None
    try:
        with Image.open(path) as im:
            width, height = im.size
        _SIZES[cache_key] = (width, height) if width > 0 and height > 0 else None
    except Exception:
        _SIZES[cache_key] = None
    return _SIZES[cache_key]


def _strip_placeholder_imgs(
    text: str,
    html_path: Path,
    root: Path,
    r2_base: str,
    placeholder_names: set[str],
) -> tuple[str, int]:
    """Drop imgs that are the TA logo or the Tabelog NO PHOTO file.

    The card and its link stay. A hidden comment marks the missing photo.
    These files must not be rewritten to an R2 URL.
    """
    if not placeholder_names:
        return text, 0
    removed = 0

    def repl(match: re.Match) -> str:
        nonlocal removed
        tag = match.group(0)
        src = SRC_RE.search(tag)
        if not src:
            return tag
        key = resolve_key(src.group(2), html_path, root, r2_base)
        name = Path(key).name if key else Path(src.group(2).split("?", 1)[0]).name
        if name not in placeholder_names:
            return tag
        removed += 1
        return "<!-- photo-missing -->"

    return IMG_RE.sub(repl, text), removed


def _strip_missing_imgs(
    text: str,
    html_path: Path,
    root: Path,
    r2_base: str,
    missing: set[str],
) -> tuple[str, int]:
    removed = 0

    def repl(match: re.Match) -> str:
        nonlocal removed
        tag = match.group(0)
        src = SRC_RE.search(tag)
        if not src:
            return tag
        key = resolve_key(src.group(2), html_path, root, r2_base)
        if key not in missing:
            return tag
        removed += 1
        return "<!-- photo-missing -->"

    return IMG_RE.sub(repl, text), removed


def _rewrite_attrs(
    text: str,
    html_path: Path,
    root: Path,
    r2_base: str,
    manifest: set[str],
) -> tuple[str, int]:
    rewritten = 0

    def repl(match: re.Match) -> str:
        nonlocal rewritten
        attr = match.group("attr")
        value = match.group("val")
        if attr.lower() == "srcset":
            new = _rewrite_srcset(value, html_path, root, r2_base, manifest)
        elif looks_like_image_ref(value):
            new = _rewrite_one(value, html_path, root, r2_base, manifest)
        else:
            return match.group(0)
        if new != value:
            rewritten += 1
        if new == value:
            return match.group(0)
        return f"{attr}{match.group('eq')}{match.group('q')}{new}{match.group('q')}"

    text = ATTR_RE.sub(repl, text)

    def css_repl(match: re.Match) -> str:
        nonlocal rewritten
        value = match.group("val").strip()
        if not looks_like_image_ref(value):
            return match.group(0)
        new = _rewrite_one(value, html_path, root, r2_base, manifest)
        if new == value:
            return match.group(0)
        rewritten += 1
        quote = match.group("q")
        return f"url({quote}{new}{quote})"

    text = CSS_URL_RE.sub(css_repl, text)
    return text, rewritten


def _augment_thumbs(
    text: str,
    html_path: Path,
    root: Path,
    r2_base: str,
) -> tuple[str, int]:
    updated = 0

    def repl(match: re.Match) -> str:
        nonlocal updated
        tag = match.group(0)
        if not tag.endswith(">"):
            return tag
        new = tag
        if not re.search(r"\bloading\s*=", new, re.I):
            new = new[:-1] + ' loading="lazy">'
        if not re.search(r"\bdecoding\s*=", new, re.I):
            new = new[:-1] + ' decoding="async">'
        has_width = re.search(r"\bwidth\s*=", new, re.I)
        has_height = re.search(r"\bheight\s*=", new, re.I)
        if not has_width and not has_height:
            src = SRC_RE.search(new)
            key = (
                resolve_key(src.group(2), html_path, root, r2_base) if src else None
            )
            size = image_size(root, key) if key else None
            if size:
                width, height = size
                new = new[:-1] + f' width="{width}" height="{height}">'
        if new != tag:
            updated += 1
        return new

    return THUMB_RE.sub(repl, text), updated


def rewrite_page(
    text: str,
    html_path: Path,
    root: Path,
    r2_base: str,
    manifest: set[str],
    missing: set[str],
    placeholder_names: set[str] | None = None,
) -> tuple[str, dict[str, int]]:
    """Rewrite one HTML document. A second call on the result is a no-op."""
    text, removed = _strip_missing_imgs(text, html_path, root, r2_base, missing)
    text, placeholders = _strip_placeholder_imgs(
        text, html_path, root, r2_base, placeholder_names or set()
    )
    text, rewritten = _rewrite_attrs(text, html_path, root, r2_base, manifest)
    text, thumbs = _augment_thumbs(text, html_path, root, r2_base)
    return text, {
        "removed": removed,
        "placeholders": placeholders,
        "rewritten": rewritten,
        "thumbs": thumbs,
    }


def local_media_names(text: str, r2_base: str) -> set[str]:
    """Basenames of media/ files that are still local (not R2 URLs)."""
    cleaned = re.sub(re.escape(r2_base) + r"/[^\s\"')]+", " ", text)
    names: set[str] = set()
    for match in re.finditer(r"""media/([^"')?#\s]+)""", cleaned):
        names.add(Path(match.group(1)).name)
    return names


def inside_absolute_url(text: str, start: int) -> bool:
    look = text[max(0, start - 400) : start]
    return re.search(r"https?:[^\s\"'()]*$", look) is not None
