"""
分镜管理系统
参考火宝短剧架构：首帧/关键帧/末帧/面板/动作帧
优化：AI 生成分镜直接返回 character_ids 和 scene_id，不再文本解析匹配
"""

import json
import uuid
import requests
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import List, Optional, Dict, Any
from datetime import datetime


class FrameType(str, Enum):
    FIRST = "first_frame"    # 首帧
    KEY = "key_frame"        # 关键帧
    LAST = "last_frame"      # 末帧
    PANEL = "panel"          # 面板（九宫格序列）
    ACTION = "action"        # 动作帧


class SceneStatus(str, Enum):
    DRAFT = "draft"          # 草稿
    PENDING = "pending"      # 待审批
    APPROVED = "approved"    # 已审批
    REJECTED = "rejected"    # 已拒绝


@dataclass
class StoryboardScene:
    """分镜场景"""
    scene_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    episode_num: int = 1
    scene_num: int = 1
    title: str = ""
    description: str = ""          # 场景描述
    dialogue: str = ""             # 对话台词
    frame_type: FrameType = FrameType.KEY
    image_prompt: str = ""         # AI图像生成提示词
    video_prompt: str = ""         # AI视频生成提示词（与 image_prompt 分离）
    image_path: Optional[str] = None
    video_path: Optional[str] = None
    duration: float = 3.0          # 秒
    status: SceneStatus = SceneStatus.DRAFT
    tags: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    notes: str = ""                # 审批备注

    # === 火宝架构新增：直接引用，不再文本解析 ===
    character_ids: List[str] = field(default_factory=list)  # 出场角色 ID 列表
    background_scene_id: str = ""  # 背景场景 ID，用于背景复用


@dataclass
class Storyboard:
    """完整分镜板"""
    storyboard_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    drama_title: str = ""
    episode_num: int = 1
    scenes: List[StoryboardScene] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


