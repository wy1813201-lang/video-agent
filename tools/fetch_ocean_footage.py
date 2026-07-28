#!/usr/bin/env python3
"""Fetch and normalize a curated set of openly licensed marine videos."""

from __future__ import annotations

import html
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import requests

API = "https://commons.wikimedia.org/w/api.php"
OUT = Path("ocean-footage")
RAW = OUT / "raw"
CLIPS = OUT / "clips"
HEADERS = {"User-Agent": "HyperFramesOceanFootage/1.1 (open-media editing test)"}
MAX_SOURCE_BYTES = 450 * 1024 * 1024
VIDEO_MIMES = {"video/webm", "video/ogg", "video/mp4", "application/ogg"}

FILES = [
    ("File:Sea turtle in North Sulawesi.webm", "sea-turtle"),
    ("File:Tropical Fish Banner Fish on Coral Reef.webm", "coral-fish"),
    ("File:Shark diving.webm", "reef-shark"),
    ("File:Wk215-deep-sea-octopuses.webm", "octopus-garden"),
    ("File:Jellyfish- 2016 Deepwater Exploration of the Marianas.webm", "deep-jellyfish"),
    ("File:Sea Nettle.webm", "sea-nettle"),
    ("File:Coral Reef Art.webm", "coral-conservation"),
    ("File:Underwater Videos.webm", "underwater-life"),
]

ALLOWED = ("public domain", "cc0", "cc by", "cc-by", "attribution", "share alike")
DENIED = ("noncommercial", "no derivatives", "cc by-nc", "cc by-nd")


def clean(value: Any) -> str:
    if isinstance(value, dict):
        value = value.get("value", "")
    text = html.unescape(str(value or ""))
    text = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"\s+", " ", text).strip()


def fetch_pages() -> dict[str, dict[str, Any]]:
    params = {
        "action": "query",
        "format": "json",
        "formatversion": 2,
        "titles": "|".join(title for title, _ in FILES),
        "prop": "imageinfo",
        "iiprop": "url|mime|size|extmetadata",
    }
    response = requests.get(API, params=params, headers=HEADERS, timeout=60)
    response.raise_for_status()
    pages = response.json().get("query", {}).get("pages", [])
    return {str(page.get("title")): page for page in pages}


def license_ok(meta: dict[str, Any]) -> bool:
    joined = " ".join(
        clean(meta.get(key, ""))
        for key in ("LicenseShortName", "License", "UsageTerms", "LicenseUrl", "Copyrighted")
    ).lower()
    return not any(x in joined for x in DENIED) and any(x in joined for x in ALLOWED)


def make_item(page: dict[str, Any], slug: str) -> dict[str, Any]:
    info = (page.get("imageinfo") or [None])[0]
    if not info:
        raise RuntimeError("missing imageinfo")
    mime = str(info.get("mime", "")).lower()
    if mime not in VIDEO_MIMES:
        raise RuntimeError(f"not a video: {mime}")
    size = int(info.get("size") or 0)
    if not size or size > MAX_SOURCE_BYTES:
        raise RuntimeError(f"invalid/oversized source: {size}")
    meta = info.get("extmetadata") or {}
    if not license_ok(meta):
        raise RuntimeError(
            "license rejected: " + clean(meta.get("LicenseShortName") or meta.get("UsageTerms"))
        )
    return {
        "slug": slug,
        "title": str(page.get("title", "")).removeprefix("File:"),
        "download_url": info["url"],
        "source_page": info.get("descriptionurl"),
        "mime": mime,
        "bytes": size,
        "width": info.get("width"),
        "height": info.get("height"),
        "author": clean(meta.get("Artist")) or clean(meta.get("Credit")) or "See source page",
        "license": clean(meta.get("LicenseShortName")) or clean(meta.get("UsageTerms")),
        "license_url": clean(meta.get("LicenseUrl")),
        "description": clean(meta.get("ImageDescription")),
        "date": clean(meta.get("DateTimeOriginal")) or clean(meta.get("DateTime")),
    }


def download(url: str, path: Path) -> None:
    with requests.get(url, headers=HEADERS, stream=True, timeout=(30, 300)) as response:
        response.raise_for_status()
        total = 0
        with path.open("wb") as handle:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if not chunk:
                    continue
                total += len(chunk)
                if total > MAX_SOURCE_BYTES:
                    raise RuntimeError("source exceeded size limit")
                handle.write(chunk)


def probe_duration(path: Path) -> float:
    result = subprocess.check_output(
        [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(path),
        ],
        text=True,
    ).strip()
    return max(0.1, float(result))


def normalize(source: Path, output: Path, index: int) -> dict[str, float]:
    duration = probe_duration(source)
    clip_len = min(8.0, duration)
    usable = max(0.0, duration - clip_len - 0.5)
    start = min(usable, 0.5 + index * 1.35) if usable else 0.0
    subprocess.run(
        [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "warning",
            "-ss", f"{start:.3f}", "-i", str(source), "-t", f"{clip_len:.3f}",
            "-an", "-vf",
            "scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280,fps=30,format=yuv420p",
            "-c:v", "libx264", "-preset", "medium", "-crf", "27",
            "-movflags", "+faststart", str(output),
        ],
        check=True,
    )
    return {"source_duration": duration, "clip_start": start, "clip_duration": clip_len}


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    CLIPS.mkdir(parents=True, exist_ok=True)
    pages = fetch_pages()
    completed: list[dict[str, Any]] = []

    for index, (title, slug) in enumerate(FILES, start=1):
        page = pages.get(title)
        if not page:
            print(f"Missing Commons page: {title}", file=sys.stderr)
            continue
        try:
            item = make_item(page, slug)
            print(f"Selected {slug}: {item['title']} ({item['bytes']/1024/1024:.1f} MB)")
            extension = ".webm" if "webm" in item["mime"] else ".ogv" if "ogg" in item["mime"] else ".mp4"
            raw_path = RAW / f"{index:02d}_{slug}{extension}"
            clip_path = CLIPS / f"{index:02d}_{slug}.mp4"
            download(item["download_url"], raw_path)
            item.update(normalize(raw_path, clip_path, index))
            item["clip_file"] = str(clip_path.relative_to(OUT))
            item["clip_bytes"] = clip_path.stat().st_size
            completed.append(item)
        except Exception as exc:  # noqa: BLE001
            print(f"Skipping {title}: {exc}", file=sys.stderr)
        finally:
            for path in RAW.glob(f"{index:02d}_{slug}.*"):
                path.unlink(missing_ok=True)

    if len(completed) < 5:
        raise RuntimeError(f"Only normalized {len(completed)} clips; need at least 5")

    (OUT / "manifest.json").write_text(
        json.dumps(completed, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    lines = [
        "# Open ocean footage attribution", "",
        "Clips were retrieved from Wikimedia Commons and normalized for a HyperFrames editing test.",
        "Original license and attribution requirements remain attached to every source.", "",
    ]
    for number, item in enumerate(completed, start=1):
        lines += [
            f"## {number}. {item['title']}",
            f"- Local clip: `{item['clip_file']}`",
            f"- Author/credit: {item['author']}",
            f"- License: {item['license']}",
            f"- License URL: {item['license_url'] or 'See source page'}",
            f"- Source page: {item['source_page']}",
            f"- Original download: {item['download_url']}",
            f"- Extract: {item['clip_start']:.2f}s–{item['clip_start'] + item['clip_duration']:.2f}s", "",
        ]
    (OUT / "ATTRIBUTION.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"Completed {len(completed)} clips")


if __name__ == "__main__":
    main()
