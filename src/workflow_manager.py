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
    """工作流阶段"""
    SCRIPT = "剧本生成"
    IMAGE_PROMPTS = "提示词生成"
    IMAGE_GEN = "图像生成"
    VIDEO_GEN = "视频生成"
    ASSEMBLY = "视频合成"
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
    """工作流状态"""
    stage: Stage = Stage.SCRIPT
    progress: float = 0.0
    message: str = ""
    current_item: str = ""
    total_items: int = 0
    completed_items: int = 0

    # 数据
    script: str = ""
    prompts: List[str] = field(default_factory=list)
    scene_texts: List[str] = field(default_factory=list)
    images: List[str] = field(default_factory=list)
    videos: List[str] = field(default_factory=list)

    # 用户干预
    user_feedback: str = ""
    needs_approval: bool = False
    approved: bool = False

    # 质量追踪
    quality_results: Dict[str, QualityResult] = field(default_factory=dict)
    regen_counts: Dict[str, int] = field(default_factory=dict)  # item_key -> 重试次数


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
        """运行完整工作流"""

        # ===== 阶段 1: 剧本生成 =====
        await self.update_progress(Stage.SCRIPT, 0.05, "正在生成剧本...", "第1集", 3, 0)

        script = await self.generate_script(config)
        self.state.script = script

        # 剧本质量检测
        await self.run_quality_check("script", script, "script_main")

        self.state.completed_items = 3
        self.state.needs_approval = True
        await self.update_progress(Stage.SCRIPT, 0.15, "剧本生成完成，请审批", "3集已完成", 3, 3)
        await self.wait_for_approval()

        # 如果用户拒绝并提供反馈，重新生成
        if self.state.user_feedback:
            self.notify(f"📝 根据反馈重新生成剧本: {self.state.user_feedback}")
            script = await self.generate_script(config)
            self.state.script = script
            self.state.user_feedback = ""

        # ===== 阶段 2: 提示词生成 =====
        await self.update_progress(Stage.IMAGE_PROMPTS, 0.2, "正在生成图像提示词...", "场景1", 12, 0)

        prompts = await self.generate_prompts(script)
        self.state.prompts = prompts
        self.state.completed_items = 12
        await self.update_progress(Stage.IMAGE_PROMPTS, 0.3, "提示词生成完成，请审批", "12个场景", 12, 12)

        self.state.needs_approval = True
        await self.wait_for_approval()

        # ===== 阶段 3: 图像生成（含审批点 + 质量检测 + 重试）=====
        await self.update_progress(Stage.IMAGE_GEN, 0.35, "正在生成图像...", "场景1/12", 12, 0)

        images = []
        for i, prompt in enumerate(prompts):
            if self.paused:
                await self.wait_for_approval()

            item_key = f"image_{i+1}"

            # 带重试的图像生成
            img = await self.regenerate_with_retry(
                item_key, self.generate_image, "image", prompt
            )
            images.append(img)

            progress = 0.35 + (i + 1) / len(prompts) * 0.2
            await self.update_progress(
                Stage.IMAGE_GEN, progress,
                f"已生成 {i+1}/{len(prompts)}",
                f"场景{i+1}", len(prompts), i + 1,
            )

            # 每4张图像设置一个审批点
            if (i + 1) % 4 == 0 and (i + 1) < len(prompts):
                self.notify(f"📸 已完成 {i+1} 张图像，请审批后继续")
                self.state.needs_approval = True
                await self.wait_for_approval()

        self.state.images = images

        # ===== 阶段 4: 视频生成（含质量检测 + 重试）=====
        await self.update_progress(Stage.VIDEO_GEN, 0.6, "正在生成视频...", "片段1/12", 12, 0)

        videos = []
        for i, img in enumerate(images):
            if self.paused:
                await self.wait_for_approval()

            item_key = f"video_{i+1}"

            video = await self.regenerate_with_retry(
                item_key, self.generate_video, "video", img
            )
            videos.append(video)

            progress = 0.6 + (i + 1) / len(images) * 0.3
            await self.update_progress(
                Stage.VIDEO_GEN, progress,
                f"已生成 {i+1}/{len(images)}",
                f"片段{i+1}", len(images), i + 1,
            )

        self.state.videos = videos

        # ===== 阶段 5: 视频合成 =====
        await self.update_progress(Stage.ASSEMBLY, 0.95, "正在合成最终视频...", "合并中", 1, 0)

        final_video = await self.assemble_videos(videos)

        await self.update_progress(Stage.COMPLETE, 1.0, "✅ 全部完成！", final_video, 1, 1)

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

    async def generate_video(self, image_path):
        """生成视频 - 调用 JimengVideoClient"""
        from jimeng_client import JimengVideoClient

        video_cfg = self.api_config.get("video", {}).get("jimeng", {})
        if not video_cfg.get("enabled"):
            self.notify("⚠️ 即梦视频 API 未启用，跳过视频生成")
            return ""

        client = JimengVideoClient()

        # 用图像路径对应的提示词（或用通用提示词）
        prompt_suffix = self.api_config.get("prompt", {}).get(
            "video_quality_suffix", "smooth motion, cinematic, high quality video"
        )
        prompt = f"cinematic short drama scene, {prompt_suffix}"

        resolution = video_cfg.get("default_resolution", "720p")

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: client.video_generation(
                prompt=prompt,
                resolution=resolution,
                aspect_ratio="9:16",
            ),
        )

        video_path = result.get("video_path", "")
        self.notify(f"🎬 视频已保存: {Path(video_path).name if video_path else '无'}")
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
