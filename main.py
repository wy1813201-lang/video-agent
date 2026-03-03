#!/usr/bin/env python3
"""
AI Short Drama Automator v2.0
自动化生成AI短剧 - 从剧本到成片全流程
"""

import os
import json
import asyncio
import argparse
import subprocess
from datetime import datetime
from typing import Optional, List
from dataclasses import dataclass, asdict

import yaml

# 核心模块
try:
    from src.script_generator import ScriptGenerator
except ImportError:
    ScriptGenerator = None

try:
    from src.prompt_builder import PromptBuilder
except ImportError:
    PromptBuilder = None

try:
    from src.storyboard_manager import StoryboardManager, Storyboard
except ImportError:
    StoryboardManager = None

try:
    from src.storyboard_flow import StoryboardFlowManager
except ImportError:
    StoryboardFlowManager = None

try:
    from src.story_bible import StoryBibleManager
except ImportError:
    StoryBibleManager = None

try:
    from src.cozex_client import CozexClient
except ImportError:
    CozexClient = None

try:
    from src.jimeng_client import JimengVideoClient
except ImportError:
    JimengVideoClient = None

try:
    from src.post_production_director import PostProductionDirector
except ImportError:
    PostProductionDirector = None

try:
    from src.asset_manager import AssetManager, AssetType
except ImportError:
    AssetManager = None

try:
    from src.video_composer import VideoComposer, CompositionConfig, VideoClip, TransitionType
except ImportError:
    VideoComposer = None

try:
    from src.video_assembler import VideoAssembler
except ImportError:
    VideoAssembler = None


def load_config(config_path: str = "config.yaml") -> dict:
    if os.path.exists(config_path):
        with open(config_path, encoding="utf-8") as f:
            return yaml.safe_load(f)
    return {}


def load_api_config(path: str = "config/api_keys.json") -> dict:
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {}


@dataclass
class DramaConfig:
    topic: str
    style: str = "情感"
    episodes: int = 3
    duration_per_episode: int = 60
    language: str = "zh"
    output_dir: str = "output"
    resolution: str = "1080x1920"
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    replicate_api_key: Optional[str] = None