class StoryboardManager:
    """分镜管理器"""

    # AI 生成分镜的 system prompt，要求直接返回结构化 JSON
    AI_SYSTEM_PROMPT = """你是专业的短剧分镜师。
根据剧本生成分镜列表，必须以 JSON 数组返回，每个分镜包含以下字段：
- scene_num: 场景编号（整数）
- title: 场景标题（字符串）
- description: 场景视觉描述，用于图像生成（英文，字符串）
- dialogue: 对话台词（中文，字符串）
- frame_type: 帧类型，枚举值 first_frame/key_frame/last_frame/panel/action
- character_ids: 出场角色 ID 列表（数组，如 ["female_lead", "male_lead"]）
- scene_id: 背景场景 ID（字符串，如 "bedroom", "office", "street"）
- duration: 时长秒数（浮点数）

只返回 JSON 数组，不要任何解释文字。"""

    def __init__(self, output_dir: str = "output/storyboards", api_config: Optional[Dict] = None):
        self.output_dir = output_dir
        self.api_config = api_config or {}
        import os
        os.makedirs(output_dir, exist_ok=True)

    def generate_from_script(self, script: str, episode_num: int = 1, drama_title: str = "") -> Storyboard:
        """从剧本自动生成分镜（文本解析，兼容旧接口）"""
        board = Storyboard(drama_title=drama_title, episode_num=episode_num)
        raw_scenes = self._parse_script(script)

        for i, raw in enumerate(raw_scenes):
            if i == 0:
                frame_type = FrameType.FIRST
            elif i == len(raw_scenes) - 1:
                frame_type = FrameType.LAST
            else:
                frame_type = FrameType.KEY

            scene = StoryboardScene(
                episode_num=episode_num,
                scene_num=i + 1,
                title=raw.get("title", f"场景{i+1}"),
                description=raw.get("description", ""),
                dialogue=raw.get("dialogue", ""),
                frame_type=frame_type,
                image_prompt=self._build_image_prompt(raw),
                video_prompt=self._build_video_prompt(raw),
                duration=raw.get("duration", 3.0),
                character_ids=raw.get("character_ids", []),
                background_scene_id=raw.get("scene_id", ""),
            )
            board.scenes.append(scene)

        return board

    def generate_from_script_ai(
        self,
        script: str,
        episode_num: int = 1,
        drama_title: str = "",
    ) -> Storyboard:
        """
        使用 AI 生成结构化分镜，直接返回 character_ids 和 scene_id。
        AI 返回 JSON，不再做文本解析匹配。
        需要在 api_config["script"] 中配置 LLM 端点。
        """
        board = Storyboard(drama_title=drama_title, episode_num=episode_num)

        raw_scenes = self._ai_generate_scenes(script)
        if not raw_scenes:
            # AI 失败时降级到文本解析
            return self.generate_from_script(script, episode_num, drama_title)

        for i, raw in enumerate(raw_scenes):
            frame_type_str = raw.get("frame_type", "key_frame")
            try:
                frame_type = FrameType(frame_type_str)
            except ValueError:
                frame_type = FrameType.KEY

            scene = StoryboardScene(
                episode_num=episode_num,
                scene_num=raw.get("scene_num", i + 1),
                title=raw.get("title", f"场景{i+1}"),
                description=raw.get("description", ""),
                dialogue=raw.get("dialogue", ""),
                frame_type=frame_type,
                image_prompt=self._build_image_prompt(raw),
                video_prompt=self._build_video_prompt(raw),
                duration=float(raw.get("duration", 3.0)),
                # 直接使用 AI 返回的结构化字段，无需文本解析
                character_ids=raw.get("character_ids", []),
                background_scene_id=raw.get("scene_id", ""),
            )
            board.scenes.append(scene)

        return board

    def _ai_generate_scenes(self, script: str) -> List[Dict[str, Any]]:
        """调用 LLM 生成结构化分镜 JSON"""
        cfg = self.api_config.get("script", {}).get("custom_opus", {})
        if not cfg.get("enabled") or not cfg.get("api_key"):
            return []

        try:
            url = f"{cfg.get('base_url', 'http://47.253.7.24:3000')}/v1/messages"
            headers = {
                "Authorization": f"Bearer {cfg['api_key']}",
                "Content-Type": "application/json",
                "anthropic-version": "2023-06-01",
            }
            data = {
                "model": cfg.get("model", "claude-sonnet-4-6"),
                "max_tokens": 4000,
                "system": self.AI_SYSTEM_PROMPT,
                "messages": [{"role": "user", "content": f"请为以下剧本生成分镜：\n\n{script}"}],
            }
            resp = requests.post(url, headers=headers, json=data, timeout=120)
            resp.raise_for_status()
            text = resp.json()["content"][0]["text"].strip()

            # 提取 JSON 数组（防止 AI 多输出文字）
            start = text.find("[")
            end = text.rfind("]") + 1
            if start == -1 or end == 0:
                return []
            return json.loads(text[start:end])
        except Exception:
            return []

    def _parse_script(self, script: str) -> List[Dict]:
        """解析剧本文本为场景列表（文本解析降级方案）"""
        scenes = []
        blocks = script.strip().split("\n\n")

        for block in blocks:
            if not block.strip():
                continue
            lines = block.strip().split("\n")
            scene: Dict = {"title": "", "description": "", "dialogue": "", "duration": 3.0}

            for line in lines:
                line = line.strip()
                if line.startswith("场景") or line.startswith("Scene"):
                    scene["title"] = line
                elif line.startswith("对话:") or line.startswith("台词:"):
                    scene["dialogue"] = line.split(":", 1)[-1].strip()
                elif line.startswith("[") and line.endswith("]"):
                    scene["description"] = line[1:-1]
                elif line:
                    if not scene["description"]:
                        scene["description"] = line
                    else:
                        scene["dialogue"] += " " + line

            if scene["title"] or scene["description"]:
                scenes.append(scene)

        return scenes if scenes else [{"title": "场景1", "description": script[:200], "dialogue": ""}]

    def _build_image_prompt(self, scene: Dict) -> str:
        """构建静态图像提示词"""
        parts = []
        if scene.get("description"):
            parts.append(scene["description"])
        parts.append("cinematic, dramatic lighting, high quality, 8k, vertical video 9:16")
        return ", ".join(parts)

    def _build_video_prompt(self, scene: Dict) -> str:
        """构建视频提示词（与图像提示词分离）"""
        parts = []
        if scene.get("description"):
            parts.append(scene["description"])
        if scene.get("dialogue"):
            parts.append("emotional expression, lip movement")
        parts.append("smooth motion, cinematic camera, high quality video, 9:16")
        return ", ".join(parts)

    def edit_scene(self, board: Storyboard, scene_id: str, **kwargs) -> bool:
        """编辑指定场景"""
        for scene in board.scenes:
            if scene.scene_id == scene_id:
                for k, v in kwargs.items():
                    if hasattr(scene, k):
                        setattr(scene, k, v)
                scene.updated_at = datetime.now().isoformat()
                return True
        return False

    def approve_scene(self, board: Storyboard, scene_id: str, notes: str = "") -> bool:
        """审批通过场景"""
        return self._set_status(board, scene_id, SceneStatus.APPROVED, notes)

    def reject_scene(self, board: Storyboard, scene_id: str, notes: str = "") -> bool:
        """拒绝场景"""
        return self._set_status(board, scene_id, SceneStatus.REJECTED, notes)

    def approve_all(self, board: Storyboard):
        """批量审批所有草稿场景"""
        for scene in board.scenes:
            if scene.status == SceneStatus.DRAFT:
                scene.status = SceneStatus.APPROVED
                scene.updated_at = datetime.now().isoformat()

    def _set_status(self, board: Storyboard, scene_id: str, status: SceneStatus, notes: str) -> bool:
        for scene in board.scenes:
            if scene.scene_id == scene_id:
                scene.status = status
                scene.notes = notes
                scene.updated_at = datetime.now().isoformat()
                return True
        return False

    def get_approved_scenes(self, board: Storyboard) -> List[StoryboardScene]:
        return [s for s in board.scenes if s.status == SceneStatus.APPROVED]

    def save(self, board: Storyboard) -> str:
        import os
        path = os.path.join(self.output_dir, f"storyboard_{board.storyboard_id}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(asdict(board), f, ensure_ascii=False, indent=2)
        return path

    def load(self, path: str) -> Storyboard:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        board = Storyboard(**{k: v for k, v in data.items() if k != "scenes"})
        board.scenes = [StoryboardScene(**s) for s in data.get("scenes", [])]
        return board

    def summary(self, board: Storyboard) -> str:
        total = len(board.scenes)
        approved = sum(1 for s in board.scenes if s.status == SceneStatus.APPROVED)
        return (f"分镜板: {board.drama_title} 第{board.episode_num}集 | "
                f"共{total}场景 | 已审批{approved} | 待审批{total-approved}")
