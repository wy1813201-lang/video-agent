"""
视频合成器
基于 FFmpeg 的视频合成，支持转场、字幕、配音、背景音乐
"""

import os
import json
import subprocess
import tempfile
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class TransitionType(str, Enum):
    NONE = "none"
    FADE = "fade"           # 淡入淡出
    DISSOLVE = "dissolve"   # 叠化
    SLIDE_LEFT = "slideleft"
    SLIDE_RIGHT = "slideright"
    WIPE = "wipe"


@dataclass
class SubtitleEntry:
    text: str
    start: float   # 秒
    end: float
    font_size: int = 48
    color: str = "white"
    position: str = "bottom"   # top / bottom / center


@dataclass
class VideoClip:
    path: str
    duration: Optional[float] = None   # None = 使用文件实际时长
    transition: TransitionType = TransitionType.FADE
    transition_duration: float = 0.5


@dataclass
class CompositionConfig:
    output_path: str = "output/final.mp4"
    resolution: str = "1080x1920"   # 竖屏 9:16
    fps: int = 30
    video_bitrate: str = "4M"
    audio_bitrate: str = "192k"
    bgm_path: Optional[str] = None
    bgm_volume: float = 0.3         # 背景音乐音量 0-1
    voiceover_path: Optional[str] = None
    voiceover_volume: float = 1.0
    subtitles: List[SubtitleEntry] = field(default_factory=list)


