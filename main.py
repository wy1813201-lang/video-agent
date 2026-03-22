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
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, asdict

import yaml

# 项目根目录
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

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
    from src.character_master import CharacterMasterRegistry
except ImportError:
    CharacterMasterRegistry = None

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
    from src.image_url_bridge import ImageUrlBridge
except ImportError:
    ImageUrlBridge = None

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
    from src.voice_generator import VoiceGenerator
except ImportError:
    VoiceGenerator = None

try:
    from src.subtitle_generator import SubtitleGenerator
except ImportError:
    SubtitleGenerator = None

try:
    from src.video_assembler import VideoAssembler
except ImportError:
    VideoAssembler = None

try:
    from src.retry_utils import retry_async
except ImportError:
    from retry_utils import retry_async

try:
    from src.meta_director import MetaDirector, DecisionType, ContentType
except ImportError:
    MetaDirector = None

try:
    from src.task_state_manager import TaskStateManager, TaskStage
except ImportError:
    TaskStateManager = None

try:
    from src.experiment_engine import ExperimentEngine, ExperimentParamsGenerator
except ImportError:
    ExperimentEngine = None

try:
    from src.human_selector import HumanSelector
except ImportError:
    HumanSelector = None


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
        
        # 配音配置
        voice_cfg = self.app_config.get("voice", {})
        self._voice_enabled = bool(voice_cfg.get("enabled", False))
        self._voice_provider = str(voice_cfg.get("provider", "edge"))
        self._voice_default = str(voice_cfg.get("default_voice", "xiaoxiao"))
        
        # 字幕配置
        subtitle_cfg = self.app_config.get("subtitle", {})
        self._subtitle_enabled = bool(subtitle_cfg.get("enabled", False))
        self._subtitle_from_audio = bool(subtitle_cfg.get("from_audio", False))
        self._visual_style_profile = str(storyboard_cfg.get("visual_style_profile", "anime"))
        
        # 审核界面配置
        self._review_ui_enabled = bool(storyboard_cfg.get("review_ui_enabled", True))
        self._review_ui_port = int(storyboard_cfg.get("review_ui_port", 8501))
        self._review_ui_auto_open = bool(storyboard_cfg.get("review_ui_auto_open", True))
        self._video_primary_method = str(video_gen_cfg.get("primary_method", "i2v")).lower()
        self._video_fallback_to_t2v = bool(video_gen_cfg.get("fallback_to_t2v", True))
        self._video_quality_threshold = float(video_gen_cfg.get("quality_threshold", 0.6))
        pipeline_cfg = self.app_config.get("pipeline", {})
        self._max_concurrent_shots = int(pipeline_cfg.get("max_concurrent_shots", 2))
        self._retry_max_attempts = int(pipeline_cfg.get("retry_max_attempts", 3))
        self._retry_base_delay_sec = float(pipeline_cfg.get("retry_base_delay_sec", 2.0))
        qa_cfg = pipeline_cfg.get("qa", {})
        self._qa_enabled = bool(qa_cfg.get("enabled", True))
        self._qa_min_video_score = float(qa_cfg.get("min_video_score", 0.6))
        self._story_bible_enabled = bool(story_bible_cfg.get("enabled", True))
        self._story_bible_path = str(story_bible_cfg.get("path", "data/story_bible.json"))
        
        # 角色母版配置
        character_master_cfg = self.app_config.get("character_master", {})
        self._character_master_enabled = bool(character_master_cfg.get("enabled", True))
        self._character_master_path = str(character_master_cfg.get("path", "data/character_masters"))
        self._character_master_auto_generate = bool(character_master_cfg.get("auto_generate_images", False))
        self.character_registry: Optional[Any] = None  # 运行时注册表

        image_cfg = api_config.get("image", {}).get("cozex", {})
        video_cfg_api = api_config.get("video", {}).get("jimeng", {})
        self._cozex_enabled = bool(image_cfg.get("enabled"))
        self._jimeng_enabled = bool(video_cfg_api.get("enabled"))
        self.cozex_client = CozexClient() if (self._cozex_enabled and CozexClient) else None
        self.jimeng_clients: List[Any] = []
        if self._jimeng_enabled and JimengVideoClient:
            pool = video_cfg_api.get("account_pool", [])
            if isinstance(pool, list) and pool:
                for acc in pool:
                    if not isinstance(acc, dict):
                        continue
                    merged = dict(video_cfg_api)
                    merged.update({
                        "access_key": acc.get("access_key", merged.get("access_key", "")),
                        "secret_key": acc.get("secret_key", merged.get("secret_key", "")),
                    })
                    self.jimeng_clients.append(JimengVideoClient(cfg_override=merged))
            else:
                self.jimeng_clients.append(JimengVideoClient())
        self._jimeng_rr_index = 0
        self.jimeng_client = self.jimeng_clients[0] if self.jimeng_clients else None
        bridge_cfg = video_cfg_api.get("image_url_bridge", {})
        self.image_url_bridge = ImageUrlBridge(config=bridge_cfg) if ImageUrlBridge else None
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

        # Meta Director（老板 Agent）
        meta_director_cfg = self.app_config.get("meta_director", {})
        self._enable_meta_director = bool(meta_director_cfg.get("enabled", False))
        self.meta_director = None
        self.experiment_engine = None
        if self._enable_meta_director and MetaDirector:
            self.meta_director = MetaDirector(meta_director_cfg)
            if ExperimentEngine:
                self.experiment_engine = ExperimentEngine()
            print("✓ Meta Director 已启用")

    async def run(self) -> str:
        print(f"\n🎬 AI短剧自动生成器 v2.0")
        print(f"   主题: {self.config.topic} | 风格: {self.config.style} | 集数: {self.config.episodes}")
        print("=" * 60)

        # 初始化任务状态管理
        self.task_state = None
        if TaskStateManager:
            self.task_state = TaskStateManager(self.config.topic.replace(" ", "_"))
            
            # 检查是否可以续传
            if self.task_state.can_resume():
                resume_point = self.task_state.get_resume_point()
                print(f"\n🔄 检测到未完成任务，将从以下位置继续：")
                print(f"   集数: 第 {resume_point.get('episode', 1)} 集")
                print(f"   阶段: {resume_point.get('stage', 'start')}")
            else:
                # 初始化新任务
                self.task_state.init(self.config.topic, self.config.episodes)
                print(f"✓ 任务状态已初始化")
        
        # 开始任务
        start_episode = 1
        
        all_boards = []
        episode_final_paths: List[str] = []

        # Meta Director: 开始生产记录
        if self.meta_director:
            self.meta_director.start_production(self.config.topic, 1)

        try:
            for ep in range(start_episode, self.config.episodes + 1):
                # 开始新一集
                if self.task_state:
                    self.task_state.start_episode(ep)
                
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
                
                # 保存任务状态
                if self.task_state:
                    self.task_state.complete_stage(TaskStage.SCRIPT.value, data={"script": script[:500]}, episode=ep)

                # Meta Director: 审核剧本
                if self.meta_director:
                    decision = self.meta_director.review_script(script)
                    print(f"\n   🎯 [Meta Director] 剧本审核")
                    print(f"      决策: {decision.decision_type.value}")
                    print(f"      评分: {decision.score.overall:.1f}/10")
                    print(f"      理由: {decision.reason}")

                    if decision.decision_type == DecisionType.REJECT:
                        print(f"      ❌ 剧本未通过，需要重新生成")
                        # TODO: 实现重新生成逻辑
                        continue
                    elif decision.decision_type == DecisionType.EXPERIMENT:
                        print(f"      🧪 触发实验模式，生成多个版本")

                        # 生成实验版本
                        if self.experiment_engine and self.script_gen:
                            script = await self._run_script_experiment(script, ep)
                        else:
                            print(f"      ⚠️ 实验引擎未启用，使用原版本")

                if self.story_bible:
                    try:
                        self.story_bible.update_after_episode(ep, script)
                        print("   ✓ Story Bible 已更新")
                    except Exception as e:
                        print(f"   ⚠️ Story Bible 更新失败: {e}")

                # 2. 创建角色母版 (Character Master)
                if self._character_master_enabled:
                    await self._create_character_masters(script, ep)

                # 3. 生成分镜
                board = None
                flow = None
                flow_path = None

                flow_mgr = None
                if self._use_two_step_flow and StoryboardFlowManager:
                    flow_mgr = StoryboardFlowManager(
                        script,
                        use_gemini=self._two_step_use_gemini,
                        visual_style_profile=self._visual_style_profile,
                        character_registry=self.character_registry,  # 传递角色母版注册表
                    )
                    flow = flow_mgr.build()
                    os.makedirs(self.storyboards_dir, exist_ok=True)
                    flow_path = os.path.join(self.storyboards_dir, f"storyboard_flow_ep{ep:02d}.json")
                    flow_mgr.save(flow, flow_path)
                    print(f"   ✓ 两步分镜生成: {len(flow.shots)} 个镜头 → {flow_path}")
                    
                    # 保存任务状态
                    if self.task_state:
                        self.task_state.complete_stage(TaskStage.STORYBOARD.value, 
                            data={"shots_count": len(flow.shots), "flow_path": flow_path}, episode=ep)

                    # Meta Director: 审核分镜
                    if self.meta_director and flow_path:
                        with open(flow_path, 'r', encoding='utf-8') as f:
                            storyboard_data = json.load(f)
                        decision = self.meta_director.review_storyboard(storyboard_data)
                        print(f"\n   🎯 [Meta Director] 分镜审核")
                        print(f"      决策: {decision.decision_type.value}")
                        print(f"      评分: {decision.score.overall:.1f}/10")
                        print(f"      理由: {decision.reason}")

                        if decision.decision_type == DecisionType.REJECT:
                            print(f"      ❌ 分镜未通过，需要重新生成")
                            # TODO: 实现重新生成逻辑

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
                    
                    # 保存分镜文件后再审核
                    if flow_mgr and flow_path:
                        flow_mgr.save(flow, flow_path)
                    
                    # 审核界面：等待用户确认
                    if self._review_ui_enabled and flow_path:
                        review_result = await self._wait_for_review(flow_path, episode_num)
                        
                        # 如果用户拒绝，根据反馈重新生成
                        max_retries = 3
                        retry_count = 0
                        while review_result.get("result") == "rejected" and retry_count < max_retries:
                            retry_count += 1
                            feedback = review_result.get("reason", "")
                            print(f"\n   🔁 第 {retry_count} 次重试...")
                            
                            # 重新生成
                            script, flow, new_flow_path = await self._regenerate_with_feedback(
                                script, episode_num, feedback
                            )
                            
                            if new_flow_path:
                                flow_path = new_flow_path
                            
                            # 再次等待审核
                            if self._review_ui_enabled:
                                review_result = await self._wait_for_review(flow_path, episode_num)
                            else:
                                break
                        
                        if review_result.get("result") == "rejected" and retry_count >= max_retries:
                            print(f"      ⚠️ 已达到最大重试次数 ({max_retries})，跳过本集")
                            continue
                    
                    # 重新加载审核后的分镜
                    if flow_path and os.path.exists(flow_path):
                        with open(flow_path, 'r', encoding='utf-8') as f:
                            flow_data = json.load(f)
                        # 更新 flow 对象
                        if "shots" in flow_data:
                            for i, shot_data in enumerate(flow_data["shots"]):
                                if i < len(flow.shots):
                                    flow.shots[i].keyframe_image_prompt = shot_data.get("keyframe_image_prompt", flow.shots[i].keyframe_image_prompt)
                                    flow.shots[i].keyframe_image_path = shot_data.get("keyframe_image_path")
                                    flow.shots[i].keyframe_image_url = shot_data.get("keyframe_image_url")
                    
                    media_result = await self._generate_media_from_flow(flow, episode_num=ep)
                elif self.prompt_builder:
                    prompts = self.prompt_builder.generate_scene_prompts(script)
                    video_prompts = []
                    media_result = {"keyframe_paths": [], "video_paths": [], "generated_shots": 0}
                else:
                    prompts = self._placeholder_prompts(script)
                    video_prompts = []
                    media_result = {"keyframe_paths": [], "video_paths": [], "generated_shots": 0}
                print(f"   ✓ 图片提示词: {len(prompts)} 个")
                
                # 保存关键帧状态
                if self.task_state and media_result.get("keyframe_paths"):
                    self.task_state.complete_stage(TaskStage.KEYFRAME.value, 
                        data={"keyframes": len(media_result.get("keyframe_paths", []))}, episode=ep)
                
                composed_video_path = self._compose_episode_if_needed(
                    media_result.get("video_paths", []), episode_num=ep
                )
                
                # 生成配音（可选）
                voice_track_path = None
                subtitle_path = None
                if self._voice_enabled and composed_video_path:
                    voice_track_path = await self._generate_voiceover(script, composed_video_path, ep)
                
                # 生成字幕（可选）
                if self._subtitle_enabled and voice_track_path:
                    subtitle_path = await self._generate_subtitles(voice_track_path, ep)
                
                # 如果有配音或字幕，重新合成视频
                if (voice_track_path or subtitle_path) and composed_video_path:
                    composed_video_path = self._compose_with_audio(
                        composed_video_path,
                        voice_path=voice_track_path,
                        subtitle_path=subtitle_path,
                        episode_num=ep
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
                    "voice_casting_path": post_prod_result.get("voice_casting_path"),
                    "voice_plan_path": post_prod_result.get("voice_plan_path"),
                    "music_plan_path": post_prod_result.get("music_plan_path"),
                    "voice_track_path": post_prod_result.get("voice_track_path"),
                    "bgm_track_path": post_prod_result.get("bgm_track_path"),
                    "storyboard_id": board.storyboard_id if board else None,
                    "storyboard_flow_path": flow_path,
                })
                if composed_video_path:
                    episode_final_paths.append(composed_video_path)
                
                # 保存本集完成状态
                if self.task_state:
                    self.task_state.complete_stage(TaskStage.FINAL.value, 
                        data={"output_path": composed_video_path}, episode=ep)
        finally:
            close_fn = getattr(self.script_gen, "close", None) if self.script_gen else None
            if close_fn:
                await close_fn()

        self.series_video_path = self._compose_series_if_needed(episode_final_paths)

        # 4. 保存结果
        output_file = self._save_results()
        print(f"\n💾 结果已保存: {output_file}")

        # Meta Director: 保存生产记录
        if self.meta_director:
            self.meta_director.save_record()
            print(f"📊 Meta Director 生产记录已保存")

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

        keyframe_paths: List[str] = []
        video_paths: List[str] = []
        generated = 0
        loop = asyncio.get_running_loop()
        semaphore = asyncio.Semaphore(max(1, self._max_concurrent_shots))

        print(f"   ▶ 开始生成媒体: Episode {episode_num}")
        async def process_shot(i, shot):
            nonlocal generated
            async with semaphore:
                print(f"   [STEP1] {i}/{len(flow.shots)} {shot.shot_id}")
                try:
                    image_result = await retry_async(
                        lambda: loop.run_in_executor(
                            None,
                            lambda p=shot.keyframe_image_prompt: self.cozex_client.generate_image(
                                prompt=p, size="1536x2560"
                            ),
                        ),
                        max_attempts=self._retry_max_attempts,
                        base_delay_sec=self._retry_base_delay_sec,
                        on_retry=lambda n, e, s: print(
                            f"     ↻ 关键帧重试#{n+1} in {s:.1f}s: {e}"
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
                    return

                if not self.jimeng_client:
                    return

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

        await asyncio.gather(*(process_shot(i, shot) for i, shot in enumerate(flow.shots, 1)))

        print(f"   ✓ 媒体生成完成: keyframes={len(keyframe_paths)}, videos={len(video_paths)}")
        return {
            "keyframe_paths": keyframe_paths,
            "video_paths": video_paths,
            "generated_shots": generated,
        }

    def _ensure_public_image_url(self, image_path_or_url: str) -> str:
        if not image_path_or_url:
            return ""
        if image_path_or_url.startswith(("http://", "https://")):
            return image_path_or_url
        if not self.image_url_bridge:
            raise RuntimeError("image_url_bridge unavailable")
        return self.image_url_bridge.ensure_public_url(image_path_or_url)

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
                client = self._next_jimeng_client()
                result = await retry_async(
                    lambda: client.video_generation(
                        prompt=t2v_prompt,
                        resolution="720p",
                        aspect_ratio="9:16",
                        scene_prompt=t2v_prompt,
                        enforce_character_consistency=True,
                    ),
                    max_attempts=self._retry_max_attempts,
                    base_delay_sec=self._retry_base_delay_sec,
                )
                return result, "t2v", fallback_reason

        # primary i2v / auto(i2v first)
        if method in ("i2v", "auto"):
            if not getattr(shot, "keyframe_image_url", None) and getattr(shot, "keyframe_image_path", None):
                try:
                    shot.keyframe_image_url = self._ensure_public_image_url(shot.keyframe_image_path)
                except Exception as e:
                    fallback_reason = f"image_url_bridge_error:{e}"

            if not getattr(shot, "keyframe_image_url", None):
                fallback_reason = fallback_reason or "missing_keyframe_url"
            else:
                try:
                    client = self._next_jimeng_client()
                    result = await retry_async(
                        lambda: client.image_to_video(
                            image_url=shot.keyframe_image_url,
                            prompt=i2v_prompt,
                            aspect_ratio="9:16",
                        ),
                        max_attempts=self._retry_max_attempts,
                        base_delay_sec=self._retry_base_delay_sec,
                        on_retry=lambda n, e, s: print(
                            f"     ↻ i2v重试#{n+1} in {s:.1f}s: {e}"
                        ),
                    )
                    score = self._quality_check_video(result.get("video_path"))
                    if self._qa_enabled:
                        qa_ok, qa_reason = self._qa_video_gate(result.get("video_path"), score)
                    else:
                        qa_ok, qa_reason = True, ""
                    if qa_ok and score >= self._video_quality_threshold:
                        return result, "i2v", ""
                    fallback_reason = qa_reason or f"i2v_quality_low:{score:.2f}"
                except Exception as e:
                    fallback_reason = f"i2v_error:{e}"

            if self._video_fallback_to_t2v:
                try:
                    client = self._next_jimeng_client()
                    result = await retry_async(
                        lambda: client.video_generation(
                            prompt=t2v_prompt,
                            resolution="720p",
                            aspect_ratio="9:16",
                            scene_prompt=t2v_prompt,
                            enforce_character_consistency=True,
                        ),
                        max_attempts=self._retry_max_attempts,
                        base_delay_sec=self._retry_base_delay_sec,
                        on_retry=lambda n, e, s: print(
                            f"     ↻ t2v重试#{n+1} in {s:.1f}s: {e}"
                        ),
                    )
                    score = self._quality_check_video(result.get("video_path"))
                    if self._qa_enabled:
                        qa_ok, qa_reason = self._qa_video_gate(result.get("video_path"), score)
                        if not qa_ok:
                            raise RuntimeError(qa_reason)
                    return result, "t2v", fallback_reason or "i2v_failed"
                except Exception as e:
                    raise RuntimeError(f"{fallback_reason}; t2v_error:{e}")

            raise RuntimeError(fallback_reason or "i2v_failed_no_fallback")

        # primary t2v
        if method == "t2v":
            client = self._next_jimeng_client()
            result = await retry_async(
                lambda: client.video_generation(
                    prompt=t2v_prompt,
                    resolution="720p",
                    aspect_ratio="9:16",
                    scene_prompt=t2v_prompt,
                    enforce_character_consistency=True,
                ),
                max_attempts=self._retry_max_attempts,
                base_delay_sec=self._retry_base_delay_sec,
                on_retry=lambda n, e, s: print(
                    f"     ↻ t2v重试#{n+1} in {s:.1f}s: {e}"
                ),
            )
            if self._qa_enabled:
                score = self._quality_check_video(result.get("video_path"))
                qa_ok, qa_reason = self._qa_video_gate(result.get("video_path"), score)
                if not qa_ok:
                    raise RuntimeError(qa_reason)
            return result, "t2v", ""

        raise RuntimeError(f"unsupported primary_method: {method}")

    def _next_jimeng_client(self):
        """账号池轮询：降低单账号限流冲击。"""
        if not self.jimeng_clients:
            return self.jimeng_client
        client = self.jimeng_clients[self._jimeng_rr_index % len(self.jimeng_clients)]
        self._jimeng_rr_index += 1
        return client

    def _qa_video_gate(self, video_path: Optional[str], score: float):
        """
        自动 QA 节点：
        - 分数低于阈值直接判废
        - 黑帧比例过高判废
        """
        if score < self._qa_min_video_score:
            return False, f"qa_score_low:{score:.2f}"
        if not video_path or not os.path.exists(video_path):
            return False, "qa_missing_video"
        black_ratio = self._estimate_black_ratio(video_path)
        if black_ratio >= 0.85:
            return False, f"qa_black_frames:{black_ratio:.2f}"
        return True, ""

    def _estimate_black_ratio(self, video_path: str) -> float:
        """
        使用 ffmpeg blackdetect 粗估黑帧占比。
        """
        cmd = [
            "ffmpeg", "-hide_banner", "-i", video_path,
            "-vf", "blackdetect=d=0.1:pic_th=0.98:pix_th=0.10",
            "-an", "-f", "null", "-"
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            text = (result.stderr or "") + "\n" + (result.stdout or "")
            total = self._probe_video_duration(video_path)
            if total <= 0:
                return 0.0
            black = 0.0
            for line in text.splitlines():
                if "black_duration:" in line:
                    seg = line.split("black_duration:")[-1].strip().split()[0]
                    black += float(seg)
            return max(0.0, min(1.0, black / total))
        except Exception:
            return 0.0

    def _probe_video_duration(self, video_path: str) -> float:
        cmd = [
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_format", video_path,
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            data = json.loads(result.stdout or "{}")
            return float(data.get("format", {}).get("duration", 0.0) or 0.0)
        except Exception:
            return 0.0

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

    async def _create_character_masters(self, script: str, episode_num: int) -> None:
        """
        创建角色母版
        
        只在第一集时创建，后续集复用同一个注册表
        """
        if episode_num > 1 and self.character_registry:
            # 后续集复用已有角色
            print(f"   ✓ 复用已有角色母版: {len(self.character_registry.list_all())} 个")
            return
        
        if not CharacterMasterRegistry:
            print("   ⚠️ CharacterMasterRegistry 不可用")
            return
        
        try:
            # 动态导入避免循环依赖
            from src.character_description_generator import create_character_masters_from_script
            
            api_config = load_api_config()
            
            # 创建角色母版
            self.character_registry = await create_character_masters_from_script(
                script=script,
                api_config=api_config,
                output_dir=self._character_master_path
            )
            
            count = len(self.character_registry.list_all())
            print(f"   ✓ 角色母版已创建: {count} 个")
            
            # 可选：生成三视图/表情图
            if self._character_master_auto_generate and self.cozex_client and count > 0:
                await self._generate_character_reference_images()
                
        except Exception as e:
            print(f"   ⚠️ 角色母版创建失败: {e}")
            # 不中断流程，继续使用原有逻辑
    
    async def _generate_character_reference_images(self) -> None:
        """生成角色参考图（三视图 + 表情图）"""
        if not self.character_registry or not self.cozex_client:
            return
        
        print("   ▶ 生成角色参考图（三视图 + 表情）...")
        
        for master in self.character_registry.list_all():
            try:
                # 生成三视图
                view_prompts = master.build_view_prompts()
                for view_name, prompt in view_prompts.items():
                    # TODO: 调用 CoZex 生成
                    print(f"      {master.name}.{view_name}: 待生成")
                
                # 生成表情图
                expr_prompts = master.build_expression_prompts()
                for expr_name, prompt in expr_prompts.items():
                    print(f"      {master.name}.{expr_name}: 待生成")
                    
            except Exception as e:
                print(f"   ⚠️ {master.name} 参考图生成失败: {e}")

    async def _generate_voiceover(self, script: str, video_path: str, episode_num: int) -> Optional[str]:
        """
        生成配音
        
        Args:
            script: 剧本文本
            video_path: 视频路径（用于获取时长）
            episode_num: 集数
            
        Returns:
            配音文件路径
        """
        if not VoiceGenerator:
            print("   ⚠️ VoiceGenerator 不可用")
            return None
        
        try:
            # 从剧本提取对话
            dialogues = self._extract_dialogues_from_script(script)
            
            if not dialogues:
                print("   ⚠️ 未提取到对话，跳过配音生成")
                return None
            
            print(f"   ▶ 生成配音: {len(dialogues)} 段对话")
            
            # 加载 API 配置
            api_config = load_api_config()
            voice_gen = VoiceGenerator(api_config)
            
            # 角色声音映射
            voice_map = self.app_config.get("voice", {}).get("character_voices", {
                "女主": "xiaoxiao",
                "男主": "yunxi",
                "女": "xiaoyi",
                "男": "yunyang",
            })
            
            output_dir = os.path.join(self.config.output_dir, "audio")
            os.makedirs(output_dir, exist_ok=True)
            
            # 逐段生成配音
            audio_paths = []
            for i, dialog in enumerate(dialogues):
                speaker = dialog.get("speaker", "")
                line = dialog.get("line", "")
                
                voice = voice_map.get(speaker, self._voice_default)
                
                output_path = os.path.join(output_dir, f"ep{episode_num:02d}_{i:03d}.mp3")
                
                try:
                    path = await voice_gen.generate(
                        text=line,
                        voice=voice,
                        output_path=output_path,
                        provider=self._voice_provider
                    )
                    audio_paths.append({
                        "speaker": speaker,
                        "text": line,
                        "path": path,
                        "duration": self._get_audio_duration(path)
                    })
                    print(f"      [{i+1}] {speaker}: {line[:30]}...")
                except Exception as e:
                    print(f"      ⚠️ 配音失败: {speaker} - {e}")
            
            if not audio_paths:
                return None
            
            # 合并所有配音
            merged_path = os.path.join(output_dir, f"ep{episode_num:02d}_voiceover.mp3")
            merged_path = self._merge_audio_files(audio_paths, merged_path)
            
            print(f"   ✓ 配音生成完成: {merged_path}")
            return merged_path
            
        except Exception as e:
            print(f"   ⚠️ 配音生成失败: {e}")
            return None
    
    def _extract_dialogues_from_script(self, script: str) -> List[dict]:
        """从剧本提取对话"""
        import re
        dialogues = []
        
        for line in script.split("\n"):
            line = line.strip()
            if not line:
                continue
            
            # 匹配 "角色: 台词" 格式
            match = re.match(r'^([^：:\n]+)[:：]\s*(.+)$', line)
            if match:
                speaker = match.group(1).strip()
                text = match.group(2).strip()
                
                # 过滤非对话行
                if speaker in {"场景", "时间", "地点", "旁白", "内容"}:
                    continue
                if len(speaker) > 10:
                    continue
                
                dialogues.append({"speaker": speaker, "line": text})
        
        return dialogues
    
    def _get_audio_duration(self, audio_path: str) -> float:
        """获取音频时长"""
        try:
            cmd = ["ffprobe", "-v", "quiet", "-print_format", "json", 
                   "-show_format", audio_path]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            import json
            data = json.loads(result.stdout)
            return float(data.get("format", {}).get("duration", 0) or 0)
        except:
            return 3.0  # 默认3秒
    
    def _merge_audio_files(self, audio_list: List[dict], output_path: str) -> str:
        """合并多个音频文件"""
        if not audio_list:
            return ""
        
        # 使用 ffmpeg concat 合并
        list_file = output_path + ".list"
        with open(list_file, "w") as f:
            for item in audio_list:
                # 计算每个音频的持续时间，添加延迟确保对话间隔
                f.write(f"file '{item['path']}'\n")
                f.write(f"duration 0.5\n")  # 添加0.5秒间隔
        
        cmd = [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_file,
            "-c", "copy", output_path
        ]
        
        try:
            subprocess.run(cmd, capture_output=True, check=True)
        except:
            # 如果失败，直接复制第一个
            import shutil
            shutil.copy(audio_list[0]['path'], output_path)
        
        os.remove(list_file)
        return output_path
    
    async def _generate_subtitles(self, audio_path: str, episode_num: int) -> Optional[str]:
        """
        从音频生成字幕
        
        Args:
            audio_path: 配音文件路径
            episode_num: 集数
            
        Returns:
            字幕文件路径
        """
        if not SubtitleGenerator:
            print("   ⚠️ SubtitleGenerator 不可用")
            return None
        
        try:
            print(f"   ▶ 生成字幕...")
            
            # 加载配置
            api_config = load_api_config()
            subtitle_gen = SubtitleGenerator(api_config)
            
            output_dir = os.path.join(self.config.output_dir, "subtitles")
            os.makedirs(output_dir, exist_ok=True)
            
            output_path = os.path.join(output_dir, f"ep{episode_num:02d}.srt")
            
            # 生成字幕
            subtitle_path = await subtitle_gen.generate_from_audio(
                audio_path=audio_path,
                output_path=output_path,
                format="srt"
            )
            
            print(f"   ✓ 字幕生成完成: {subtitle_path}")
            return subtitle_path
            
        except Exception as e:
            print(f"   ⚠️ 字幕生成失败: {e}")
            return None
    
    def _compose_with_audio(
        self, 
        video_path: str, 
        voice_path: str = None,
        subtitle_path: str = None,
        episode_num: int = 1
    ) -> str:
        """
        将配音和字幕合成到视频中
        
        Args:
            video_path: 原视频路径
            voice_path: 配音路径
            subtitle_path: 字幕路径
            episode_num: 集数
            
        Returns:
            合成后的视频路径
        """
        if not self.composer:
            return video_path
        
        try:
            # 更新配置
            old_bgm = self.composer.config.bgm_path
            old_voice = self.composer.config.voiceover_path
            old_subtitles = self.composer.config.subtitles
            
            self.composer.config.bgm_path = None  # 不加 BGM
            self.composer.config.voiceover_path = voice_path
            self.composer.config.subtitles = []  # 字幕后面单独处理
            
            output_path = os.path.join(
                self.config.output_dir, 
                f"episode_{episode_num:02d}_final_with_audio.mp4"
            )
            
            old_output = self.composer.config.output_path
            self.composer.config.output_path = output_path
            
            # 合成
            clips = [VideoClip(path=video_path)]
            result = self.composer.compose(clips)
            
            # 恢复配置
            self.composer.config.bgm_path = old_bgm
            self.composer.config.voiceover_path = old_voice
            self.composer.config.subtitles = old_subtitles
            self.composer.config.output_path = old_output
            
            # 烧录字幕
            if subtitle_path and os.path.exists(result):
                result = self._burn_subtitle_file(result, subtitle_path)
            
            print(f"   ✓ 配音+字幕合成完成: {result}")
            return result
            
        except Exception as e:
            print(f"   ⚠️ 配音+字幕合成失败: {e}")
            return video_path
    
    def _burn_subtitle_file(self, video_path: str, subtitle_path: str) -> str:
        """烧录字幕文件到视频"""
        output_path = video_path.replace(".mp4", "_subtitled.mp4")
        
        cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-vf", f"subtitles='{subtitle_path}'",
            "-c:a", "copy",
            output_path
        ]
        
        try:
            subprocess.run(cmd, capture_output=True, check=True)
            return output_path
        except Exception as e:
            print(f"   ⚠️ 字幕烧录失败: {e}")
            return video_path

    async def _wait_for_review(self, flow_path: str, episode_num: int) -> None:
        """
        等待用户审核确认
        
        启动 Streamlit 审核界面，用户确认后继续
        """
        import threading
        import time
        import webbrowser
        
        review_file = os.path.join(
            os.path.dirname(flow_path),
            f"review_status_ep{episode_num:02d}.json"
        )
        
        # 创建审核状态文件
        review_status = {
            "status": "pending",  # pending / approved / rejected
            "flow_path": flow_path,
            "episode": episode_num,
            "created_at": time.time()
        }
        with open(review_file, "w", encoding="utf-8") as f:
            json.dump(review_status, f, ensure_ascii=False, indent=2)
        
        print(f"\n   📋 等待审核确认...")
        print(f"      分镜文件: {flow_path}")
        print(f"      状态文件: {review_file}")
        
        # 启动 Streamlit 审核界面
        if self._review_ui_auto_open:
            # 在后台启动 Streamlit
            streamlit_path = os.path.join(ROOT_DIR, "web", "review_streamlit.py")
            
            def run_streamlit():
                import subprocess
                subprocess.run([
                    "streamlit", "run", streamlit_path,
                    "--server.port", str(self._review_ui_port),
                    "--server.headless", "true",
                    "--browser.gatherUsageStats", "false"
                ], cwd=ROOT_DIR)
            
            # 检查 Streamlit 是否已经在运行
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            result = sock.connect_ex(('localhost', self._review_ui_port))
            sock.close()
            
            if result != 0:
                # 未运行，启动它
                thread = threading.Thread(target=run_streamlit, daemon=True)
                thread.start()
                time.sleep(3)  # 等待 Streamlit 启动
                
                # 自动打开浏览器
                try:
                    webbrowser.open(f"http://localhost:{self._review_ui_port}")
                except:
                    pass
                
                print(f"      ✅ 审核界面已启动: http://localhost:{self._review_ui_port}")
            else:
                print(f"      ✅ 审核界面已在运行: http://localhost:{self._review_ui_port}")
        
        print(f"      请在审核界面中确认后，输入 [继续] 继续生成...")
        
        # 等待用户确认
        while True:
            if os.path.exists(review_file):
                with open(review_file, "r", encoding="utf-8") as f:
                    status = json.load(f)
                
                if status.get("status") == "approved":
                    print(f"      ✅ 用户已确认，继续生成...")
                    return {"result": "approved", "flow_path": flow_path}
                elif status.get("status") == "rejected":
                    reject_reason = status.get("reject_reason", "")
                    print(f"      ❌ 用户拒绝，原因: {reject_reason}")
                    return {"result": "rejected", "reason": reject_reason, "flow_path": flow_path}
            
            await asyncio.sleep(2)

    async def _regenerate_with_feedback(self, script: str, episode_num: int, feedback: str) -> tuple:
        """
        根据用户反馈重新生成
        
        Args:
            script: 原始剧本
            episode_num: 集数
            feedback: 用户拒绝原因
            
        Returns:
            (新的剧本, 新的分镜flow)
        """
        print(f"\n   🔄 根据反馈重新生成...")
        print(f"      反馈: {feedback[:100]}...")
        
        # 1. 重新生成剧本（如果有剧本相关反馈）
        if any(keyword in feedback for keyword in ["剧本", "剧情", "台词", "故事", "反转", "节奏"]):
            if self.script_gen:
                # 将反馈融入剧本生成
                feedback_prompt = f"""
用户反馈（请根据以下要求重新优化剧本）：
{feedback}

请在保持原有主题的基础上，按照以上要求重新生成剧本。
"""
                script = await self.script_gen.generate_episode(
                    topic=self.config.topic,
                    episode_num=episode_num,
                    total_episodes=self.config.episodes,
                    story_context=feedback_prompt,
                )
                print(f"      ✓ 剧本已重新生成")
        
        # 2. 重新生成角色（如果有角色相关反馈）
        if any(keyword in feedback for keyword in ["角色", "形象", "外貌", "服装", "长相", "颜值"]):
            print(f"      🔄 重新生成角色母版...")
            if self._character_master_enabled:
                await self._create_character_masters(script, episode_num)
        
        # 3. 重新生成分镜
        flow = None
        flow_path = None
        if self._use_two_step_flow and StoryboardFlowManager:
            # 将反馈融入分镜生成
            flow_mgr = StoryboardFlowManager(
                script,
                use_gemini=self._two_step_use_gemini,
                visual_style_profile=self._visual_style_profile,
                character_registry=self.character_registry,
            )
            flow = flow_mgr.build()
            
            # 保存新的分镜文件
            os.makedirs(self.storyboards_dir, exist_ok=True)
            flow_path = os.path.join(self.storyboards_dir, f"storyboard_flow_ep{episode_num:02d}_v2.json")
            flow_mgr.save(flow, flow_path)
            print(f"      ✓ 分镜已重新生成: {len(flow.shots)} 个镜头")
        
        return script, flow, flow_path

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

    async def _run_script_experiment(self, base_script: str, episode_num: int) -> str:
        """
        运行剧本实验，生成多个版本并让用户选择

        Args:
            base_script: 基础剧本
            episode_num: 集数

        Returns:
            选中的剧本（或原剧本）
        """
        print(f"\n   🧪 [实验引擎] 开始生成剧本变体")

        # 生成实验参数
        params_list = ExperimentParamsGenerator.generate_script_params()

        # 生成变体版本
        versions = []
        for idx, params in enumerate(params_list, 1):
            version_id = f"script_ep{episode_num:02d}_v{idx}"
            print(f"\n      [版本 {idx}] 生成中...")
            print(f"      参数: {params.get('name', 'unknown')}")

            try:
                # 构建变体提示词
                variant_prompt = self._build_script_variant_prompt(base_script, params)

                # 重新生成剧本
                variant_script = await self.script_gen.generate_episode(
                    topic=self.config.topic,
                    episode_num=episode_num,
                    total_episodes=self.config.episodes,
                    story_context=variant_prompt,
                )

                versions.append({
                    "version_id": version_id,
                    "params": params,
                    "content": variant_script
                })

                # 记录到 Meta Director
                if self.meta_director:
                    self.meta_director.record_experiment(version_id, params, variant_script)

                print(f"      ✓ 生成成功 ({len(variant_script)} 字)")

            except Exception as e:
                print(f"      ✗ 生成失败: {e}")
                continue

        if not versions:
            print(f"      ⚠️ 未能生成实验版本，使用原版本")
            return base_script

        # 人工选择最佳版本
        if HumanSelector:
            selected = HumanSelector.select_best_script(versions)
            if selected:
                print(f"\n      ✓ 已选择: {selected['version_id']}")
                print(f"      理由: {selected['reason']}")

                # 记录选择
                if self.meta_director:
                    self.meta_director.select_best_version(
                        selected['version_id'],
                        selected['reason']
                    )

                return selected['content']
            else:
                print(f"      ⚠️ 未选择版本，使用原版本")
                return base_script
        else:
            print(f"      ⚠️ 人工选择器未启用，使用第一个版本")
            return versions[0]['content']

    def _build_script_variant_prompt(self, base_script: str, params: Dict[str, Any]) -> str:
        """
        构建剧本变体提示词

        Args:
            base_script: 基础剧本
            params: 实验参数

        Returns:
            变体提示词
        """
        prompts = []

        if params.get("conflict_timing") == "immediate":
            prompts.append("【重要】开头第一句话就要有强烈冲突，不要任何铺垫")
        elif params.get("conflict_timing") == "early":
            prompts.append("【重要】前10秒内必须出现明显冲突")

        if params.get("reversal_count"):
            prompts.append(f"【重要】必须有{params['reversal_count']}个明显的剧情反转")

        if params.get("emotion_intensity") == "extreme":
            prompts.append("【重要】情绪表达要极端化，使用强烈的情绪词汇（如：暴怒、崩溃、震惊）")
        elif params.get("emotion_intensity") == "high":
            prompts.append("【重要】情绪表达要强烈，使用高强度情绪词汇")

        if params.get("hook_style") == "shock":
            prompts.append("【重要】开头使用震惊式Hook（如：死亡、背叛、身份曝光、重大秘密）")
        elif params.get("hook_style") == "mystery":
            prompts.append("【重要】开头使用悬念式Hook（如：未解之谜、隐藏真相、神秘线索）")

        if params.get("scene_count"):
            prompts.append(f"【重要】剧本必须包含恰好{params['scene_count']}个场景")

        variant_instruction = "\n".join(prompts)
        return f"{variant_instruction}\n\n请基于以上要求重新创作剧本。"

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