class ShortDramaAutomator:
    """AI短剧自动生成器 v2.0"""

    def __init__(self, drama_config: DramaConfig, app_config: dict = None):
        self.config = drama_config
        self.app_config = app_config or {}
        self.episodes_data = []
        self.series_video_path: Optional[str] = None

        os.makedirs(drama_config.output_dir, exist_ok=True)

        api_config = load_api_config()
        storage_cfg = self.app_config.get("storage", {})
        video_cfg = self.app_config.get("video", {})
        storyboard_cfg = self.app_config.get("storyboard", {})
        story_bible_cfg = self.app_config.get("story_bible", {})
        video_gen_cfg = self.app_config.get("video_generation", {})

        # 初始化模块
        self.script_gen = ScriptGenerator(drama_config, api_config) if ScriptGenerator else None
        self.prompt_builder = PromptBuilder(drama_config) if PromptBuilder else None

        self.storyboard_mgr = (
            StoryboardManager(storage_cfg.get("storyboards_dir", "output/storyboards"))
            if StoryboardManager else None
        )
        self.storyboards_dir = storage_cfg.get("storyboards_dir", "output/storyboards")
        self.asset_mgr = (
            AssetManager(storage_cfg.get("dir", "data/storage"))
            if AssetManager else None
        )

        transition = TransitionType(video_cfg.get("transition", "fade")) if VideoComposer else None
        self.composer = None
        if VideoComposer:
            comp_cfg = CompositionConfig(
                output_path=os.path.join(drama_config.output_dir, "final.mp4"),
                resolution=drama_config.resolution,
                fps=self.app_config.get("output", {}).get("fps", 30),
                bgm_volume=video_cfg.get("bgm_volume", 0.3),
                voiceover_volume=video_cfg.get("voiceover_volume", 1.0),
            )
            try:
                self.composer = VideoComposer(comp_cfg)
            except RuntimeError as e:
                print(f"⚠️  {e}")

        self._auto_approve = storyboard_cfg.get("auto_approve", False)
        self._scene_duration = storyboard_cfg.get("default_scene_duration", 3.0)
        self._use_two_step_flow = storyboard_cfg.get("use_two_step_flow", True)
        self._two_step_use_gemini = storyboard_cfg.get("use_gemini_for_prompts", False)
        self._auto_generate_media = storyboard_cfg.get("auto_generate_media", False)
        self._auto_compose_episode = storyboard_cfg.get("auto_compose_episode", False)
        self._auto_compose_series = storyboard_cfg.get("auto_compose_series", False)
        self._enable_post_production_director = storyboard_cfg.get("enable_post_production_director", False)
        self._visual_style_profile = str(storyboard_cfg.get("visual_style_profile", "anime"))
        self._video_primary_method = str(video_gen_cfg.get("primary_method", "i2v")).lower()
        self._video_fallback_to_t2v = bool(video_gen_cfg.get("fallback_to_t2v", True))
        self._video_quality_threshold = float(video_gen_cfg.get("quality_threshold", 0.6))
        self._story_bible_enabled = bool(story_bible_cfg.get("enabled", True))
        self._story_bible_path = str(story_bible_cfg.get("path", "data/story_bible.json"))

        image_cfg = api_config.get("image", {}).get("cozex", {})
        video_cfg_api = api_config.get("video", {}).get("jimeng", {})
        self._cozex_enabled = bool(image_cfg.get("enabled"))
        self._jimeng_enabled = bool(video_cfg_api.get("enabled"))
        self.cozex_client = CozexClient() if (self._cozex_enabled and CozexClient) else None
        self.jimeng_client = JimengVideoClient() if (self._jimeng_enabled and JimengVideoClient) else None
        self.post_director = PostProductionDirector(self.app_config) if (
            self._enable_post_production_director and PostProductionDirector
        ) else None
        self.story_bible = None
        if self._story_bible_enabled and StoryBibleManager:
            try:
                self.story_bible = StoryBibleManager(self._story_bible_path)
                self.story_bible.set_series_meta(
                    title=self.config.topic,
                    total_episodes=self.config.episodes,
                    genre=self.config.style,
                )
                self.story_bible.save()
            except Exception as e:
                print(f"⚠️ Story Bible 初始化失败: {e}")
                self.story_bible = None

    async def run(self) -> str:
        print(f"\n🎬 AI短剧自动生成器 v2.0")
        print(f"   主题: {self.config.topic} | 风格: {self.config.style} | 集数: {self.config.episodes}")
        print("=" * 60)

        all_boards = []
        episode_final_paths: List[str] = []
        try:
            for ep in range(1, self.config.episodes + 1):
                print(f"\n📝 第 {ep} 集")

                # 1. 生成剧本
                story_context = ""
                if self.story_bible:
                    try:
                        story_context = self.story_bible.build_context_for_episode(ep)
                    except Exception as e:
                        print(f"   ⚠️ Story Bible 上下文读取失败: {e}")
                        story_context = ""

                if self.script_gen:
                    script = await self.script_gen.generate_episode(
                        topic=self.config.topic,
                        episode_num=ep,
                        total_episodes=self.config.episodes,
                        story_context=story_context,
                    )
                else:
                    script = self._placeholder_script(ep)
                print(f"   ✓ 剧本生成完成 ({len(script)} 字)")
                if self.story_bible:
                    try:
                        self.story_bible.update_after_episode(ep, script)
                        print("   ✓ Story Bible 已更新")
                    except Exception as e:
                        print(f"   ⚠️ Story Bible 更新失败: {e}")

                # 2. 生成分镜
                board = None
                flow = None
                flow_path = None

                flow_mgr = None
                if self._use_two_step_flow and StoryboardFlowManager:
                    flow_mgr = StoryboardFlowManager(
                        script,
                        use_gemini=self._two_step_use_gemini,
                        visual_style_profile=self._visual_style_profile,
                    )
                    flow = flow_mgr.build()
                    os.makedirs(self.storyboards_dir, exist_ok=True)
                    flow_path = os.path.join(self.storyboards_dir, f"storyboard_flow_ep{ep:02d}.json")
                    flow_mgr.save(flow, flow_path)
                    print(f"   ✓ 两步分镜生成: {len(flow.shots)} 个镜头 → {flow_path}")

                if self.storyboard_mgr:
                    board = self.storyboard_mgr.generate_from_script(
                        script, episode_num=ep, drama_title=self.config.topic
                    )
                    if self._auto_approve:
                        self.storyboard_mgr.approve_all(board)
                    board_path = self.storyboard_mgr.save(board)
                    all_boards.append(board)
                    print(f"   ✓ 分镜生成: {len(board.scenes)} 个场景 → {board_path}")
                    print(f"   {self.storyboard_mgr.summary(board)}")

                # 3. 生成图片提示词
                if flow:
                    prompts = [s.keyframe_image_prompt for s in flow.shots]
                    video_prompts = [getattr(s, "motion_prompt", "") or s.video_prompt for s in flow.shots]
                    print(f"   ✓ STEP1图片提示词(人物/场景/构图合成): {len(prompts)} 个")
                    print(f"   ✓ STEP2运动提示词(用于I2V/T2V决策): {len(video_prompts)} 个")
                    media_result = await self._generate_media_from_flow(flow, episode_num=ep)
                    if flow_mgr and flow_path:
                        flow_mgr.save(flow, flow_path)
                elif self.prompt_builder:
                    prompts = self.prompt_builder.generate_scene_prompts(script)
                    video_prompts = []
                    media_result = {"keyframe_paths": [], "video_paths": [], "generated_shots": 0}
                else:
                    prompts = self._placeholder_prompts(script)
                    video_prompts = []
                    media_result = {"keyframe_paths": [], "video_paths": [], "generated_shots": 0}
                print(f"   ✓ 图片提示词: {len(prompts)} 个")
                composed_video_path = self._compose_episode_if_needed(
                    media_result.get("video_paths", []), episode_num=ep
                )
                post_prod_result = self._run_post_production_if_needed(
                    episode_num=ep,
                    script_text=script,
                    storyboard_flow_path=flow_path,
                    clip_paths=media_result.get("video_paths", []),
                    emotion_tags=self._collect_emotion_tags(flow),
                )
                if post_prod_result.get("final_path"):
                    composed_video_path = post_prod_result["final_path"]

                self.episodes_data.append({
                    "episode_num": ep,
                    "script": script,
                    "image_prompts": prompts,
                    "video_prompts": video_prompts,
                    "keyframe_paths": media_result.get("keyframe_paths", []),
                    "video_paths": media_result.get("video_paths", []),
                    "generated_shots": media_result.get("generated_shots", 0),
                    "composed_video_path": composed_video_path,
                    "timeline_path": post_prod_result.get("timeline_path"),
                    "voice_plan_path": post_prod_result.get("voice_plan_path"),
                    "music_plan_path": post_prod_result.get("music_plan_path"),
                    "voice_track_path": post_prod_result.get("voice_track_path"),
                    "bgm_track_path": post_prod_result.get("bgm_track_path"),
                    "storyboard_id": board.storyboard_id if board else None,
                    "storyboard_flow_path": flow_path,
                })
                if composed_video_path:
                    episode_final_paths.append(composed_video_path)
        finally:
            close_fn = getattr(self.script_gen, "close", None) if self.script_gen else None
            if close_fn:
                await close_fn()

        self.series_video_path = self._compose_series_if_needed(episode_final_paths)

        # 4. 保存结果
        output_file = self._save_results()
        print(f"\n💾 结果已保存: {output_file}")

        # 5. 素材统计
        if self.asset_mgr:
            stats = self.asset_mgr.stats()
            print(f"📦 素材库: {stats['total']} 个素材 ({stats['total_size_mb']} MB)")

        print(f"\n✅ 完成! 共 {len(self.episodes_data)} 集")
        return output_file

    async def _generate_media_from_flow(self, flow, episode_num: int) -> dict:
        """按两步分镜自动调用 Cozex + Jimeng 生成媒体文件。"""
        if not self._auto_generate_media:
            return {"keyframe_paths": [], "video_paths": [], "generated_shots": 0}

        if not flow or not flow.shots:
            return {"keyframe_paths": [], "video_paths": [], "generated_shots": 0}

        if not self.cozex_client:
            print("   ⚠️ Cozex 未启用，跳过自动关键帧生成")
            return {"keyframe_paths": [], "video_paths": [], "generated_shots": 0}

        keyframe_paths = []
        video_paths = []
        generated = 0
        loop = asyncio.get_running_loop()

        print(f"   ▶ 开始生成媒体: Episode {episode_num}")
        for i, shot in enumerate(flow.shots, 1):
            print(f"   [STEP1] {i}/{len(flow.shots)} {shot.shot_id}")
            try:
                image_result = await loop.run_in_executor(
                    None,
                    lambda p=shot.keyframe_image_prompt: self.cozex_client.generate_image(
                        prompt=p, size="1536x2560"
                    ),
                )
                shot.keyframe_image_path = image_result.get("saved_path")
                data_items = image_result.get("data") or []
                if data_items and isinstance(data_items[0], dict):
                    shot.keyframe_image_url = data_items[0].get("url")
                if shot.keyframe_image_path:
                    keyframe_paths.append(shot.keyframe_image_path)
            except Exception as e:
                print(f"     ✗ 关键帧失败: {e}")
                continue

            if not self.jimeng_client:
                continue

            print(f"   [STEP2] {i}/{len(flow.shots)} {shot.shot_id}")
            try:
                video_result, method_used, fallback_reason = await self._generate_video_for_shot(shot)
                shot.video_method = method_used
                shot.fallback_reason = fallback_reason
                shot.video_path = video_result.get("video_path") if video_result else None
                shot.video_task_id = video_result.get("task_id") if video_result else None
                shot.video_quality_score = self._quality_check_video(shot.video_path)
                print(
                    f"     ✓ method={shot.video_method} quality={shot.video_quality_score:.2f}"
                    + (f" fallback={shot.fallback_reason}" if shot.fallback_reason else "")
                )
                if shot.video_path:
                    video_paths.append(shot.video_path)
                    generated += 1
            except Exception as e:
                print(f"     ✗ 视频失败: {e}")

        print(f"   ✓ 媒体生成完成: keyframes={len(keyframe_paths)}, videos={len(video_paths)}")
        return {
            "keyframe_paths": keyframe_paths,
            "video_paths": video_paths,
            "generated_shots": generated,
        }

    async def _generate_video_for_shot(self, shot):
        """
        根据配置选择 i2v/t2v/auto 生成视频，并支持 i2v -> t2v fallback。
        返回: (result_dict_or_none, method_used, fallback_reason)
        """
        method = self._video_primary_method
        fallback_reason = ""

        continuity_hint = ""
        if getattr(shot, "continuity_state", None):
            continuity_hint = (
                f", continuity lock: {shot.continuity_state.get('identity_lock', '')}, "
                f"{shot.continuity_state.get('outfit_lock', '')}, "
                f"{shot.continuity_state.get('lighting_lock', '')}"
            )
        motion_prompt = getattr(shot, "motion_prompt", "") or getattr(shot, "video_prompt", "")
        i2v_prompt = f"{motion_prompt}{continuity_hint}"
        t2v_prompt = getattr(shot, "t2v_prompt", "") or self._build_t2v_prompt(shot)
        image_score = self._quality_check_image(getattr(shot, "keyframe_image_path", None))

        if method in ("i2v", "auto") and image_score < self._video_quality_threshold:
            fallback_reason = f"image_quality_low:{image_score:.2f}"
            if self._video_fallback_to_t2v:
                result = await self.jimeng_client.video_generation(
                    prompt=t2v_prompt,
                    resolution="720p",
                    aspect_ratio="9:16",
                    scene_prompt=t2v_prompt,
                    enforce_character_consistency=True,
                )
                return result, "t2v", fallback_reason

        # primary i2v / auto(i2v first)
        if method in ("i2v", "auto"):
            if not getattr(shot, "keyframe_image_url", None):
                fallback_reason = "missing_keyframe_url"
            else:
                try:
                    result = await self.jimeng_client.image_to_video(
                        image_url=shot.keyframe_image_url,
                        prompt=i2v_prompt,
                        aspect_ratio="9:16",
                    )
                    score = self._quality_check_video(result.get("video_path"))
                    if score >= self._video_quality_threshold:
                        return result, "i2v", ""
                    fallback_reason = f"i2v_quality_low:{score:.2f}"
                except Exception as e:
                    fallback_reason = f"i2v_error:{e}"

            if self._video_fallback_to_t2v:
                try:
                    result = await self.jimeng_client.video_generation(
                        prompt=t2v_prompt,
                        resolution="720p",
                        aspect_ratio="9:16",
                        scene_prompt=t2v_prompt,
                        enforce_character_consistency=True,
                    )
                    return result, "t2v", fallback_reason or "i2v_failed"
                except Exception as e:
                    raise RuntimeError(f"{fallback_reason}; t2v_error:{e}")

            raise RuntimeError(fallback_reason or "i2v_failed_no_fallback")

        # primary t2v
        if method == "t2v":
            result = await self.jimeng_client.video_generation(
                prompt=t2v_prompt,
                resolution="720p",
                aspect_ratio="9:16",
                scene_prompt=t2v_prompt,
                enforce_character_consistency=True,
            )
            return result, "t2v", ""

        raise RuntimeError(f"unsupported primary_method: {method}")

    def _build_t2v_prompt(self, shot) -> str:
        """构建更适合 T2V 的合成 prompt（避免直接无脑拼接过长文本）。"""
        parts = [
            getattr(shot, "keyframe_image_prompt", ""),
            getattr(shot, "motion_prompt", "") or getattr(shot, "video_prompt", ""),
            "cinematic lighting, smooth motion, coherent character identity, vertical 9:16, high quality",
        ]
        prompt = ", ".join([p for p in parts if p])
        # 简单长度控制，避免超长 prompt 影响稳定性
        return prompt[:1000]

    def _quality_check_video(self, video_path: Optional[str]) -> float:
        """
        轻量质量评分(0-1):
        - 存在性/大小
        - 时长下限
        - 分辨率下限
        """
        if not video_path or not os.path.exists(video_path):
            return 0.0
        try:
            size_bytes = os.path.getsize(video_path)
            size_score = 0.0 if size_bytes < 100_000 else min(1.0, size_bytes / 2_000_000)

            cmd = [
                "ffprobe", "-v", "quiet", "-print_format", "json",
                "-show_streams", "-show_format", video_path,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            data = json.loads(result.stdout or "{}")
            duration = float(data.get("format", {}).get("duration", 0) or 0)
            duration_score = 1.0 if duration >= 2.0 else duration / 2.0

            v_stream = None
            for s in data.get("streams", []):
                if s.get("codec_type") == "video":
                    v_stream = s
                    break
            if not v_stream:
                return 0.0
            width = int(v_stream.get("width", 0) or 0)
            height = int(v_stream.get("height", 0) or 0)
            pixel_score = 1.0 if width * height >= 640 * 360 else (width * height) / float(640 * 360)

            return max(0.0, min(1.0, 0.35 * size_score + 0.35 * duration_score + 0.30 * pixel_score))
        except Exception:
            return 0.3

    def _quality_check_image(self, image_path: Optional[str]) -> float:
        """轻量图像质量评分(0-1)，用于 i2v 前判断是否直接走 t2v。"""
        if not image_path or not os.path.exists(image_path):
            return 0.0
        try:
            size_bytes = os.path.getsize(image_path)
            size_score = 0.0 if size_bytes < 80_000 else min(1.0, size_bytes / 1_500_000)
            # 尝试用 ffprobe 获取分辨率（图片同样可读）
            cmd = [
                "ffprobe", "-v", "quiet", "-print_format", "json",
                "-show_streams", image_path,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            data = json.loads(result.stdout or "{}")
            v_stream = None
            for s in data.get("streams", []):
                if s.get("codec_type") == "video":
                    v_stream = s
                    break
            if not v_stream:
                return max(0.0, min(1.0, size_score))
            width = int(v_stream.get("width", 0) or 0)
            height = int(v_stream.get("height", 0) or 0)
            pixel_score = 1.0 if width * height >= 1024 * 1024 else (width * height) / float(1024 * 1024)
            return max(0.0, min(1.0, 0.45 * size_score + 0.55 * pixel_score))
        except Exception:
            return 0.4

    def _compose_episode_if_needed(self, video_paths: List[str], episode_num: int) -> Optional[str]:
        """有视频片段时，自动合成单集成片。"""
        if not self._auto_compose_episode:
            return None
        if not self.composer:
            print("   ⚠️ VideoComposer 不可用，跳过自动合成")
            return None

        valid = [p for p in video_paths if p and os.path.exists(p)]
        if not valid:
            print("   ⚠️ 无有效视频片段，跳过自动合成")
            return None

        output_path = os.path.join(self.config.output_dir, f"episode_{episode_num:02d}_final.mp4")
        old_output = self.composer.config.output_path
        self.composer.config.output_path = output_path
        try:
            clips = [VideoClip(path=p) for p in valid]
            final = self.composer.compose(clips)
            print(f"   ✓ 单集合成完成: {final}")
            return final
        except Exception as e:
            print(f"   ✗ 单集合成失败: {e}")
            return None
        finally:
            self.composer.config.output_path = old_output

    def _run_post_production_if_needed(
        self,
        episode_num: int,
        script_text: str,
        storyboard_flow_path: Optional[str],
        clip_paths: List[str],
        emotion_tags: Optional[List[str]] = None,
    ) -> dict:
        """执行升级版后期导演流程（步骤6）。"""
        if not self.post_director:
            return {}
        if not storyboard_flow_path or not os.path.exists(storyboard_flow_path):
            print("   ⚠️ 缺少 storyboard.json，跳过 Post-Production Director")
            return {}
        if not clip_paths:
            print("   ⚠️ 无视频片段，跳过 Post-Production Director")
            return {}

        print("   ▶ STEP6_POST_PRODUCTION_DIRECTOR")
        try:
            result = self.post_director.run(
                episode_num=episode_num,
                script_text=script_text,
                storyboard_json_path=storyboard_flow_path,
                clip_paths=clip_paths,
                output_dir=self.config.output_dir,
                emotion_tags=emotion_tags,
            )
            final_path = result.get("final_path")
            if final_path:
                print(f"   ✓ Post-Production 完成: {final_path}")
            return result
        except Exception as e:
            print(f"   ✗ Post-Production 失败: {e}")
            return {}

    def _collect_emotion_tags(self, flow) -> List[str]:
        if not flow or not getattr(flow, "shots", None):
            return []
        tags = []
        for shot in flow.shots:
            mood = ""
            if getattr(shot, "continuity_state", None):
                mood = shot.continuity_state.get("mood_lock", "")
            tags.append(mood)
        return tags

    def _compose_series_if_needed(self, episode_video_paths: List[str]) -> Optional[str]:
        """将每集成片拼接为总成片。"""
        if not self._auto_compose_series:
            return None
        if not self.composer:
            print("⚠️ VideoComposer 不可用，跳过全集合成")
            return None

        valid = [p for p in episode_video_paths if p and os.path.exists(p)]
        if not valid:
            print("⚠️ 无可用单集成片，跳过全集合成")
            return None

        output_path = os.path.join(self.config.output_dir, "series_final.mp4")
        old_output = self.composer.config.output_path
        self.composer.config.output_path = output_path
        try:
            clips = [VideoClip(path=p) for p in valid]
            final = self.composer.compose(clips)
            print(f"\n🎞️ 全集成片完成: {final}")
            return final
        except Exception as e:
            print(f"\n✗ 全集合成失败: {e}")
            return None
        finally:
            self.composer.config.output_path = old_output

    def compose_video(self, video_paths: List[str], bgm_path: str = None,
                      voiceover_path: str = None) -> Optional[str]:
        """合成最终视频"""
        if not self.composer:
            print("⚠️  VideoComposer 不可用（FFmpeg 未安装）")
            return None

        if bgm_path:
            self.composer.config.bgm_path = bgm_path
        if voiceover_path:
            self.composer.config.voiceover_path = voiceover_path

        clips = [VideoClip(path=p) for p in video_paths]
        return self.composer.compose(clips)

    def images_to_video(self, image_paths: List[str], duration_each: float = 3.0,
                        output_path: str = None) -> Optional[str]:
        """图片序列转视频"""
        if not self.composer:
            print("⚠️  VideoComposer 不可用")
            return None
        return self.composer.images_to_video(image_paths, duration_each, output_path)

    def _placeholder_script(self, ep: int) -> str:
        return f"""第{ep}集

场景1: [开场]
对话: 主人公醒来，发现自己在一个陌生的房间...

场景2: [发展]
对话: 这时，门突然打开了...

场景3: [高潮]
对话: 原来一切都是命中注定！

场景4: [结尾]
对话: 敬请期待下一集！
"""

    def _placeholder_prompts(self, script: str) -> List[str]:
        scenes = script.split("场景")
        return [
            f"cinematic scene {i}, dramatic lighting, high quality, 8k, vertical 9:16"
            for i in range(1, len(scenes))
        ]

    def _save_results(self) -> str:
        path = os.path.join(
            self.config.output_dir,
            f"drama_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        with open(path, "w", encoding="utf-8") as f:
            json.dump({
                "config": asdict(self.config),
                "episodes": self.episodes_data,
                "series_video_path": self.series_video_path,
            }, f, ensure_ascii=False, indent=2)
        return path


# ── CLI ──────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="AI Short Drama Automator - 一句话生成完整短剧",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python main.py generate --topic "重生千金复仇记" --style 情感 --episodes 5
  python main.py storyboard --script script.txt --episode 1
  python main.py compose --videos clip1.mp4 clip2.mp4 --bgm music.mp3
  python main.py assets --list
  python main.py assets --import photo.jpg --tags "角色,主角" --category characters
        """
    )
    sub = p.add_subparsers(dest="command")

    # generate
    gen = sub.add_parser("generate", help="生成短剧剧本和分镜")
    gen.add_argument("--topic", required=True, help="短剧主题")
    gen.add_argument("--style", default="情感", choices=["情感", "悬疑", "搞笑", "科幻"], help="风格")
    gen.add_argument("--episodes", type=int, default=3, help="集数")
    gen.add_argument("--output", default="output", help="输出目录")
    gen.add_argument("--config", default="config.yaml", help="配置文件路径")
    gen.add_argument("--auto-approve", action="store_true", help="自动审批所有分镜")

    # storyboard
    sb = sub.add_parser("storyboard", help="从剧本生成分镜")
    sb.add_argument("--script", required=True, help="剧本文件路径")
    sb.add_argument("--episode", type=int, default=1, help="集数")
    sb.add_argument("--title", default="", help="剧名")
    sb.add_argument("--approve-all", action="store_true", help="生成后自动审批")

    # compose
    comp = sub.add_parser("compose", help="合成视频")
    comp.add_argument("--videos", nargs="+", required=True, help="视频片段路径列表")
    comp.add_argument("--bgm", help="背景音乐路径")
    comp.add_argument("--voiceover", help="配音文件路径")
    comp.add_argument("--output", default="output/final.mp4", help="输出路径")
    comp.add_argument("--transition", default="fade",
                      choices=["none", "fade", "dissolve", "slideleft", "slideright", "wipe"])

    # images2video
    i2v = sub.add_parser("images2video", help="图片序列转视频")
    i2v.add_argument("--images", nargs="+", required=True, help="图片路径列表")
    i2v.add_argument("--duration", type=float, default=3.0, help="每张图片时长(秒)")
    i2v.add_argument("--output", default="output/slideshow.mp4", help="输出路径")

    # assets
    ast = sub.add_parser("assets", help="素材库管理")
    ast.add_argument("--list", action="store_true", help="列出所有素材")
    ast.add_argument("--import", dest="import_file", help="导入素材文件")
    ast.add_argument("--tags", default="", help="标签（逗号分隔）")
    ast.add_argument("--category", default="uncategorized", help="分类")
    ast.add_argument("--stats", action="store_true", help="显示素材统计")

    return p


async def cmd_generate(args, app_config: dict):
    app_config.setdefault("storyboard", {})["auto_approve"] = args.auto_approve

    api_config = load_api_config()
    anthropic_key = api_config.get("script", {}).get("custom_opus", {}).get("api_key")

    config = DramaConfig(
        topic=args.topic,
        style=args.style,
        episodes=args.episodes,
        output_dir=args.output,
        anthropic_api_key=anthropic_key,
    )
    automator = ShortDramaAutomator(config, app_config)
    await automator.run()


def cmd_storyboard(args):
    if not StoryboardManager:
        print("❌ StoryboardManager 不可用")
        return
    with open(args.script, encoding="utf-8") as f:
        script = f.read()
    mgr = StoryboardManager()
    board = mgr.generate_from_script(script, episode_num=args.episode, drama_title=args.title)
    if args.approve_all:
        mgr.approve_all(board)
    path = mgr.save(board)
    print(mgr.summary(board))
    print(f"💾 分镜已保存: {path}")


def cmd_compose(args):
    if not VideoComposer:
        print("❌ VideoComposer 不可用")
        return
    cfg = CompositionConfig(
        output_path=args.output,
        bgm_path=args.bgm,
        voiceover_path=args.voiceover,
    )
    composer = VideoComposer(cfg)
    clips = [VideoClip(path=p, transition=TransitionType(args.transition)) for p in args.videos]
    result = composer.compose(clips)
    print(f"🎬 视频已合成: {result}")


def cmd_images2video(args):
    if not VideoComposer:
        print("❌ VideoComposer 不可用")
        return
    cfg = CompositionConfig(output_path=args.output)
    composer = VideoComposer(cfg)
    result = composer.images_to_video(args.images, args.duration, args.output)
    print(f"🎬 幻灯片视频: {result}")


def cmd_assets(args):
    if not AssetManager:
        print("❌ AssetManager 不可用")
        return
    mgr = AssetManager()
    if args.stats:
        print(json.dumps(mgr.stats(), ensure_ascii=False, indent=2))
    elif args.list:
        assets = mgr.list_all()
        if not assets:
            print("素材库为空")
        for a in assets:
            print(f"[{a.asset_id}] {a.asset_type.value:6s} {a.name:30s} tags={a.tags} cat={a.category}")
    elif args.import_file:
        tags = [t.strip() for t in args.tags.split(",") if t.strip()]
        asset = mgr.import_file(args.import_file, tags=tags, category=args.category)
        print(f"✅ 已导入: [{asset.asset_id}] {asset.name}")


def main():
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        # 无参数时运行默认示例
        app_config = load_config()
        config = DramaConfig(topic="重生千金复仇记", style="情感", episodes=3)
        automator = ShortDramaAutomator(config, app_config)
        asyncio.run(automator.run())
        return

    app_config = load_config(getattr(args, "config", "config.yaml"))

    if args.command == "generate":
        asyncio.run(cmd_generate(args, app_config))
    elif args.command == "storyboard":
        cmd_storyboard(args)
    elif args.command == "compose":
        cmd_compose(args)
    elif args.command == "images2video":
        cmd_images2video(args)
    elif args.command == "assets":
        cmd_assets(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