class VideoComposer:
    """FFmpeg 视频合成器"""

    def __init__(self, config: CompositionConfig = None):
        self.config = config or CompositionConfig()
        self._check_ffmpeg()

    def _check_ffmpeg(self):
        try:
            subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            raise RuntimeError("FFmpeg 未安装或不在 PATH 中，请先安装 FFmpeg")

    # ── 核心合成 ─────────────────────────────────────────────────────────────

    def compose(self, clips: List[VideoClip]) -> str:
        """合成视频片段为完整视频"""
        if not clips:
            raise ValueError("没有可合成的视频片段")

        os.makedirs(os.path.dirname(self.config.output_path) or ".", exist_ok=True)
        w, h = self.config.resolution.split("x")

        # 1. 标准化所有片段（统一分辨率/帧率）
        normalized = self._normalize_clips(clips, int(w), int(h))

        # 2. 拼接（带转场）
        concat_path = self._concat_with_transitions(normalized, clips)

        # 3. 混音（配音 + BGM）
        audio_path = self._mix_audio(concat_path)

        # 4. 烧录字幕
        final = self._burn_subtitles(audio_path)

        # 清理临时文件
        for p in normalized:
            if p != concat_path and os.path.exists(p):
                os.remove(p)

        print(f"✅ 视频合成完成: {final}")
        return final

    def _normalize_clips(self, clips: List[VideoClip], w: int, h: int) -> List[str]:
        """统一分辨率和帧率"""
        results = []
        for i, clip in enumerate(clips):
            out = tempfile.mktemp(suffix=f"_norm{i}.mp4")
            cmd = [
                "ffmpeg", "-y", "-i", clip.path,
                "-vf", f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
                       f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:black",
                "-r", str(self.config.fps),
                "-c:v", "libx264", "-preset", "fast",
                "-c:a", "aac", "-ar", "44100",
            ]
            if clip.duration:
                cmd += ["-t", str(clip.duration)]
            cmd.append(out)
            self._run(cmd)
            results.append(out)
        return results

    def _concat_with_transitions(self, normalized: List[str], clips: List[VideoClip]) -> str:
        """使用 xfade 滤镜拼接转场"""
        if len(normalized) == 1:
            return normalized[0]

        out = tempfile.mktemp(suffix="_concat.mp4")

        # 构建 xfade filter_complex
        inputs = []
        for p in normalized:
            inputs += ["-i", p]

        # 获取每段时长
        durations = [self._get_duration(p) for p in normalized]

        filter_parts = []
        offset = 0.0
        prev = "[0:v]"
        prev_a = "[0:a]"

        for i in range(1, len(normalized)):
            td = clips[i].transition_duration if clips[i].transition != TransitionType.NONE else 0
            offset += durations[i - 1] - td
            vout = f"[v{i}]"
            aout = f"[a{i}]"

            if clips[i].transition == TransitionType.NONE:
                filter_parts.append(f"{prev}[{i}:v]concat=n=2:v=1:a=0{vout}")
                filter_parts.append(f"{prev_a}[{i}:a]concat=n=2:v=0:a=1{aout}")
            else:
                xfade = clips[i].transition.value if clips[i].transition != TransitionType.DISSOLVE else "dissolve"
                filter_parts.append(
                    f"{prev}[{i}:v]xfade=transition={xfade}:duration={td}:offset={offset:.3f}{vout}"
                )
                filter_parts.append(
                    f"{prev_a}[{i}:a]acrossfade=d={td}{aout}"
                )

            prev = vout
            prev_a = aout

        filter_str = ";".join(filter_parts)
        cmd = ["ffmpeg", "-y"] + inputs + [
            "-filter_complex", filter_str,
            "-map", prev, "-map", prev_a,
            "-c:v", "libx264", "-preset", "fast",
            "-c:a", "aac",
            out
        ]
        self._run(cmd)
        return out

    def _mix_audio(self, video_path: str) -> str:
        """混合配音和背景音乐"""
        if not self.config.bgm_path and not self.config.voiceover_path:
            return video_path

        out = tempfile.mktemp(suffix="_audio.mp4")
        inputs = ["-i", video_path]
        filter_parts = ["[0:a]volume=1.0[va]"]
        mix_inputs = "[va]"

        if self.config.voiceover_path and os.path.exists(self.config.voiceover_path):
            inputs += ["-i", self.config.voiceover_path]
            idx = len(inputs) // 2
            filter_parts.append(f"[{idx}:a]volume={self.config.voiceover_volume}[vo]")
            mix_inputs += "[vo]"

        if self.config.bgm_path and os.path.exists(self.config.bgm_path):
            inputs += ["-i", self.config.bgm_path]
            idx = len(inputs) // 2
            filter_parts.append(f"[{idx}:a]volume={self.config.bgm_volume}[bgm]")
            mix_inputs += "[bgm]"

        n = mix_inputs.count("[")
        filter_parts.append(f"{mix_inputs}amix=inputs={n}:duration=first[aout]")

        cmd = ["ffmpeg", "-y"] + inputs + [
            "-filter_complex", ";".join(filter_parts),
            "-map", "0:v", "-map", "[aout]",
            "-c:v", "copy", "-c:a", "aac",
            "-b:a", self.config.audio_bitrate,
            out
        ]
        self._run(cmd)
        return out

    def _burn_subtitles(self, video_path: str) -> str:
        """烧录字幕到视频"""
        if not self.config.subtitles:
            # 直接输出到最终路径
            os.rename(video_path, self.config.output_path)
            return self.config.output_path

        srt_path = tempfile.mktemp(suffix=".srt")
        self._write_srt(self.config.subtitles, srt_path)

        cmd = [
            "ffmpeg", "-y", "-i", video_path,
            "-vf", f"subtitles={srt_path}:force_style='FontSize=48,PrimaryColour=&Hffffff,Outline=2'",
            "-c:a", "copy",
            self.config.output_path
        ]
        self._run(cmd)
        os.remove(srt_path)
        return self.config.output_path

    # ── 工具方法 ─────────────────────────────────────────────────────────────

    def images_to_video(self, image_paths: List[str], duration_each: float = 3.0,
                        output_path: str = None) -> str:
        """将图片序列合成为视频"""
        out = output_path or tempfile.mktemp(suffix="_slideshow.mp4")
        w, h = self.config.resolution.split("x")

        # 写 concat 列表
        list_file = tempfile.mktemp(suffix=".txt")
        with open(list_file, "w") as f:
            for p in image_paths:
                f.write(f"file '{os.path.abspath(p)}'\n")
                f.write(f"duration {duration_each}\n")

        cmd = [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_file,
            "-vf", f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
                   f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:black,fps={self.config.fps}",
            "-c:v", "libx264", "-preset", "fast", "-pix_fmt", "yuv420p",
            out
        ]
        self._run(cmd)
        os.remove(list_file)
        return out

    def add_bgm(self, video_path: str, bgm_path: str, volume: float = 0.3,
                output_path: str = None) -> str:
        """给视频添加背景音乐"""
        out = output_path or video_path.replace(".mp4", "_bgm.mp4")
        cmd = [
            "ffmpeg", "-y", "-i", video_path, "-i", bgm_path,
            "-filter_complex",
            f"[0:a]volume=1.0[va];[1:a]volume={volume}[bgm];[va][bgm]amix=inputs=2:duration=first[aout]",
            "-map", "0:v", "-map", "[aout]",
            "-c:v", "copy", "-c:a", "aac",
            out
        ]
        self._run(cmd)
        return out

    def _get_duration(self, path: str) -> float:
        cmd = [
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_format", path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        data = json.loads(result.stdout)
        return float(data["format"]["duration"])

    def _write_srt(self, subtitles: List[SubtitleEntry], path: str):
        def fmt(t: float) -> str:
            h = int(t // 3600)
            m = int((t % 3600) // 60)
            s = int(t % 60)
            ms = int((t % 1) * 1000)
            return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

        with open(path, "w", encoding="utf-8") as f:
            for i, sub in enumerate(subtitles, 1):
                f.write(f"{i}\n{fmt(sub.start)} --> {fmt(sub.end)}\n{sub.text}\n\n")

    def _run(self, cmd: List[str]):
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"FFmpeg 错误:\n{result.stderr[-500:]}")
