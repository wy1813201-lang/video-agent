#!/usr/bin/env python3
"""
短剧 5.0 单集合成入口（最小实现）

目标：把 `07_视频片段` -> `08_后期合成` 接起来。
优先策略：
1. 能拿到 script + storyboard + clips 时，走 PostProductionDirector
2. 否则降级为 VideoComposer 纯拼接

支持输入：
- --episode-dir: 单集目录（内部可包含 07_视频片段 / 08_后期合成 / manifest）
- --clips-dir:   直接指定 07_视频片段
- --manifest:    显式指定 manifest JSON
- --output-dir:  显式指定 08_后期合成
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.video_composer import CompositionConfig, VideoClip, VideoComposer
from src.post_production_director import PostProductionDirector

VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}
MANIFEST_CANDIDATES = [
    "manifest.json",
    "episode_manifest.json",
    "shortdrama5_manifest.json",
    "workflow_manifest.json",
]
STORYBOARD_CANDIDATES = [
    "storyboard.json",
    "storyboard_flow.json",
    "storyboard_latest.json",
    "storyboard_with_keyframes.json",
]
SCRIPT_CANDIDATES = ["script.txt", "episode_script.txt", "script.md"]


@dataclass
class EpisodeContext:
    episode_dir: Optional[Path]
    clips_dir: Path
    output_dir: Path
    manifest_path: Optional[Path] = None
    storyboard_path: Optional[Path] = None
    script_path: Optional[Path] = None
    episode_num: int = 1
    clip_paths: Optional[List[str]] = None


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="短剧5.0 单集合成入口")
    p.add_argument("--episode-dir", help="单集目录，内部可包含 07_视频片段 / 08_后期合成")
    p.add_argument("--clips-dir", help="直接指定视频片段目录（如 07_视频片段）")
    p.add_argument("--manifest", help="显式指定 manifest.json")
    p.add_argument("--output-dir", help="显式指定输出目录（默认 08_后期合成）")
    p.add_argument("--episode-num", type=int, default=None, help="显式指定集数")
    p.add_argument("--force-basic", action="store_true", help="强制只做基础拼接，不走 PostProductionDirector")
    p.add_argument("--dry-run", action="store_true", help="只解析与打印，不实际执行合成")
    return p.parse_args()


def is_video_file(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in VIDEO_EXTS


def natural_key(path: Path):
    import re
    return [int(s) if s.isdigit() else s.lower() for s in re.split(r"(\d+)", path.name)]


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def find_first_existing(base: Path, candidates: List[str]) -> Optional[Path]:
    for name in candidates:
        p = base / name
        if p.exists():
            return p
    return None


def discover_manifest(base: Path) -> Optional[Path]:
    direct = find_first_existing(base, MANIFEST_CANDIDATES)
    if direct:
        return direct
    for p in sorted(base.rglob("*.json")):
        if p.name in MANIFEST_CANDIDATES:
            return p
    return None


def discover_storyboard(base: Path) -> Optional[Path]:
    direct = find_first_existing(base, STORYBOARD_CANDIDATES)
    if direct:
        return direct
    for p in sorted(base.rglob("*.json")):
        if p.name in STORYBOARD_CANDIDATES or "storyboard" in p.name.lower():
            return p
    return None


def discover_script(base: Path) -> Optional[Path]:
    direct = find_first_existing(base, SCRIPT_CANDIDATES)
    if direct:
        return direct
    for p in sorted(base.rglob("*")):
        if p.is_file() and p.name in SCRIPT_CANDIDATES:
            return p
    return None


def extract_episode_num(text: str) -> Optional[int]:
    import re
    m = re.search(r"(?:episode|ep|第)(\d+)", text, flags=re.IGNORECASE)
    if m:
        return int(m.group(1))
    return None


def discover_context(args: argparse.Namespace) -> EpisodeContext:
    episode_dir = Path(args.episode_dir).resolve() if args.episode_dir else None
    manifest_path = Path(args.manifest).resolve() if args.manifest else None

    if args.clips_dir:
        clips_dir = Path(args.clips_dir).resolve()
    elif episode_dir:
        clips_dir = episode_dir / "07_视频片段"
        if not clips_dir.exists():
            clips_dir = episode_dir
    else:
        raise SystemExit("必须提供 --episode-dir 或 --clips-dir")

    if not clips_dir.exists():
        raise SystemExit(f"片段目录不存在: {clips_dir}")

    base = episode_dir or clips_dir
    if manifest_path is None:
        manifest_path = discover_manifest(base)

    output_dir = Path(args.output_dir).resolve() if args.output_dir else ((episode_dir / "08_后期合成") if episode_dir else (clips_dir.parent / "08_后期合成"))
    storyboard_path = discover_storyboard(base)
    script_path = discover_script(base)

    ep_num = args.episode_num
    if ep_num is None:
        for probe in [str(episode_dir or ""), str(clips_dir), str(manifest_path or "")]:
            ep_num = extract_episode_num(probe)
            if ep_num is not None:
                break
    if ep_num is None:
        ep_num = 1

    return EpisodeContext(
        episode_dir=episode_dir,
        clips_dir=clips_dir,
        output_dir=output_dir,
        manifest_path=manifest_path,
        storyboard_path=storyboard_path,
        script_path=script_path,
        episode_num=ep_num,
    )


def normalize_manifest_clip_paths(data: Any, base_dir: Path) -> List[str]:
    candidates: List[Any] = []
    if isinstance(data, dict):
        for key in ["clip_paths", "clips", "videos", "video_paths", "segments", "shots"]:
            val = data.get(key)
            if isinstance(val, list):
                candidates = val
                break
    elif isinstance(data, list):
        candidates = data

    results: List[str] = []
    for item in candidates:
        path_str = None
        if isinstance(item, str):
            path_str = item
        elif isinstance(item, dict):
            for key in ["clip_path", "path", "video_path", "file", "output_path"]:
                if item.get(key):
                    path_str = item[key]
                    break
        if not path_str:
            continue
        p = Path(path_str)
        if not p.is_absolute():
            p = (base_dir / p).resolve()
        if p.exists() and is_video_file(p):
            results.append(str(p))
    return results


def collect_clip_paths(ctx: EpisodeContext) -> List[str]:
    clip_paths: List[str] = []
    if ctx.manifest_path and ctx.manifest_path.exists():
        try:
            data = read_json(ctx.manifest_path)
            clip_paths.extend(normalize_manifest_clip_paths(data, ctx.manifest_path.parent))
        except Exception as e:
            print(f"⚠️ manifest 解析失败，改走目录扫描: {e}")

    if not clip_paths:
        clip_paths = [str(p.resolve()) for p in sorted(ctx.clips_dir.iterdir(), key=natural_key) if is_video_file(p)]

    deduped: List[str] = []
    seen = set()
    for p in clip_paths:
        if p not in seen and os.path.exists(p):
            deduped.append(p)
            seen.add(p)
    return deduped


def load_script_text(script_path: Optional[Path]) -> str:
    if not script_path or not script_path.exists():
        return ""
    return script_path.read_text(encoding="utf-8")


def run_basic_compose(ctx: EpisodeContext, clip_paths: List[str]) -> Dict[str, Any]:
    ctx.output_dir.mkdir(parents=True, exist_ok=True)
    output_path = ctx.output_dir / f"episode_{ctx.episode_num:02d}_assembled.mp4"
    composer = VideoComposer(CompositionConfig(output_path=str(output_path)))
    final_path = composer.compose([VideoClip(path=p) for p in clip_paths])
    return {
        "mode": "basic_compose",
        "final_path": final_path,
    }


def run_post_production(ctx: EpisodeContext, clip_paths: List[str]) -> Dict[str, Any]:
    script_text = load_script_text(ctx.script_path)
    director = PostProductionDirector(config={})
    return director.run(
        episode_num=ctx.episode_num,
        script_text=script_text,
        storyboard_json_path=str(ctx.storyboard_path),
        clip_paths=clip_paths,
        output_dir=str(ctx.output_dir),
        emotion_tags=None,
    )


def main() -> int:
    args = parse_args()
    ctx = discover_context(args)
    clip_paths = collect_clip_paths(ctx)
    ctx.clip_paths = clip_paths

    print("🎬 短剧5.0 单集合成入口")
    print(f"- episode_dir: {ctx.episode_dir or ''}")
    print(f"- clips_dir:   {ctx.clips_dir}")
    print(f"- output_dir:  {ctx.output_dir}")
    print(f"- manifest:    {ctx.manifest_path or ''}")
    print(f"- storyboard:  {ctx.storyboard_path or ''}")
    print(f"- script:      {ctx.script_path or ''}")
    print(f"- episode_num: {ctx.episode_num}")
    print(f"- clips:       {len(clip_paths)}")

    if not clip_paths:
        print("❌ 没找到可用视频片段")
        return 2

    if args.dry_run:
        for idx, p in enumerate(clip_paths, 1):
            print(f"  [{idx:02d}] {p}")
        return 0

    can_post = (not args.force_basic and ctx.storyboard_path and ctx.storyboard_path.exists())

    try:
        if can_post:
            result = run_post_production(ctx, clip_paths)
            mode = "post_production_director"
            final_path = result.get("final_path")
            if not final_path:
                raise RuntimeError("PostProductionDirector 未产出 final_path")
        else:
            result = run_basic_compose(ctx, clip_paths)
            mode = result["mode"]
            final_path = result.get("final_path")

        summary = {
            "mode": mode,
            "episode_num": ctx.episode_num,
            "clip_count": len(clip_paths),
            "episode_dir": str(ctx.episode_dir) if ctx.episode_dir else "",
            "clips_dir": str(ctx.clips_dir),
            "output_dir": str(ctx.output_dir),
            "manifest_path": str(ctx.manifest_path) if ctx.manifest_path else "",
            "storyboard_path": str(ctx.storyboard_path) if ctx.storyboard_path else "",
            "script_path": str(ctx.script_path) if ctx.script_path else "",
            "final_path": final_path or "",
            "result": result,
        }
        summary_path = ctx.output_dir / "assemble_summary.json"
        summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"✅ 合成完成: {final_path}")
        print(f"📝 摘要已写入: {summary_path}")
        return 0
    except Exception as e:
        print(f"❌ 合成失败: {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
