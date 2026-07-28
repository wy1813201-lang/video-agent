#!/usr/bin/env python3
"""Fetch openly licensed ocean-life footage from Wikimedia Commons.

The script searches Commons, verifies license metadata, downloads a bounded set
of clips, normalizes each to a short 9:16 H.264 MP4, and writes attribution
manifests. Intended for a one-off HyperFrames editing test.
"""

from __future__ import annotations

import html
import json
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import requests

API = "https://commons.wikimedia.org/w/api.php"
OUT = Path("ocean-footage")
RAW = OUT / "raw"
CLIPS = OUT / "clips"
HEADERS = {"User-Agent": "HyperFramesOceanFootage/1.0 (open-media editing test)"}

SEARCHES = [
    ("sea turtle underwater video", "sea-turtle"),
    ("coral reef fish underwater video", "coral-fish"),
    ("reef shark underwater video", "reef-shark"),
    ("octopus deep sea NOAA video", "octopus"),
    ("jellyfish Mariana video NOAA", "jellyfish"),
    ("manta ray underwater video", "manta-ray"),
    ("school of fish underwater video", "fish-school"),
    ("coral reef underwater video", "coral-reef"),
]

ALLOWED_LICENSE_MARKERS = (
    "public domain",
    "cc0",
    "creative commons attribution",
    "cc by",
    "cc-by",
    "cc by-sa",
    "cc-by-sa",
)
DENIED_LICENSE_MARKERS = ("noncommercial", "no derivatives", "cc by-nc", "cc by-nd")
VIDEO_MIMES = {"video/webm", "video/ogg", "video/mp4", "application/ogg"}
MAX_SOURCE_BYTES = 450 * 1024 * 1024
TARGET_CLIPS = 8


def clean(value: Any) -> str:
    if isinstance(value, dict):
        value = value.get("value", "")
    text = html.unescape(str(value or ""))
    text = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"\s+", " ", text).strip()


def commons_search(query: str, limit: int = 20) -> list[dict[str, Any]]:
    params = {
        "action": "query",
        "format": "json",
        "formatversion": 2,
        "generator": "search",
        "gsrsearch": query,
        "gsrnamespace": 6,
        "gsrlimit": limit,
        "prop": "imageinfo",
        "iiprop": "url|mime|size|extmetadata",
    }
    response = requests.get(API, params=params, headers=HEADERS, timeout=45)
    response.raise_for_status()
    return response.json().get("query", {}).get("pages", [])


def license_ok(meta: dict[str, Any]) -> bool:
    joined = " ".join(
        clean(meta.get(key, ""))
        for key in ("LicenseShortName", "License", "UsageTerms", "LicenseUrl", "Copyrighted")
    ).lower()
    if any(marker in joined for marker in DENIED_LICENSE_MARKERS):
        return False
    return any(marker in joined for marker in ALLOWED_LICENSE_MARKERS)


