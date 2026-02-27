"""
场景管理器
参考火宝短剧架构：Scene 类管理背景库，实现背景复用逻辑
"""

import json
import os
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class Scene:
    """背景场景"""
    scene_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""                      # 场景名称（如：卧室、办公室、街道）
    name_en: str = ""                   # 英文名（用于提示词）
    description: str = ""              # 场景视觉描述（用于图像生成）
    tags: List[str] = field(default_factory=list)  # 标签（室内/室外/白天/夜晚等）
    reference_image: Optional[str] = None  # 参考图路径
    seed_value: Optional[int] = None   # 背景生成种子，确保复用一致性
    usage_count: int = 0               # 使用次数（复用统计）

    def to_prompt_fragment(self) -> str:
        """转换为提示词片段"""
        parts = []
        if self.description:
            parts.append(self.description)
        if self.tags:
            parts.extend(self.tags)
        return ", ".join(parts)

    def to_dict(self) -> dict:
        return {
            "scene_id": self.scene_id,
            "name": self.name,
            "name_en": self.name_en,
            "description": self.description,
            "tags": self.tags,
            "reference_image": self.reference_image,
            "seed_value": self.seed_value,
            "usage_count": self.usage_count,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Scene":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


# 默认背景场景库
DEFAULT_SCENES: Dict[str, Scene] = {
    "bedroom": Scene(
        scene_id="bedroom",
        name="卧室",
        name_en="bedroom",
        description="cozy bedroom interior, soft lighting, modern furniture",
        tags=["indoor", "private", "warm lighting"],
        seed_value=50001,
    ),
    "office": Scene(
        scene_id="office",
        name="办公室",
        name_en="office",
        description="modern office interior, professional environment, city view window",
        tags=["indoor", "professional", "daytime"],
        seed_value=50002,
    ),
    "street": Scene(
        scene_id="street",
        name="街道",
        name_en="street",
        description="urban street, city background, pedestrians, natural lighting",
        tags=["outdoor", "urban", "daytime"],
        seed_value=50003,
    ),
    "restaurant": Scene(
        scene_id="restaurant",
        name="餐厅",
        name_en="restaurant",
        description="elegant restaurant interior, warm ambiance, dining tables",
        tags=["indoor", "social", "warm lighting"],
        seed_value=50004,
    ),
    "living_room": Scene(
        scene_id="living_room",
        name="客厅",
        name_en="living room",
        description="comfortable living room, family space, sofa and TV",
        tags=["indoor", "family", "warm"],
        seed_value=50005,
    ),
    "hospital": Scene(
        scene_id="hospital",
        name="医院",
        name_en="hospital",
        description="hospital corridor, clean white walls, medical environment",
        tags=["indoor", "medical", "bright lighting"],
        seed_value=50006,
    ),
    "park": Scene(
        scene_id="park",
        name="公园",
        name_en="park",
        description="beautiful park, green trees, natural scenery, peaceful",
        tags=["outdoor", "nature", "daytime"],
        seed_value=50007,
    ),
    "night_city": Scene(
        scene_id="night_city",
        name="夜晚城市",
        name_en="night city",
        description="city at night, neon lights, urban nightscape, dramatic",
        tags=["outdoor", "urban", "night", "dramatic"],
        seed_value=50008,
    ),
}


class SceneManager:
    """
    背景场景管理器
    支持场景库持久化和跨项目复用
    """

    def __init__(self, library_path: str = "data/scene_library.json"):
        self.library_path = library_path
        self.scenes: Dict[str, Scene] = {}
        self._load()

    def _load(self):
        """加载场景库，合并默认场景"""
        self.scenes = {**DEFAULT_SCENES}
        if os.path.exists(self.library_path):
            try:
                with open(self.library_path, encoding="utf-8") as f:
                    data = json.load(f)
                for sid, sdata in data.items():
                    self.scenes[sid] = Scene.from_dict(sdata)
            except Exception:
                pass

    def save(self):
        """持久化场景库"""
        os.makedirs(os.path.dirname(self.library_path) or ".", exist_ok=True)
        with open(self.library_path, "w", encoding="utf-8") as f:
            json.dump(
                {sid: s.to_dict() for sid, s in self.scenes.items()},
                f, ensure_ascii=False, indent=2
            )

    def get(self, scene_id: str) -> Optional[Scene]:
        """获取场景，并记录使用次数"""
        scene = self.scenes.get(scene_id)
        if scene:
            scene.usage_count += 1
        return scene

    def get_prompt(self, scene_id: str) -> str:
        """直接获取场景提示词片段，用于注入图像/视频 prompt"""
        scene = self.get(scene_id)
        return scene.to_prompt_fragment() if scene else ""

    def add(self, scene: Scene):
        """添加或更新场景"""
        self.scenes[scene.scene_id] = scene

    def find_by_tag(self, tag: str) -> List[Scene]:
        """按标签查找场景"""
        return [s for s in self.scenes.values() if tag in s.tags]

    def find_by_name(self, name: str) -> Optional[Scene]:
        """按中文名查找场景"""
        for s in self.scenes.values():
            if s.name == name or s.name_en == name:
                return s
        return None

    def inject_into_prompt(self, prompt: str, scene_id: str) -> str:
        """将背景场景描述注入到提示词中"""
        fragment = self.get_prompt(scene_id)
        if not fragment:
            return prompt
        return f"{prompt}, {fragment}"

    def list_all(self) -> List[Dict]:
        """列出所有场景（用于 UI 展示）"""
        return [s.to_dict() for s in self.scenes.values()]
