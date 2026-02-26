"""
分镜管理系统
参考火宝短剧架构：首帧/关键帧/末帧/面板
"""

import json
import uuid
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import List, Optional, Dict
from datetime import datetime


class FrameType(str, Enum):
    FIRST = "first_frame"    # 首帧
    KEY = "key_frame"        # 关键帧
    LAST = "last_frame"      # 末帧
    PANEL = "panel"          # 面板（九宫格序列）


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
    image_path: Optional[str] = None
    video_path: Optional[str] = None
    duration: float = 3.0          # 秒
    status: SceneStatus = SceneStatus.DRAFT
    tags: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    notes: str = ""                # 审批备注


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

    def __init__(self, output_dir: str = "output/storyboards"):
        self.output_dir = output_dir
        import os
        os.makedirs(output_dir, exist_ok=True)

    def generate_from_script(self, script: str, episode_num: int = 1, drama_title: str = "") -> Storyboard:
        """从剧本自动生成分镜"""
        board = Storyboard(drama_title=drama_title, episode_num=episode_num)
        raw_scenes = self._parse_script(script)

        for i, raw in enumerate(raw_scenes):
            # 首场景为首帧，末场景为末帧，其余为关键帧
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
                duration=raw.get("duration", 3.0),
            )
            board.scenes.append(scene)

        return board

    def _parse_script(self, script: str) -> List[Dict]:
        """解析剧本文本为场景列表"""
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
        """构建AI图像生成提示词"""
        parts = []
        if scene.get("description"):
            parts.append(scene["description"])
        parts.append("cinematic, dramatic lighting, high quality, 8k, vertical video 9:16")
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
