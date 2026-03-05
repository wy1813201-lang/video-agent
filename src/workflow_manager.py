"""
视频生成工作流管理器
支持进度追踪、用户干预、实时反馈、质量检测、重新生成
"""

import asyncio
import json
import os
import sys
import requests
from pathlib import Path
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Callable, List, Dict, Any
from datetime import datetime

# 确保 src 目录在路径中
sys.path.insert(0, os.path.dirname(__file__))

CONFIG_PATH = Path(__file__).parent.parent / "config" / "api_keys.json"


class Stage(Enum):
    """工作流阶段（SOP 角色优先 + 关键帧驱动版本）"""
    SCRIPT = "剧本生成"              # 阶段 1
    CHARACTER_MASTER = "角色母版构建"  # 阶段 2 ★新增
    STORYBOARD = "分镜拆解"           # 阶段 3
    KEYFRAME = "关键帧生成"           # 阶段 4 ★新增
    VIDEO_GEN = "视频生成"            # 阶段 5（强制 i2v）
    ASSEMBLY = "视频合成"             # 阶段 6
    QUALITY_AUDIT = "质量审核"        # 阶段 7
    FEEDBACK_LOOP = "反馈优化"       # 阶段 8 ★新增：最终质检 + 闭环优化
    COMPLETE = "完成"


@dataclass
class QualityResult:
    """质量检测结果"""
    passed: bool
    score: float          # 0.0 - 1.0
    issues: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)


@dataclass
class WorkflowState:
    """工作流状态（SOP 7阶段）"""
    stage: Stage = Stage.SCRIPT
    progress: float = 0.0
    message: str = ""
    current_item: str = ""
    total_items: int = 0
    completed_items: int = 0

    # 阶段数据
    script: str = ""                   # 阶段1: 剧本原文
    structured_script: dict = field(default_factory=dict)  # 阶段1: 结构化剧本 JSON
    character_masters: list = field(default_factory=list)  # 阶段2: CharacterMaster 列表
    storyboard: dict = field(default_factory=dict)         # 阶段3: FILM_STORYBOARD JSON
    keyframes: Dict[str, str] = field(default_factory=dict)  # 阶段4: {shot_id: image_path}
    prompts: List[str] = field(default_factory=list)       # 兼容旧字段
    scene_texts: List[str] = field(default_factory=list)
    images: List[str] = field(default_factory=list)
    videos: List[str] = field(default_factory=list)
    audit_report: Any = None                               # 阶段7: AuditReport

    # 用户干预
    user_feedback: str = ""
    needs_approval: bool = False
    approved: bool = False

    # 质量追踪
    quality_results: Dict[str, QualityResult] = field(default_factory=dict)
    regen_counts: Dict[str, int] = field(default_factory=dict)


