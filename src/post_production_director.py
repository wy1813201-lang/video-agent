"""
Post-Production Director Agent

输入:
- script_text
- storyboard_json_path
- clip_paths
- emotion_tags (optional)

输出:
- timeline.json
- voice_plan.json
- music_plan.json
- voice_track.wav (best-effort)
- episode_XX_final.mp4 (best-effort)
"""

import json
import os
import shlex
import subprocess
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from .tts_client import VoiceSelector
from .video_composer import VideoComposer, CompositionConfig, VideoClip


EMOTION_SPEED_MAP = {
    "mysterious": 0.90,
    "calm": 0.92,
    "tension": 0.85,
    "epic": 1.05,
    "narration": 0.95,
}

SCENE_EMOTION_MAP = {
    "悬疑/紧张": "mysterious",
    "平静/叙事": "narration",
    "紧张/对抗": "tension",
    "爱情/温情": "calm",
    "复仇/愤怒": "epic",
    "悲伤/离别": "calm",
    "轻松/幽默": "calm",
    "震惊/反转": "tension",
}


@dataclass
class TimelineItem:
    shot_id: str
    clip_path: str
    start: float
    end: float
    duration: float
    emotion: str
    dialogue: str
    rhythm: str


@dataclass
class VoicePlanItem:
    shot_id: str
    text: str
    emotion: str
    speed: float
    pause_after: float
    volume: float


@dataclass
class MusicPlanItem:
    shot_id: str
    emotion: str
    start: float
    end: float
    track: str
    volume_db: float
    transition: str