def candidate_from_page(page: dict[str, Any], slug: str) -> dict[str, Any] | None:
    infos = page.get("imageinfo") or []
    if not infos:
        return None
    info = infos[0]
    mime = str(info.get("mime", "")).lower()
    if mime not in VIDEO_MIMES:
        return None
    size = int(info.get("size") or 0)
    if not size or size > MAX_SOURCE_BYTES:
        return None
    meta = info.get("extmetadata") or {}
    if not license_ok(meta):
        return None
    title = str(page.get("title") or "").removeprefix("File:")
    source_page = info.get("descriptionurl") or (
        "https://commons.wikimedia.org/wiki/" + requests.utils.quote(str(page.get("title", "")), safe=":")
    )
    return {
        "slug": slug,
        "title": title,
        "download_url": info.get("url"),
        "source_page": source_page,
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


def select_candidates() -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    for query, slug in SEARCHES:
        try:
            pages = commons_search(query)
        except Exception as exc:  # noqa: BLE001
            print(f"Search failed for {query!r}: {exc}", file=sys.stderr)
            continue
        candidates = []
        for page in pages:
            item = candidate_from_page(page, slug)
            if item and item["download_url"] not in seen_urls:
                candidates.append(item)
        # Prefer moderate file sizes and portrait-friendly or near-square media.
        candidates.sort(
            key=lambda x: (
                0 if (x.get("height") or 0) >= (x.get("width") or 0) else 1,
                x["bytes"],
            )
        )
        if candidates:
            pick = candidates[0]
            selected.append(pick)
            seen_urls.add(pick["download_url"])
            print(f"Selected {slug}: {pick['title']} ({pick['bytes']/1024/1024:.1f} MB)")
        if len(selected) >= TARGET_CLIPS:
            break
        time.sleep(0.4)
    return selected


def download(url: str, path: Path) -> None:
    with requests.get(url, headers=HEADERS, stream=True, timeout=(30, 240)) as response:
        response.raise_for_status()
        total = 0
        with path.open("wb") as handle:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if not chunk:
                    continue
                total += len(chunk)
                if total > MAX_SOURCE_BYTES:
                    raise RuntimeError("Source exceeded size limit during download")
                handle.write(chunk)


def duration_seconds(path: Path) -> float:
    command = [
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(path),
    ]
    value = subprocess.check_output(command, text=True).strip()
    return max(0.1, float(value))


def normalize(source: Path, output: Path, index: int) -> dict[str, float]:
    duration = duration_seconds(source)
    clip_len = min(8.0, max(5.0, duration))
    # Deterministic offsets spread across the source while avoiding the first/last second.
    usable = max(0.0, duration - clip_len - 1.0)
    start = min(usable, 1.0 + index * 1.7) if usable else 0.0
    vf = (
        "scale=720:1280:force_original_aspect_ratio=increase,"
        "crop=720:1280,"
        "fps=30,format=yuv420p"
    )
    command = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "warning",
        "-ss", f"{start:.3f}", "-i", str(source), "-t", f"{clip_len:.3f}",
        "-an", "-vf", vf, "-c:v", "libx264", "-preset", "medium",
        "-crf", "26", "-movflags", "+faststart", str(output),
    ]
    subprocess.run(command, check=True)
    return {"source_duration": duration, "clip_start": start, "clip_duration": clip_len}


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    CLIPS.mkdir(parents=True, exist_ok=True)
    selected = select_candidates()
    if len(selected) < 5:
        raise RuntimeError(f"Only found {len(selected)} acceptable clips; need at least 5")

    completed: list[dict[str, Any]] = []
    for index, item in enumerate(selected, start=1):
        extension = ".webm" if "webm" in item["mime"] else ".ogv" if "ogg" in item["mime"] else ".mp4"
        raw_path = RAW / f"{index:02d}_{item['slug']}{extension}"
        clip_path = CLIPS / f"{index:02d}_{item['slug']}.mp4"
        try:
            print(f"Downloading {item['title']}")
            download(item["download_url"], raw_path)
            timing = normalize(raw_path, clip_path, index)
            item.update(timing)
            item["clip_file"] = str(clip_path.relative_to(OUT))
            item["clip_bytes"] = clip_path.stat().st_size
            completed.append(item)
        except Exception as exc:  # noqa: BLE001
            print(f"Skipping {item['title']}: {exc}", file=sys.stderr)
        finally:
            raw_path.unlink(missing_ok=True)

    if len(completed) < 5:
        raise RuntimeError(f"Only normalized {len(completed)} clips; need at least 5")

    (OUT / "manifest.json").write_text(json.dumps(completed, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        "# Open ocean footage attribution",
        "",
        "All clips were retrieved from Wikimedia Commons and normalized only for this HyperFrames editing test.",
        "The original license and attribution requirements remain attached to each source.",
        "",
    ]
    for n, item in enumerate(completed, start=1):
        lines.extend(
            [
                f"## {n}. {item['title']}",
                f"- Local clip: `{item['clip_file']}`",
                f"- Author/credit: {item['author']}",
                f"- License: {item['license']}",
                f"- License URL: {item['license_url'] or 'See source page'}",
                f"- Source page: {item['source_page']}",
                f"- Original download: {item['download_url']}",
                f"- Extract: {item['clip_start']:.2f}s–{item['clip_start'] + item['clip_duration']:.2f}s",
                "",
            ]
        )
    (OUT / "ATTRIBUTION.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"Completed {len(completed)} clips")


if __name__ == "__main__":
    main()