class WorkflowManager:
    """视频生成工作流管理器"""

    MAX_REGEN_ATTEMPTS = 3
    QUALITY_THRESHOLD = 0.6  # 低于此分数触发重新生成

    def __init__(
        self,
        notify_callback: Optional[Callable] = None,
        quality_callback: Optional[Callable[[str, Any], QualityResult]] = None,
    ):
        self.state = WorkflowState()
        self.notify = notify_callback or (lambda x: print(x))
        # quality_callback(item_type, item_data) -> QualityResult
        self.quality_callback = quality_callback or self._default_quality_check
        self.paused = False
        self._approval_event = asyncio.Event()
        self.api_config = self._load_config()

    def _load_config(self) -> dict:
        """读取并返回 API 配置，供各方法复用"""
        with open(CONFIG_PATH) as f:
            return json.load(f)

    def _get_ip_adapter_config(self, provider: str) -> Dict[str, Any]:
        """读取并合并 IP-Adapter 配置。provider: image_cozex / video_jimeng"""
        global_cfg = self.api_config.get("character_consistency", {}).get("ip_adapter", {})

        provider_cfg = {}
        if provider == "image_cozex":
            provider_cfg = self.api_config.get("image", {}).get("cozex", {}).get("ip_adapter", {})
        elif provider == "video_jimeng":
            provider_cfg = self.api_config.get("video", {}).get("jimeng", {}).get("ip_adapter", {})

        merged = dict(global_cfg)
        merged.update(provider_cfg)
        return merged

    # ------------------------------------------------------------------ #
    #  进度 & 审批
    # ------------------------------------------------------------------ #

    async def update_progress(
        self,
        stage: Stage,
        progress: float,
        message: str = "",
        current_item: str = "",
        total: int = 0,
        completed: int = 0,
    ):
        self.state.stage = stage
        self.state.progress = progress
        self.state.message = message
        self.state.current_item = current_item
        self.state.total_items = total
        self.state.completed_items = completed

        bar_length = 20
        filled = int(bar_length * progress)
        bar = "█" * filled + "░" * (bar_length - filled)

        status_msg = (
            f"📊 工作流状态\n\n"
            f"[{bar}] {progress*100:.1f}%\n"
            f"阶段: {stage.value}\n"
            f"{message}\n\n"
            f"当前: {current_item}\n"
            f"进度: {completed}/{total}"
        )
        self.notify(status_msg)

        if self.state.needs_approval:
            self.notify("⏸️ 等待用户审批...")
            await self.wait_for_approval()

    async def wait_for_approval(self, timeout: int = 300):
        """等待用户审批，超时后自动继续"""
        self._approval_event.clear()
        try:
            await asyncio.wait_for(self._approval_event.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            self.notify("⏰ 审批超时，自动继续执行")

        self.state.approved = False
        self.state.needs_approval = False

    def approve(self):
        self.state.approved = True
        self.state.needs_approval = False
        self._approval_event.set()
        self.notify("✅ 用户已批准，继续执行")

    def reject(self, feedback: str = ""):
        self.state.approved = False
        self.state.needs_approval = False
        self.state.user_feedback = feedback
        self.notify(f"❌ 用户要求修改: {feedback}")

    # ------------------------------------------------------------------ #
    #  质量检测
    # ------------------------------------------------------------------ #

    def _default_quality_check(self, item_type: str, item_data: Any) -> QualityResult:
        """默认质量检测（占位实现，实际应接入视觉/文本评估模型）"""
        return QualityResult(passed=True, score=0.8)

    async def run_quality_check(
        self, item_type: str, item_data: Any, item_key: str
    ) -> QualityResult:
        """
        运行质量检测并记录结果。
        item_type: 'image' | 'video' | 'script' | 'prompt'
        item_key:  用于追踪的唯一标识（如 'image_3'）
        """
        result: QualityResult = self.quality_callback(item_type, item_data)
        self.state.quality_results[item_key] = result

        if not result.passed or result.score < self.QUALITY_THRESHOLD:
            issues_str = "; ".join(result.issues) if result.issues else "质量不达标"
            self.notify(
                f"⚠️ 质量检测未通过 [{item_key}] 分数: {result.score:.2f}\n"
                f"问题: {issues_str}"
            )
        else:
            self.notify(f"✅ 质量检测通过 [{item_key}] 分数: {result.score:.2f}")

        return result

    # ------------------------------------------------------------------ #
    #  重新生成机制
    # ------------------------------------------------------------------ #

    async def regenerate_with_retry(
        self,
        item_key: str,
        generate_fn: Callable,
        item_type: str,
        *args,
        **kwargs,
    ) -> Any:
        """
        带质量检测的生成 + 自动重试。
        generate_fn 是异步生成函数，*args/**kwargs 传给它。
        超过 MAX_REGEN_ATTEMPTS 后返回最后一次结果。
        """
        attempt = 0
        result = None

        while attempt < self.MAX_REGEN_ATTEMPTS:
            result = await generate_fn(*args, **kwargs)
            attempt += 1
            self.state.regen_counts[item_key] = attempt

            quality = await self.run_quality_check(item_type, result, item_key)

            if quality.passed and quality.score >= self.QUALITY_THRESHOLD:
                return result

            if attempt < self.MAX_REGEN_ATTEMPTS:
                self.notify(
                    f"🔄 重新生成 [{item_key}] 第 {attempt}/{self.MAX_REGEN_ATTEMPTS} 次..."
                )
            else:
                self.notify(
                    f"⚠️ [{item_key}] 已达最大重试次数，使用当前结果"
                )

        return result

    # ------------------------------------------------------------------ #
    #  状态查询
    # ------------------------------------------------------------------ #

    def get_status(self) -> dict:
        return {
            "stage": self.state.stage.value,
            "progress": self.state.progress,
            "message": self.state.message,
            "current_item": self.state.current_item,
            "completed": self.state.completed_items,
            "total": self.state.total_items,
            "needs_approval": self.state.needs_approval,
            "quality_summary": {
                k: {"passed": v.passed, "score": v.score}
                for k, v in self.state.quality_results.items()
            },
            "regen_counts": self.state.regen_counts,
        }

    # ------------------------------------------------------------------ #
    #  主工作流
    # ------------------------------------------------------------------ #

    async def run_workflow(self, config):
        """
        运行完整 SOP 工作流（角色优先 + 关键帧驱动）

        流水线: 剧本 → 角色母版 → 分镜 → 关键帧 → i2v视频 → 合成 → 质量审核
        """
        # ── 阶段 1: 剧本生成 (0-15%) ──────────────────────────────────
        await self.update_progress(Stage.SCRIPT, 0.03, "[1/7] 正在生成剧本...", "生成中", 1, 0)
        script = await self.generate_script(config)
        self.state.script = script
        await self.run_quality_check("script", script, "script_main")
        self.state.needs_approval = True
        await self.update_progress(Stage.SCRIPT, 0.12, "[1/7] 剧本生成完成，请审批", "等待审批", 1, 1)
        await self.wait_for_approval()
        if self.state.user_feedback:
            self.notify(f"📝 根据反馈重新生成剧本: {self.state.user_feedback}")
            script = await self.generate_script(config)
            self.state.script = script
            self.state.user_feedback = ""

        # ── 阶段 2: 角色母版构建 (15-25%) ────────────────────────────
        await self.update_progress(
            Stage.CHARACTER_MASTER, 0.15,
            "[2/7] 正在构建角色母版资产...", "分析剧本角色", 1, 0
        )
        character_masters = await self.build_character_masters(script, config)
        self.state.character_masters = character_masters
        self.state.needs_approval = True
        await self.update_progress(
            Stage.CHARACTER_MASTER, 0.25,
            f"[2/7] 角色母版构建完成（{len(character_masters)}个角色），请审批",
            "等待审批", len(character_masters), len(character_masters)
        )
        await self.wait_for_approval()

        # ── 阶段 3: 分镜拆解 (25-40%) ────────────────────────────────
        await self.update_progress(
            Stage.STORYBOARD, 0.27,
            "[3/7] 正在拆解分镜...", "Film Director Agent 工作中", 1, 0
        )
        storyboard = await self.generate_storyboard(script, character_masters)
        self.state.storyboard = storyboard
        scenes = storyboard.get("scenes", [])
        total_shots = sum(len(s.get("shots", [])) for s in scenes)
        await self.update_progress(
            Stage.STORYBOARD, 0.40,
            f"[3/7] 分镜完成（{len(scenes)}个场景，{total_shots}个镜头）",
            "等待审批", total_shots, total_shots
        )

        # ── 阶段 4: 关键帧生成 (40-65%) ──────────────────────────────
        await self.update_progress(
            Stage.KEYFRAME, 0.42,
            "[4/7] 正在生成关键帧图片...", f"0/{total_shots}", total_shots, 0
        )
        keyframes = await self.generate_all_keyframes(storyboard, character_masters)
        self.state.keyframes = keyframes
        self.state.images = list(keyframes.values())

        # 每 4 张审批一次
        completed = 0
        for shot_id, img_path in keyframes.items():
            completed += 1
            progress = 0.42 + completed / max(total_shots, 1) * 0.22
            await self.update_progress(
                Stage.KEYFRAME, progress,
                f"[4/7] 关键帧 {completed}/{total_shots}",
                shot_id, total_shots, completed
            )
            if completed % 4 == 0 and completed < total_shots:
                self.notify(f"📸 已完成 {completed} 张关键帧，请审批后继续")
                self.state.needs_approval = True
                await self.wait_for_approval()

        self.state.needs_approval = True
        await self.update_progress(
            Stage.KEYFRAME, 0.65,
            f"[4/7] 关键帧全部生成完毕（{len(keyframes)}张），请审批",
            "等待审批", total_shots, total_shots
        )
        await self.wait_for_approval()

        # ── 阶段 5: 视频生成（强制 i2v）(65-88%) ──────────────────────
        await self.update_progress(
            Stage.VIDEO_GEN, 0.65,
            "[5/7] 正在基于关键帧生成视频（i2v模式）...",
            f"0/{len(keyframes)}", len(keyframes), 0
        )
        # 从分镜中预取每个镜头的 motion_prompt
        video_prompts: Dict[str, str] = {}
        for _scene in storyboard.get("scenes", []):
            for _shot in _scene.get("shots", []):
                _sid = _shot.get("shot_id", "")
                if _sid:
                    video_prompts[_sid] = _shot.get(
                        "motion_prompt", _shot.get("video_prompt", "")
                    )

        videos = []
        keyframe_items = list(keyframes.items())
        for i, (shot_id, img_path) in enumerate(keyframe_items):
            if self.paused:
                await self.wait_for_approval()
            item_key = f"video_{shot_id}"
            motion_prompt = video_prompts.get(shot_id, "")
            video = await self.regenerate_with_retry(
                item_key, self.generate_video, "video", img_path, motion_prompt
            )
            videos.append(video)
            progress = 0.65 + (i + 1) / len(keyframe_items) * 0.23
            await self.update_progress(
                Stage.VIDEO_GEN, progress,
                f"[5/7] 视频 {i+1}/{len(keyframe_items)}",
                shot_id, len(keyframe_items), i + 1
            )
        self.state.videos = videos

        # ── 阶段 6: 视频合成 (88-95%) ────────────────────────────────
        await self.update_progress(
            Stage.ASSEMBLY, 0.88,
            "[6/7] 正在合成最终视频（统一调色/转场/音频）...", "合并中", 1, 0
        )
        final_video = await self.assemble_videos(videos)

        # ── 阶段 7: 质量审核 (95-100%) ───────────────────────────────
        await self.update_progress(
            Stage.QUALITY_AUDIT, 0.95,
            "[7/7] 正在进行质量审核...", "SOP合规检查", 1, 0
        )
        audit_report = await self.run_sop_quality_audit(storyboard, character_masters)
        self.state.audit_report = audit_report

        # ── 阶段 8: 反馈优化（终极质检 + 闭环）───────────────
        await self.update_progress(
            Stage.FEEDBACK_LOOP, 0.97,
            "[8/8] 正在进行视频质量评估与闭环优化...", "质检中", 1, 0
        )
        
        # 提取所有 prompts 用于反馈评估
        all_prompts = []
        for scene in storyboard.get("scenes", []):
            for shot in scene.get("shots", []):
                for key in ["keyframe_image_prompt", "video_prompt", "motion_prompt"]:
                    if p := shot.get(key, ""):
                        all_prompts.append(p)
        
        feedback_report = await self.run_feedback_optimization(
            final_video, storyboard, all_prompts
        )
        
        # 根据反馈决定是否重做
        if feedback_report.needs_regen:
            self.notify(f"⚠️ 质检发现问题，启动优化流程...")
            self.notify(feedback_report.summary())
            
            # 应用优化操作
            from feedback_loop import ParameterTuner
            tuner = ParameterTuner()
            tuner.apply_actions(feedback_report.optimization_actions)
            self.notify(f"📝 已自动调整 {len(feedback_report.optimization_actions)} 项配置")
            
            # ── 闭环重做 ───────────────────────────────────────
            regen_result = await self._execute_regen(
                feedback_report,
                storyboard,
                character_masters,
                keyframes,
                videos
            )
            
            if regen_result.get("regen_done"):
                final_video = regen_result.get("final_video", final_video)
                self.notify(f"🔄 重做完成，评分: {regen_result.get('new_score', 'N/A')}")
                
                # 可选：再次评估（递归上限防止无限循环）
                if regen_result.get("should_recheck") and self.state.regen_counts.get("total", 0) < 3:
                    self.state.regen_counts["total"] = self.state.regen_counts.get("total", 0) + 1
                    recheck_report = await self.run_feedback_optimization(
                        final_video, storyboard, all_prompts
                    )
                    if not recheck_report.overall_pass:
                        self.notify(f"⚠️ 再次质检未通过，可手动调整后重试")
                    else:
                        feedback_report = recheck_report
            else:
                self.notify(f"⚠️ 跳过重做: {regen_result.get('reason', '未知原因')}")
        
        status_icon = "✅" if feedback_report.overall_pass else "⚠️"
        final_status = f"{status_icon} 全部完成！"
        if not feedback_report.overall_pass:
            final_status += f" (质量评分: {feedback_report.scores.overall:.1%})"
        
        await self.update_progress(
            Stage.COMPLETE, 1.0,
            final_status,
            final_video, 1, 1
        )
        return final_video

    # ------------------------------------------------------------------ #
    #  生成方法（占位，待接入实际 API）
    # ------------------------------------------------------------------ #

    async def generate_script(self, config):
        """生成剧本 - 调用 ScriptGenerator"""
        from script_generator import ScriptGenerator

        script_gen = ScriptGenerator(config, self.api_config)
        topic = getattr(config, "topic", "短剧")
        episodes = getattr(config, "episodes", 3)

        try:
            parts = []
            for i in range(1, episodes + 1):
                ep = await script_gen.generate_episode(topic, i, episodes)
                parts.append(ep)
            return "\n\n---\n\n".join(parts)
        finally:
            close_fn = getattr(script_gen, "close", None)
            if close_fn:
                await close_fn()

    async def generate_prompts(self, script):
        """从剧本提取图像提示词"""
        quality_suffix = self.api_config.get("prompt", {}).get(
            "image_quality_suffix", "high quality, 8k, detailed, masterpiece"
        )
        aspect_ratio = self.api_config.get("prompt", {}).get("default_aspect_ratio", "9:16")
        ip_cfg = self._get_ip_adapter_config("image_cozex")
        use_ip_adapter = bool(ip_cfg.get("enabled", False))

        prompts = []
        scene_texts = []
        for block in script.split("场景"):
            text = block.strip()
            if not text:
                continue
            # 取前120字作为场景描述
            desc = text[:120].replace("\n", " ")
            scene_texts.append(text)
            prompts.append(
                f"cinematic scene, {desc}, {quality_suffix}, aspect ratio {aspect_ratio}"
            )

        if not prompts:
            return [f"cinematic short drama scene, {quality_suffix}"]

        if use_ip_adapter:
            try:
                from character_consistency import CharacterExtractor, PromptEnhancer
                extractor = CharacterExtractor()
                characters = extractor.extract_characters(script)
                if characters:
                    enhancer = PromptEnhancer(characters)
                    prompts = enhancer.enhance_batch(
                        prompts=prompts,
                        scene_texts=scene_texts,
                        use_ip_adapter=True,
                    )
            except Exception as e:
                self.notify(f"⚠️ IP-Adapter 提示词增强失败，继续使用基础提示词: {e}")

        self.state.scene_texts = scene_texts
        return prompts

    async def generate_image(self, prompt):
        """生成图像 - 调用 cozex 图像 API"""
        img_cfg = self.api_config.get("image", {}).get("cozex", {})
        if not img_cfg.get("enabled"):
            # fallback: 返回空路径，不阻断流程
            self.notify("⚠️ 图像 API 未启用，跳过图像生成")
            return ""

        api_key = img_cfg["api_key"]
        base_url = img_cfg["base_url"].rstrip("/")
        model = img_cfg.get("model", "doubao-seedream-5-0-260128")

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "prompt": prompt,
            "n": 1,
            "size": "1024x1792",  # 9:16
        }

        loop = asyncio.get_event_loop()
        resp = await loop.run_in_executor(
            None,
            lambda: requests.post(
                f"{base_url}/v1/images/generations",
                headers=headers,
                json=payload,
                timeout=60,
            ),
        )
        resp.raise_for_status()
        data = resp.json()

        image_url = data["data"][0].get("url", "")
        if not image_url:
            raise Exception("图像 API 未返回 URL")

        # 下载图像
        output_dir = Path(img_cfg.get("output_dir", "~/Desktop/ShortDrama")).expanduser()
        images_dir = output_dir / "images"
        images_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        img_path = images_dir / f"image_{timestamp}.png"

        img_resp = await loop.run_in_executor(
            None, lambda: requests.get(image_url, timeout=60)
        )
        img_resp.raise_for_status()
        img_path.write_bytes(img_resp.content)

        self.notify(f"🖼️ 图像已保存: {img_path.name}")
        return str(img_path)

    async def generate_video(self, image_path: str, motion_prompt: str = ""):
        """
        生成视频 - 支持 Cozex API

        SOP 规定：视频必须基于关键帧图片生成，禁止随机生成角色。
        若 image_path 为空或文件不存在，直接抛出 ValueError。

        Args:
            image_path:    关键帧图片本地路径（必填）
            motion_prompt: 来自分镜的 motion_prompt（优先使用）；为空时用通用后缀
        """
        # ── SOP 强制检查：必须有关键帧图片 ──
        if not image_path:
            raise ValueError(
                "[SOP] generate_video 要求提供 image_path（关键帧图片路径）。"
                "视频必须基于关键帧生成（i2v模式），禁止随机生成角色。"
            )
        if not Path(image_path).exists():
            raise ValueError(
                f"[SOP] 关键帧图片不存在: {image_path}。"
                "请先完成关键帧生成阶段再进行视频生成。"
            )

        # SOP 优先走 Jimeng i2v（真图生视频），确保角色与关键帧绑定。
        try:
            from .jimeng_client import JimengVideoClient
        except ImportError:
            from jimeng_client import JimengVideoClient

        video_cfg_jimeng = self.api_config.get("video", {}).get("jimeng", {})
        if not video_cfg_jimeng.get("enabled"):
            self.notify("⚠️ Jimeng 未启用，跳过 i2v 视频生成")
            return ""

        client = JimengVideoClient()

        prompt_suffix = self.api_config.get("prompt", {}).get(
            "video_quality_suffix",
            "smooth motion, cinematic high quality, consistent character, i2v"
        )
        # 优先使用分镜的 motion_prompt，否则用通用描述
        if motion_prompt:
            prompt = (
                f"{motion_prompt}, "
                f"based on the reference image, maintain character appearance exactly as shown, "
                f"{prompt_suffix}, 9:16 vertical format"
            )
        else:
            prompt = (
                f"based on the reference image, {prompt_suffix}, "
                f"maintain character appearance exactly as shown, "
                f"9:16 vertical format"
            )

        resolution = video_cfg_jimeng.get("default_resolution", "720p")
        # Jimeng i2v 需要公网 URL。若是本地路径，落地 pending 状态供上传后重跑。
        if image_path.startswith("http://") or image_path.startswith("https://"):
            result = await client.image_to_video(
                image_url=image_path,
                prompt=prompt,
                aspect_ratio="9:16",
            )
        else:
            status_dir = Path("output/video_generation")
            status_dir.mkdir(parents=True, exist_ok=True)
            status_path = status_dir / f"pending_i2v_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            status_payload = {
                "stage": "视频生成",
                "status": "pending",
                "reason": "Jimeng i2v 需要公网可访问 image_url，当前为本地路径",
                "input_image": image_path,
                "motion_prompt": motion_prompt,
                "resolution": resolution,
            }
            status_path.write_text(json.dumps(status_payload, ensure_ascii=False, indent=2), encoding="utf-8")
            self.notify(f"⚠️ i2v 待处理（缺少公网URL）: {status_path}")
            return ""

        video_path = result.get("video_path", "")
        self.notify(f"🎬 [i2v] 视频已保存: {Path(video_path).name if video_path else '无'}")
        return video_path

    async def assemble_videos(self, videos):
        """合成视频 - 调用 FFmpeg 拼接"""
        valid = [v for v in videos if v and Path(v).exists()]
        if not valid:
            self.notify("⚠️ 无有效视频片段，跳过合成")
            return ""

        output_dir = Path(
            self.api_config.get("video", {}).get("jimeng", {}).get(
                "output_dir", "~/Desktop/ShortDrama"
            )
        ).expanduser()
        output_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        list_file = output_dir / f"concat_{timestamp}.txt"
        output_file = output_dir / f"final_{timestamp}.mp4"

        # 写 ffmpeg concat 列表
        list_file.write_text(
            "\n".join(f"file '{v}'" for v in valid), encoding="utf-8"
        )

        cmd = (
            f"ffmpeg -y -f concat -safe 0 -i '{list_file}' "
            f"-c copy '{output_file}' 2>&1"
        )

        loop = asyncio.get_event_loop()
        proc = await loop.run_in_executor(None, lambda: os.popen(cmd).read())

        list_file.unlink(missing_ok=True)

        if output_file.exists():
            self.notify(f"✅ 最终视频: {output_file}")
            return str(output_file)
        else:
            self.notify(f"❌ FFmpeg 合成失败:\n{proc}")
            return ""

    # ------------------------------------------------------------------ #
    #  SOP 新增 Helper 方法
    # ------------------------------------------------------------------ #

    async def build_character_masters(self, script: str, config) -> list:
        """
        [SOP 阶段2] 从剧本中提取角色并构建 CharacterMaster 对象。
        
        并在图像 API 启用时，直接生成角色官方基准图片。
        """
        try:
            from .character_master import CharacterMaster, CharacterMasterRegistry
            from .character_consistency import CharacterExtractor
            from .cozex_client import CozexClient
        except ImportError:
            from character_master import CharacterMaster, CharacterMasterRegistry
            from character_consistency import CharacterExtractor
            from cozex_client import CozexClient

        registry = CharacterMasterRegistry(
            registry_dir=str(Path("data/character_masters"))
        )
        extractor = CharacterExtractor()

        img_cfg = self.api_config.get("image", {}).get("cozex", {})
        use_image_api = img_cfg.get("enabled", False)
        client = CozexClient() if use_image_api else None

        masters = []

        def _build_master_sheet_prompt(master: "CharacterMaster") -> str:
            """单图角色参考总表：三视图 + 服装细节 + 代表表情。"""
            anchor = master.to_anchor_fragment()
            return (
                "character bible sheet, single image layout with labeled panels, "
                "panel A front full-body view, panel B side full-body view, panel C back full-body view, "
                "panel D outfit detail swatches and fabric close-up, "
                "panel E neutral expression close-up, panel F happy expression close-up, "
                "panel G sad expression close-up, panel H angry expression close-up, "
                "same person identity across all panels, strict identity lock, "
                f"{anchor}, white clean background, studio lighting, high detail model sheet"
            )
        try:
            characters = extractor.extract_characters(script)
            for role_key, trait in characters.items():
                master = CharacterMaster(
                    character_id=f"char_{role_key}",
                    name=trait.name,
                    gender=trait.gender or "unknown",
                    age_range=trait.age_range or "unknown age",
                    hair_color="black",
                    hair_style="natural style",
                    face_structure=trait.appearance or "natural face structure",
                    skin_tone="natural skin tone",
                    eye_description="expressive eyes",
                    outfit_primary=trait.outfit or "casual outfit",
                    personality=trait.personality or "",
                    role_in_story=role_key,
                    extra_tags=trait.extra_tags,
                )
                
                # 若开启图像 API，生成单图角色总参考表（后续视频/配音统一锚点）
                if client:
                    try:
                        prompt = _build_master_sheet_prompt(master)
                        loop = asyncio.get_event_loop()
                        image_path = await loop.run_in_executor(
                            None,
                            lambda m=prompt: client.image_generation(m, size="2048x2048").get("saved_path", ""),
                        )
                        if image_path:
                            master.reference_images["master_sheet"] = image_path
                            self.notify(f"🖼️ 角色总参考图生成成功: {master.name}")
                    except Exception as e:
                        self.notify(f"⚠️ 角色 {master.name} 图片生成失败: {e}")

                try:
                    registry.register(master)
                    masters.append(master)
                    self.notify(f"👤 角色母版已注册: {master.name}")
                except ValueError as ve:
                    self.notify(f"⚠️ 角色 {master.name} 母版注册失败（SOP校验）: {ve}")
                    masters.append(master)

        except Exception as e:
            self.notify(f"⚠️ 角色提取失败: {e}，使用示例角色母版")
            masters.append(CharacterMaster.example())

        if not masters:
            masters.append(CharacterMaster.example())

        return masters

    @staticmethod
    def _flat_to_nested_storyboard(flat: dict) -> dict:
        """
        将 FilmDirectorAgent.run() 的 film_storyboard 平铺格式
        转换为 scenes 嵌套格式，供 QualityAuditor / generate_all_keyframes 使用。

        输入：{"film_storyboard": [{scene_id, shot_id, ...}, ...], ...}
        输出：{"scenes": [{"scene_id": ..., "shots": [...]}], ...}
        """
        scenes_ordered: dict = {}
        for shot in flat.get("film_storyboard", []):
            scene_id = shot.get("scene_id", "Scene_01")
            if scene_id not in scenes_ordered:
                scenes_ordered[scene_id] = {
                    "scene_id": scene_id,
                    "location": shot.get("scene_location", ""),
                    "time_of_day": shot.get("scene_time", ""),
                    "emotional_tone": shot.get("scene_emotion", ""),
                    "shots": [],
                }
            scenes_ordered[scene_id]["shots"].append(shot)
        return {
            "director_intent": flat.get("director_intent", {}),
            "characters": flat.get("characters", {}),
            "scenes": list(scenes_ordered.values()),
        }

    async def generate_storyboard(self, script: str, character_masters: list) -> dict:
        """
        [SOP 阶段3] 调用 FilmDirectorAgent 生成电影级分镜。
        返回 scenes 嵌套格式（供 QualityAuditor / generate_all_keyframes 统一使用）。
        """
        try:
            from .film_director_agent import FilmDirectorAgent
        except ImportError:
            from film_director_agent import FilmDirectorAgent

        visual_style = self.api_config.get("storyboard", {}).get(
            "visual_style_profile", "cinematic"
        )
        loop = asyncio.get_event_loop()
        agent = FilmDirectorAgent(script, visual_style)
        # 注入角色母版 ID，确保分镜与角色资产关联
        agent.character_master_ids = [m.character_id for m in character_masters]

        # 运行完整导演流程（意图分析→分镜→镜头规划→视觉增强→角色→运镜→Prompt编译→输出）
        flat_storyboard = await loop.run_in_executor(
            None, lambda: agent.run(use_gemini=False)
        )
        # 转换为 scenes 嵌套格式
        storyboard = self._flat_to_nested_storyboard(flat_storyboard)

        # 保存分镜 JSON
        out_path = Path("output/storyboard_latest.json")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            import json as _json
            _json.dump(storyboard, f, ensure_ascii=False, indent=2)
        self.notify(f"🎬 分镜已保存: {out_path}")
        return storyboard

    async def generate_all_keyframes(
        self, storyboard: dict, character_masters: list
    ) -> Dict[str, str]:
        """
        [SOP 阶段4] 为所有分镜生成关键帧图片（调用 KeyframeGenerator + CozexClient）。

        Returns:
            {shot_id: image_path}
        """
        try:
            from .keyframe_generator import KeyframeGenerator
            from .cozex_client import CozexClient
        except ImportError:
            from keyframe_generator import KeyframeGenerator
            from cozex_client import CozexClient

        img_cfg = self.api_config.get("image", {}).get("cozex", {})
        if not img_cfg.get("enabled"):
            self.notify("⚠️ 图像 API 未启用，关键帧生成跳过，使用空路径占位")
            # 返回占位字典（shot_id -> ""）
            placeholder = {}
            for scene in storyboard.get("scenes", []):
                for shot in scene.get("shots", []):
                    placeholder[shot.get("shot_id", f"s_{len(placeholder)}")] = ""
            return placeholder

        client = CozexClient()
        generator = KeyframeGenerator(output_dir="output/keyframes")
        results: Dict[str, str] = {}

        for scene in storyboard.get("scenes", []):
            for shot in scene.get("shots", []):
                shot_id = shot.get("shot_id", "unknown")
                # 确定该分镜出场的角色母版
                shot_char_ids = shot.get("characters_in_shot", [])
                if shot_char_ids:
                    shot_masters = [
                        m for m in character_masters
                        if m.character_id in shot_char_ids or m.name in shot_char_ids
                    ]
                else:
                    shot_masters = character_masters  # 默认使用所有角色

                if not shot_masters:
                    shot_masters = character_masters

                try:
                    # 构建九宫格关键帧规格 (9-panel narrative storyboard)
                    spec = generator.build_nine_grid_prompt(shot, shot_masters)
                    # 异步生成图片
                    loop = asyncio.get_event_loop()
                    image_path = await loop.run_in_executor(
                        None,
                        lambda s=spec: client.image_generation(s.compiled_prompt).get(
                            "saved_path", ""
                        ),
                    )
                    spec.image_path = image_path
                    results[shot_id] = image_path
                    self.notify(f"🖼️ 关键帧 [{shot_id}] → {Path(image_path).name if image_path else '失败'}")
                except Exception as e:
                    self.notify(f"⚠️ 关键帧 [{shot_id}] 生成失败: {e}")
                    results[shot_id] = ""

        # 将关键帧路径注入分镜 JSON 并保存
        try:
            generator.save_storyboard_with_keyframes(
                storyboard, results, "output/storyboard_with_keyframes.json"
            )
        except Exception:
            pass

        return results

    async def run_sop_quality_audit(
        self, storyboard: dict, character_masters: list
    ):
        """
        [SOP 阶段7] 对整个分镜执行质量审核并保存报告。
        """
        try:
            from .quality_auditor import QualityAuditor
        except ImportError:
            from quality_auditor import QualityAuditor

        audit_thresholds = self.api_config.get("quality_audit", {})
        auditor = QualityAuditor(thresholds=audit_thresholds or None)

        loop = asyncio.get_event_loop()
        report = await loop.run_in_executor(
            None,
            lambda: auditor.audit_storyboard(
                storyboard, character_masters, episode="current"
            ),
        )

        # 保存报告
        report_path = "output/quality_audit_report.json"
        await loop.run_in_executor(
            None, lambda: auditor.save_report(report, report_path)
        )
        self.notify(
            f"📋 质量审核完成: 通过率 {report.passed_shots}/{report.total_shots}，"
            f"人物一致性: {report.avg_character_consistency:.1%}"
        )
        return report

    async def run_feedback_optimization(
        self, final_video: str, storyboard: dict, prompts: List[str]
    ):
        """
        [SOP 阶段8] 视频质量反馈优化闭环
        - 三维度评分（图文对齐、运动流畅、美学质量）
        - 根因分析
        - 自动调整配置
        - 决定是否需要重做
        """
        try:
            from .feedback_loop import FeedbackLoop, ScoringConfig
        except ImportError:
            from feedback_loop import FeedbackLoop, ScoringConfig

        # 获取评分配置
        scoring_cfg = self.api_config.get("feedback_loop", {})
        config = ScoringConfig(
            text_alignment_threshold=scoring_cfg.get("text_alignment_threshold", 0.6),
            motion_quality_threshold=scoring_cfg.get("motion_quality_threshold", 0.5),
            aesthetic_threshold=scoring_cfg.get("aesthetic_threshold", 0.6),
            overall_threshold=scoring_cfg.get("overall_threshold", 0.65),
        )

        loop = FeedbackLoop(scoring_config=config)
        
        # 提取所有 prompt
        all_prompts = []
        for scene in storyboard.get("scenes", []):
            for shot in scene.get("shots", []):
                for key in ["keyframe_image_prompt", "video_prompt", "motion_prompt"]:
                    if p := shot.get(key, ""):
                        all_prompts.append(p)

        # 执行反馈循环
        report = await loop.evaluate_and_optimize(
            final_video, storyboard, all_prompts
        )

        # 保存报告
        report_path = "output/feedback_report.json"
        import json as json_module
        with open(report_path, "w", encoding="utf-8") as f:
            json_module.dump({
                "scores": report.scores.to_dict(),
                "root_causes": [
                    {
                        "stage": rc.stage,
                        "shot_ids": rc.shot_ids,
                        "confidence": rc.confidence,
                        "description": rc.description,
                        "suggestions": rc.suggestions,
                    }
                    for rc in report.root_causes
                ],
                "optimization_actions": [
                    {
                        "action_type": op.action_type,
                        "target": op.target,
                        "reason": op.reason,
                    }
                    for op in report.optimization_actions
                ],
                "overall_pass": report.overall_pass,
                "needs_regen": report.needs_regen,
                "regen_plan": report.regen_plan,
            }, f, ensure_ascii=False, indent=2)

        self.notify(
            f"🎯 反馈优化完成: 综合评分 {report.scores.overall:.1%}, "
            f"图文对齐: {report.scores.text_alignment:.1%}, "
            f"运动质量: {report.scores.motion_quality:.1%}, "
            f"美学: {report.scores.aesthetic:.1%}"
        )
        
        return report

    async def _execute_regen(
        self,
        feedback_report,
        storyboard: dict,
        character_masters: list,
        keyframes: Dict[str, str],
        old_videos: List[str],
    ) -> dict:
        """
        执行闭环重做
        返回: {"regen_done": bool, "final_video": str, "new_score": float, "should_recheck": bool, "reason": str}
        """
        regen_plan = feedback_report.regen_plan
        actions = feedback_report.optimization_actions
        
        # 检查是否达到重做上限
        total_regen = self.state.regen_counts.get("total", 0)
        if total_regen >= 3:
            return {"regen_done": False, "reason": "已达到最大重做次数(3次)"}
        
        self.notify(f"🔄 开始执行 {regen_plan} 级别重做...")
        
        # ── Shot 级别：重做特定分镜 ─────────────────────────────
        if regen_plan == "shot":
            shot_actions = [a for a in actions if a.action_type == "regen_shot"]
            if not shot_actions:
                return {"regen_done": False, "reason": "无分镜需要重做"}
            
            shot_ids_to_regen = [a.target for a in shot_actions]
            self.notify(f"📍 重新生成分镜: {', '.join(shot_ids_to_regen[:3])}")
            
            # 重新生成这些分镜的 keyframe + video
            new_videos = []
            for shot_id in shot_ids_to_regen:
                # 找到对应的 keyframe
                img_path = keyframes.get(shot_id, "")
                if not img_path:
                    continue
                
                # 找到对应的 prompt
                shot_prompt = ""
                for scene in storyboard.get("scenes", []):
                    for shot in scene.get("shots", []):
                        if shot.get("shot_id") == shot_id:
                            shot_prompt = shot.get("video_prompt") or shot.get("motion_prompt", "")
                            break
                
                # 重新生成视频
                try:
                    video_path = await self.generate_video(img_path, shot_prompt)
                    if video_path:
                        new_videos.append(video_path)
                        self.state.regen_counts[shot_id] = self.state.regen_counts.get(shot_id, 0) + 1
                except Exception as e:
                    self.notify(f"⚠️ 分镜 {shot_id} 重做失败: {e}")
            
            # 替换旧视频片段
            if new_videos:
                # 用新视频替换旧的
                for new_v in new_videos:
                    if new_v and Path(new_v).exists():
                        old_videos.append(new_v)
                
                # 重新合成
                final_video = await self.assemble_videos(old_videos)
                return {
                    "regen_done": True,
                    "final_video": final_video,
                    "new_score": "待评估",
                    "should_recheck": True
                }
            return {"regen_done": False, "reason": "分镜重做后无有效视频"}
        
        # ── Stage 级别：重做某个阶段 ───────────────────────────
        elif regen_plan == "stage":
            # 判断需要重做的阶段
            stage_actions = [a for a in actions if a.action_type in ("adjust_params", "enhance_prompt_template")]
            
            # 重新加载配置
            self.api_config = self._load_config()
            
            # 检查是否需要重做视频生成
            video_actions = [a for a in stage_actions if "video" in a.target]
            if video_actions:
                self.notify("🎬 重新生成视频（参数已调整）...")
                videos = []
                for shot_id, img_path in keyframes.items():
                    if not img_path:
                        continue
                    shot_prompt = ""
                    for scene in storyboard.get("scenes", []):
                        for shot in scene.get("shots", []):
                            if shot.get("shot_id") == shot_id:
                                shot_prompt = shot.get("video_prompt") or shot.get("motion_prompt", "")
                                break
                    try:
                        v = await self.generate_video(img_path, shot_prompt)
                        if v:
                            videos.append(v)
                    except Exception as e:
                        self.notify(f"⚠️ {shot_id} 生成失败: {e}")
                
                if videos:
                    final_video = await self.assemble_videos(videos)
                    return {
                        "regen_done": True,
                        "final_video": final_video,
                        "new_score": "待评估",
                        "should_recheck": True
                    }
            
            # 检查是否需要重做关键帧
            keyframe_actions = [a for a in stage_actions if "image" in a.target or "keyframe" in a.target]
            if keyframe_actions:
                self.notify("🖼️ 重新生成关键帧（参数已调整）...")
                new_keyframes = await self.generate_all_keyframes(storyboard, character_masters)
                
                # 用新关键帧重新生成视频
                videos = []
                for shot_id, img_path in new_keyframes.items():
                    if not img_path:
                        continue
                    shot_prompt = ""
                    for scene in storyboard.get("scenes", []):
                        for shot in scene.get("shots", []):
                            if shot.get("shot_id") == shot_id:
                                shot_prompt = shot.get("video_prompt") or shot.get("motion_prompt", "")
                                break
                    try:
                        v = await self.generate_video(img_path, shot_prompt)
                        if v:
                            videos.append(v)
                    except:
                        pass
                
                if videos:
                    final_video = await self.assemble_videos(videos)
                    return {
                        "regen_done": True,
                        "final_video": final_video,
                        "new_score": "待评估",
                        "should_recheck": True
                    }
            
            return {"regen_done": False, "reason": "阶段重做无可用操作"}
        
        # ── Full 级别：全流程重跑 ─────────────────────────────
        elif regen_plan == "full":
            self.notify("🔁 全流程重跑（配置已更新）...")
            
            # 保存当前状态用于恢复
            old_config = self.api_config.copy()
            
            # 重新加载最新配置
            self.api_config = self._load_config()
            
            # 重新执行关键阶段（视频生成 + 合成）
            videos = []
            for shot_id, img_path in keyframes.items():
                if not img_path:
                    continue
                shot_prompt = ""
                for scene in storyboard.get("scenes", []):
                    for shot in scene.get("shots", []):
                        if shot.get("shot_id") == shot_id:
                            shot_prompt = shot.get("video_prompt") or shot.get("motion_prompt", "")
                            break
                try:
                    v = await self.generate_video(img_path, shot_prompt)
                    if v:
                        videos.append(v)
                except Exception as e:
                    self.notify(f"⚠️ {shot_id} 失败: {e}")
            
            if videos:
                final_video = await self.assemble_videos(videos)
                return {
                    "regen_done": True,
                    "final_video": final_video,
                    "new_score": "待评估",
                    "should_recheck": True
                }
            
            return {"regen_done": False, "reason": "全流程重做失败"}
        
        return {"regen_done": False, "reason": f"未知重做计划: {regen_plan}"}