class PostProductionDirector:
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.post_cfg = self.config.get("post_production", {})
        self.tts_cfg = self.config.get("tts", {})
        self.voice_selector = VoiceSelector(default_engine="edge")

    def run(
        self,
        episode_num: int,
        script_text: str,
        storyboard_json_path: str,
        clip_paths: List[str],
        output_dir: str = "output",
        emotion_tags: Optional[List[str]] = None,
    ) -> Dict[str, Optional[str]]:
        out_dir = Path(output_dir)
        pp_dir = out_dir / "post_production" / f"episode_{episode_num:02d}"
        pp_dir.mkdir(parents=True, exist_ok=True)

        storyboard = self._load_storyboard(storyboard_json_path)
        timeline = self._build_timeline(script_text, storyboard, clip_paths, emotion_tags)
        timeline_path = str(pp_dir / "timeline.json")
        self._save_json(timeline_path, [asdict(x) for x in timeline])

        voice_plan = self._generate_voice_plan(timeline)
        voice_plan_path = str(pp_dir / "voice_plan.json")
        self._save_json(voice_plan_path, [asdict(x) for x in voice_plan])

        music_plan = self._generate_music_plan(timeline)
        music_plan_path = str(pp_dir / "music_plan.json")
        self._save_json(music_plan_path, [asdict(x) for x in music_plan])

        # Stage 6: Generate Subtitles
        srt_path = str(pp_dir / "bilingual_subtitles.srt")
        self._generate_srt_file(timeline, srt_path)

        voice_track_path = self._render_voice_track(voice_plan, pp_dir)
        bgm_track_path = self._render_music_track(music_plan, pp_dir, total_duration=timeline[-1].end if timeline else 0.0)

        final_path = self._merge_episode_media(
            episode_num=episode_num,
            clip_paths=clip_paths,
            voice_track_path=voice_track_path,
            bgm_track_path=bgm_track_path,
            srt_path=srt_path,
            output_dir=output_dir,
        )

        # Generate clickbait thumbnail prompt
        thumbnail_prompt = self.generate_youtube_thumbnail_prompt(script_text)
        thumbnail_prompt_path = str(pp_dir / "thumbnail_prompt.txt")
        with open(thumbnail_prompt_path, "w", encoding="utf-8") as f:
            f.write(thumbnail_prompt)

        return {
            "timeline_path": timeline_path,
            "voice_plan_path": voice_plan_path,
            "music_plan_path": music_plan_path,
            "voice_track_path": voice_track_path,
            "bgm_track_path": bgm_track_path,
            "srt_path": srt_path,
            "thumbnail_prompt": thumbnail_prompt,
            "final_path": final_path,
        }

    def _load_storyboard(self, path: str) -> Dict[str, Any]:
        if not path or not os.path.exists(path):
            return {}
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _build_timeline(
        self,
        script_text: str,
        storyboard: Dict[str, Any],
        clip_paths: List[str],
        emotion_tags: Optional[List[str]],
    ) -> List[TimelineItem]:
        shots = storyboard.get("shots", []) if storyboard else []
        dialogues = self._extract_dialogues(script_text)
        timeline: List[TimelineItem] = []
        cursor = 0.0

        for idx, clip in enumerate(clip_paths):
            shot = shots[idx] if idx < len(shots) else {}
            shot_id = shot.get("shot_id", f"shot_{idx+1:03d}")
            scene_emotion = shot.get("continuity_state", {}).get("mood_lock", "")
            emotion = self._normalize_emotion(scene_emotion)
            if emotion_tags and idx < len(emotion_tags):
                emotion = emotion_tags[idx]

            duration = self._probe_duration(clip) if os.path.exists(clip) else 5.0
            rhythm = self._infer_rhythm(duration)
            dialogue = dialogues[idx] if idx < len(dialogues) else ""

            item = TimelineItem(
                shot_id=shot_id,
                clip_path=clip,
                start=round(cursor, 3),
                end=round(cursor + duration, 3),
                duration=round(duration, 3),
                emotion=emotion,
                dialogue=dialogue,
                rhythm=rhythm,
            )
            timeline.append(item)
            cursor += duration

        return timeline

    def _extract_dialogues(self, script_text: str) -> List[str]:
        lines = []
        for raw in (script_text or "").splitlines():
            s = raw.strip()
            if not s:
                continue
            if s.startswith("场景"):
                continue
            if ":" in s or "：" in s:
                parts = s.replace("：", ":", 1).split(":", 1)
                if len(parts) == 2 and parts[1].strip():
                    lines.append(parts[1].strip())
        return lines

    def _normalize_emotion(self, scene_emotion: str) -> str:
        if scene_emotion in SCENE_EMOTION_MAP:
            return SCENE_EMOTION_MAP[scene_emotion]
        if any(k in scene_emotion for k in ["紧张", "悬疑", "反转"]):
            return "tension"
        if any(k in scene_emotion for k in ["平静", "叙事"]):
            return "narration"
        if any(k in scene_emotion for k in ["温情", "轻松", "幽默", "悲伤"]):
            return "calm"
        return "narration"

    def _infer_rhythm(self, duration: float) -> str:
        if duration < 3:
            return "tension"
        if duration > 7:
            return "ambient"
        return "narrative"

    def _generate_voice_plan(self, timeline: List[TimelineItem]) -> List[VoicePlanItem]:
        plan: List[VoicePlanItem] = []
        for item in timeline:
            emotion = item.emotion
            speed = EMOTION_SPEED_MAP.get(emotion, 0.95)
            pause = 0.35 if item.rhythm == "tension" else 0.5
            volume = 1.0 if emotion in ("epic", "tension") else 0.9
            text = item.dialogue or " "
            plan.append(
                VoicePlanItem(
                    shot_id=item.shot_id,
                    text=text,
                    emotion=emotion,
                    speed=speed,
                    pause_after=pause,
                    volume=volume,
                )
            )
        return plan

    def _generate_music_plan(self, timeline: List[TimelineItem]) -> List[MusicPlanItem]:
        tracks = self._scan_bgm_tracks()
        plan: List[MusicPlanItem] = []
        for item in timeline:
            track = self._pick_track_for_emotion(item.emotion, tracks)
            volume_db = -12.0 if item.dialogue.strip() else -7.0
            transition = "acrossfade" if plan else "none"
            plan.append(
                MusicPlanItem(
                    shot_id=item.shot_id,
                    emotion=item.emotion,
                    start=item.start,
                    end=item.end,
                    track=track,
                    volume_db=volume_db,
                    transition=transition,
                )
            )
        return plan

    def _scan_bgm_tracks(self) -> List[str]:
        bgm_dir = self.post_cfg.get("bgm_dir", "assets/bgm")
        p = Path(bgm_dir)
        if not p.exists():
            return []
        tracks = []
        for ext in ("*.mp3", "*.wav", "*.m4a", "*.aac"):
            tracks.extend([str(x) for x in p.glob(ext)])
        return sorted(tracks)

    def _pick_track_for_emotion(self, emotion: str, tracks: List[str]) -> str:
        if not tracks:
            return ""
        keys = {
            "mysterious": ["myst", "suspense", "dark"],
            "tension": ["tension", "hit", "dramatic", "thrill"],
            "calm": ["calm", "soft", "ambient", "piano"],
            "epic": ["epic", "hero", "trailer", "battle"],
            "narration": ["narrative", "story", "light", "bgm"],
        }.get(emotion, ["bgm"])
        for t in tracks:
            name = Path(t).name.lower()
            if any(k in name for k in keys):
                return t
        return tracks[0]

    def _render_voice_track(self, voice_plan: List[VoicePlanItem], pp_dir: Path) -> Optional[str]:
        if not voice_plan:
            return None

        engine = self.tts_cfg.get("provider", "edge_tts")
        engine = "edge" if "edge" in engine else "edge"
        voice_raw = self.tts_cfg.get("voice", "zh-CN-XiaoxiaoNeural")
        voice = self._normalize_edge_voice(voice_raw)

        segment_paths: List[str] = []
        for i, item in enumerate(voice_plan, 1):
            if not item.text.strip():
                continue
            rate = self._speed_to_edge_rate(item.speed)
            seg_mp3 = pp_dir / f"voice_seg_{i:03d}.mp3"
            generated = self.voice_selector.generate(
                text=item.text,
                output_path=str(seg_mp3),
                engine=engine,
                voice=voice,
                rate=rate,
            )
            if not generated or not os.path.exists(generated):
                continue
            segment_paths.append(generated)

            silence = self._make_silence(pp_dir, seconds=item.pause_after, name=f"pause_{i:03d}.wav")
            if silence:
                segment_paths.append(silence)

        if not segment_paths:
            return None

        concat_file = pp_dir / "voice_concat.txt"
        with open(concat_file, "w", encoding="utf-8") as f:
            for p in segment_paths:
                f.write(f"file {shlex.quote(os.path.abspath(p))}\n")

        out_wav = pp_dir / "voice_track.wav"
        cmd = [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file),
            "-ac", "1", "-ar", "44100", str(out_wav),
        ]
        ok = self._run_ffmpeg(cmd)
        return str(out_wav) if ok else None

    def _normalize_edge_voice(self, voice_raw: str) -> str:
        # tts_config may already store full voice ID
        mapping = {
            "zh-cn-xiaoxiaoneural": "xiaoxiao",
            "zh-cn-yunxineural": "yunxi",
            "zh-cn-yunjianneural": "yunjian",
            "zh-cn-xiaoyineural": "xiaoyi",
        }
        key = voice_raw.strip().lower()
        return mapping.get(key, voice_raw)

    def _speed_to_edge_rate(self, speed: float) -> str:
        pct = int(round((speed - 1.0) * 100))
        if pct >= 0:
            return f"+{pct}%"
        return f"{pct}%"

    def _make_silence(self, pp_dir: Path, seconds: float, name: str) -> Optional[str]:
        if seconds <= 0:
            return None
        out = pp_dir / name
        cmd = [
            "ffmpeg", "-y", "-f", "lavfi", "-i",
            "anullsrc=r=44100:cl=mono", "-t", str(round(seconds, 3)), str(out),
        ]
        return str(out) if self._run_ffmpeg(cmd) else None

    def _render_music_track(self, music_plan: List[MusicPlanItem], pp_dir: Path, total_duration: float) -> Optional[str]:
        if not music_plan or total_duration <= 0:
            return None

        # Select the first available track as base, then loop/cut to timeline length.
        first = ""
        for item in music_plan:
            if item.track and os.path.exists(item.track):
                first = item.track
                break
        if not first:
            return None

        bgm_out = pp_dir / "bgm_track.wav"
        cmd = [
            "ffmpeg", "-y", "-stream_loop", "-1", "-i", first,
            "-t", str(round(total_duration, 3)),
            "-af", "afade=t=in:st=0:d=0.8,afade=t=out:st=max(0\\,t-1.2):d=1.2",
            str(bgm_out),
        ]
        # fallback afade expression compatibility
        if not self._run_ffmpeg(cmd):
            cmd = [
                "ffmpeg", "-y", "-stream_loop", "-1", "-i", first,
                "-t", str(round(total_duration, 3)),
                str(bgm_out),
            ]
            if not self._run_ffmpeg(cmd):
                return None
        return str(bgm_out)

    def _merge_episode_media(
        self,
        episode_num: int,
        clip_paths: List[str],
        voice_track_path: Optional[str],
        bgm_track_path: Optional[str],
        srt_path: Optional[str],
        output_dir: str,
    ) -> Optional[str]:
        valid = [p for p in clip_paths if p and os.path.exists(p)]
        if not valid:
            return None

        base_video = os.path.join(output_dir, f"episode_{episode_num:02d}_base.mp4")
        final_video = os.path.join(output_dir, f"episode_{episode_num:02d}_final.mp4")

        composer = VideoComposer(CompositionConfig(output_path=base_video))
        composer.compose([VideoClip(path=p) for p in valid])

        if not voice_track_path and not bgm_track_path:
            os.replace(base_video, final_video)
            return final_video

        cmd = ["ffmpeg", "-y", "-i", base_video]
        filter_parts = []
        map_audio = None
        input_idx = 1

        if voice_track_path and os.path.exists(voice_track_path):
            cmd += ["-i", voice_track_path]
            filter_parts.append("[1:a]volume=1.0[voice]")
            map_audio = "[voice]"
            input_idx = 2

        if bgm_track_path and os.path.exists(bgm_track_path):
            cmd += ["-i", bgm_track_path]
            bgm_in = f"[{input_idx}:a]"
            if map_audio == "[voice]":
                # sidechain ducking: voice appears -> bgm reduced
                filter_parts.append(f"{bgm_in}volume=0.65[bgm]")
                filter_parts.append("[bgm][voice]sidechaincompress=threshold=0.02:ratio=8:attack=20:release=250[ducked]")
                filter_parts.append("[voice][ducked]amix=inputs=2:duration=first:normalize=0[aout]")
                map_audio = "[aout]"
            else:
                filter_parts.append(f"{bgm_in}volume=0.65[aout]")
                map_audio = "[aout]"

        if filter_parts and map_audio:
            filter_str = ";".join(filter_parts)
            # If SRT is provided, add subtitles to the video filter
            if srt_path and os.path.exists(srt_path):
                # Escape path for FFmpeg filter
                srt_escaped = srt_path.replace("\\", "/").replace(":", "\\:")
                video_filter = f"subtitles={srt_escaped}:force_style='Fontname=Arial,FontSize=24,PrimaryColour=&H0000FFFF,OutlineColour=&H00000000,BorderStyle=1,Outline=2,Alignment=2,MarginV=15'"
                cmd += [
                    "-filter_complex", filter_str,
                    "-vf", video_filter,
                    "-map", "0:v", "-map", map_audio,
                    "-c:v", "libx264", "-c:a", "aac",
                    final_video,
                ]
            else:
                cmd += [
                    "-filter_complex", filter_str,
                    "-map", "0:v", "-map", map_audio,
                    "-c:v", "copy", "-c:a", "aac",
                    final_video,
                ]
        else:
            if srt_path and os.path.exists(srt_path):
                srt_escaped = srt_path.replace("\\", "/").replace(":", "\\:")
                video_filter = f"subtitles={srt_escaped}:force_style='Fontname=Arial,FontSize=24,PrimaryColour=&H0000FFFF,OutlineColour=&H00000000,BorderStyle=1,Outline=2,Alignment=2,MarginV=15'"
                cmd += ["-vf", video_filter, "-c:v", "libx264", "-c:a", "copy", final_video]
            else:
                cmd += ["-c:v", "copy", "-c:a", "copy", final_video]

        ok = self._run_ffmpeg(cmd)
        if not ok:
            return None
        return final_video

    def _probe_duration(self, video_path: str) -> float:
        cmd = [
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_format", video_path,
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            data = json.loads(result.stdout or "{}")
            return float(data.get("format", {}).get("duration", 5.0))
        except Exception:
            return 5.0

    def _run_ffmpeg(self, cmd: List[str]) -> bool:
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            return result.returncode == 0
        except Exception:
            return False

    def _save_json(self, path: str, data: Any) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    # ------------------------------------------------------------------ #
    #  SOP 后期增强方法（统一调色 / 锐度颗粒 / 动态模糊）
    # ------------------------------------------------------------------ #

    def apply_unified_color_grade(
        self,
        input_video: str,
        output_video: str,
        style: str = "cinematic",
    ) -> bool:
        """
        [SOP 阶段6] 统一调色 —— 确保全集色调风格一致。

        预设：
        - cinematic: 低饱和、轻微蓝绿偏移、略微提亮高光
        - warm:      暖橙色调，适合情感剧
        - cool:      冷蓝绿，适合悬疑/科幻
        - vintage:   复古低对比，胶片感
        """
        if not os.path.exists(input_video):
            return False

        PRESETS = {
            "cinematic": (
                "eq=brightness=0.03:contrast=1.08:saturation=0.82,"
                "colorbalance=rs=-0.05:gs=0.02:bs=0.08"
            ),
            "warm": (
                "eq=brightness=0.02:contrast=1.05:saturation=1.10,"
                "colorbalance=rs=0.12:gs=0.02:bs=-0.08"
            ),
            "cool": (
                "eq=brightness=0.0:contrast=1.10:saturation=0.85,"
                "colorbalance=rs=-0.08:gs=0.01:bs=0.12"
            ),
            "vintage": (
                "eq=brightness=0.0:contrast=0.92:saturation=0.70:gamma=1.08,"
                "curves=preset=vintage"
            ),
        }
        vf = PRESETS.get(style, PRESETS["cinematic"])
        cmd = [
            "ffmpeg", "-y", "-i", input_video,
            "-vf", vf,
            "-c:v", "libx264", "-crf", "18", "-preset", "fast",
            "-c:a", "copy", output_video,
        ]
        ok = self._run_ffmpeg(cmd)
        if ok:
            print(f"[PostProduction] 统一调色完成 ({style}): {output_video}")
        return ok

    def apply_unified_sharpness_grain(
        self,
        input_video: str,
        output_video: str,
        sharpen_strength: float = 0.5,
        grain_intensity: float = 0.03,
    ) -> bool:
        """
        [SOP 阶段6] 统一锐度与胶片颗粒——提升画面质感和风格统一性。

        Args:
            sharpen_strength: 锐化强度 0~2 (推荐 0.3~0.8)
            grain_intensity:  胶片颗粒强度 0~0.1 (推荐 0.02~0.05)
        """
        if not os.path.exists(input_video):
            return False

        # unsharp: luma_msize_x=5, luma_msize_y=5, luma_amount
        unsharp = f"unsharp=lx=5:ly=5:la={sharpen_strength:.2f}:cx=5:cy=5:ca=0.0"
        # noise as grain (alls=noise seed, strength)
        noise = f"noise=alls={int(grain_intensity*100)}:allf=t+u"
        vf = f"{unsharp},{noise}"

        cmd = [
            "ffmpeg", "-y", "-i", input_video,
            "-vf", vf,
            "-c:v", "libx264", "-crf", "18", "-preset", "fast",
            "-c:a", "copy", output_video,
        ]
        ok = self._run_ffmpeg(cmd)
        if ok:
            print(f"[PostProduction] 锐度+颗粒处理完成: {output_video}")
        return ok

    def apply_dynamic_blur(
        self,
        input_video: str,
        output_video: str,
        blur_radius: int = 3,
        motion_threshold: float = 0.3,
    ) -> bool:
        """
        [SOP 阶段6] 动态模糊 —— 为快速运动场景添加运动感，避免画面僵硬。

        Args:
            blur_radius:       模糊半径 (1~10)
            motion_threshold: 仅在画面运动量超过此阈值时应用（0~1，0=总是应用）
        """
        if not os.path.exists(input_video):
            return False

        # minterpolate: motion blur at display frame rate
        vf = (
            f"minterpolate=fps=60:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1,"
            f"boxblur=lr={blur_radius}:lp=1"
        )
        cmd = [
            "ffmpeg", "-y", "-i", input_video,
            "-vf", vf,
            "-c:v", "libx264", "-crf", "18", "-preset", "fast",
            "-c:a", "copy", output_video,
        ]
        ok = self._run_ffmpeg(cmd)
        # fallback: simple boxblur if minterpolate fails
        if not ok:
            cmd = [
                "ffmpeg", "-y", "-i", input_video,
                "-vf", f"boxblur=lr={blur_radius}:lp=1",
                "-c:v", "libx264", "-crf", "18", "-preset", "fast",
                "-c:a", "copy", output_video,
            ]
            ok = self._run_ffmpeg(cmd)
        if ok:
            print(f"[PostProduction] 动态模糊处理完成: {output_video}")
        return ok

    def apply_full_sop_post_processing(
        self,
        input_video: str,
        output_dir: str,
        color_style: str = "cinematic",
        apply_grain: bool = True,
        apply_blur: bool = False,
    ) -> str:
        """
        [SOP 阶段6] 一键应用全套后期处理：调色 → 锐度/颗粒 → (可选)动态模糊。

        Returns:
            最终输出路径（字符串）
        """
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        # Step 1: 统一调色
        graded = str(out_dir / "step1_graded.mp4")
        ok = self.apply_unified_color_grade(input_video, graded, color_style)
        current = graded if ok else input_video

        # Step 2: 锐度 + 颗粒
        if apply_grain:
            grained = str(out_dir / "step2_grain.mp4")
            ok = self.apply_unified_sharpness_grain(current, grained)
            if ok:
                current = grained

        # Step 3: 动态模糊（可选）
        if apply_blur:
            blurred = str(out_dir / "step3_blur.mp4")
            ok = self.apply_dynamic_blur(current, blurred)
            if ok:
                current = blurred

        # 输出最终成片
        final = str(out_dir / "final_sop_processed.mp4")
        if current != input_video:
            import shutil as _shutil
            _shutil.copy2(current, final)
        else:
            final = current

        print(f"[PostProduction] SOP 全套后期完成: {final}")
        return final

    # ------------------------------------------------------------------ #
    #  SOP Stage 6: YouTube Meta Enhancements
    # ------------------------------------------------------------------ #

    def _format_time_srt(self, seconds: float) -> str:
        """格式化秒数为 SRT 时间格式 (HH:MM:SS,mmm)"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        msec = int((seconds - int(seconds)) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{msec:03d}"

    def _generate_srt_file(self, timeline: List[TimelineItem], srt_path: str) -> bool:
        """从 timeline 生成双语 SRT 字幕文件"""
        lines = []
        seq = 1
        for item in timeline:
            if not item.dialogue.strip():
                continue
            start_str = self._format_time_srt(item.start)
            end_str = self._format_time_srt(item.end - 0.1)  # 留出一点间隙
            lines.append(str(seq))
            lines.append(f"{start_str} --> {end_str}")
            # 模拟双语字幕：中文原音，英文直译（可以通过 LLM API获取真实翻译，此处仅拼接格式）
            clean_zh = item.dialogue.replace('\n', ' ')
            lines.append(clean_zh)
            # Todo: 接入真实的翻译 API
            lines.append(f"[EN Translation of: {clean_zh}]")
            lines.append("")
            seq += 1
        
        with open(srt_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        return True

    def generate_youtube_thumbnail_prompt(self, script_text: str) -> str:
        """
        [SOP 阶段6] 生成 YouTube / TikTok 高转化率封面图的 Prompt
        抽取极具张力的瞬间（打脸、曝光、震惊）作为缩略图。
        """
        # 简单从前几行提取关键词作为核心冲突
        title_lines = [line for line in script_text.splitlines() if line.strip()][:5]
        context = " ".join(title_lines)
        
        return (
            "YouTube clickbait thumbnail, extreme emotional reaction, high tension, "
            "close-up of gorgeous characters, shocked expression, hyper-realistic, "
            "highly attractive idol-drama aesthetic, cinematic lighting, high saturation, "
            f"context: {context}, "
            "bold composition, dramatic rim light, 16:9 aspect ratio, masterpiece"
        )
