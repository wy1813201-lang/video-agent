"""
提示词生成器
为AI图像/视频生成工具创建提示词
参考火宝短剧架构优化：image/video prompt 分离，FramePrompt 多帧类型支持
"""

import re
from typing import List, Dict, Optional
from dataclasses import dataclass, field
from enum import Enum


class FrameType(str, Enum):
    """帧类型，参考火宝架构"""
    FIRST = "first"    # 首帧 - 场景开场
    KEY = "key"        # 关键帧 - 核心情节
    LAST = "last"      # 末帧 - 场景收尾
    PANEL = "panel"    # 面板 - 九宫格序列帧
    ACTION = "action"  # 动作帧 - 运动/转场


@dataclass
class FramePrompt:
    """
    单帧提示词，支持 image/video 分离
    参考火宝：每帧独立管理图像提示和视频提示
    """
    frame_type: FrameType = FrameType.KEY
    scene_num: int = 1
    frame_index: int = 0               # 同场景内的帧序号

    # 图像提示词（用于静态图生成，如 doubao-seedream）
    image_prompt: str = ""
    # 视频提示词（用于视频生成，如 doubao-seedance / kling）
    video_prompt: str = ""

    # 角色 ID 列表（直接引用，不再文本解析）
    character_ids: List[str] = field(default_factory=list)
    # 场景 ID（背景复用）
    scene_id: str = ""

    # 附加参数
    duration: float = 3.0              # 视频时长（秒）
    seed: Optional[int] = None         # 图像种子值
    aspect_ratio: str = "9:16"         # 画面比例

    def to_dict(self) -> dict:
        return {
            "frame_type": self.frame_type.value,
            "scene_num": self.scene_num,
            "frame_index": self.frame_index,
            "image_prompt": self.image_prompt,
            "video_prompt": self.video_prompt,
            "character_ids": self.character_ids,
            "scene_id": self.scene_id,
            "duration": self.duration,
            "seed": self.seed,
            "aspect_ratio": self.aspect_ratio,
        }


@dataclass
class ScenePrompt:
    """场景提示词（兼容旧接口）"""
    scene_num: int
    description: str
    character_prompt: str
    environment_prompt: str
    mood_prompt: str
    full_prompt: str


class PromptBuilder:
    """AI图像/视频提示词生成器"""

    # 常用风格关键词
    STYLE_KEYWORDS = {
        "电影感": "cinematic, film grain, professional cinematography",
        "动漫": "anime style, manga, Japanese animation",
        "写实": "photorealistic, realistic, 8k, detailed",
        "水彩": "watercolor painting, artistic, soft colors",
        "油画": "oil painting style, classic art",
        "3D": "3D render, C4D, octane render, detailed",
    }

    # 情绪关键词
    MOOD_KEYWORDS = {
        "紧张": "tense, suspenseful, dark atmosphere",
        "温馨": "warm, cozy, soft lighting, heartwarming",
        "浪漫": "romantic, dreamy, soft focus, bokeh",
        "悲伤": "sad, melancholic, tearful, emotional",
        "恐怖": "scary, horror, dark, eerie",
        "搞笑": "funny, comedic, humorous, exaggerated",
    }

    # 帧类型对应的视频运镜提示
    FRAME_MOTION_HINTS = {
        FrameType.FIRST: "slow zoom in, establishing shot",
        FrameType.KEY: "subtle camera movement, focus pull",
        FrameType.LAST: "slow zoom out, fade",
        FrameType.PANEL: "static shot, no camera movement",
        FrameType.ACTION: "dynamic camera, fast movement, action shot",
    }

    def __init__(self, config):
        self.config = config
        self.style = config.style

    def generate_scene_prompts(self, script: str) -> List[str]:
        """从剧本生成场景提示词（兼容旧接口）"""
        scenes = self._parse_scenes(script)
        return [self._build_prompt(scene) for scene in scenes]

    def generate_frame_prompts(
        self,
        scenes: List[Dict],
        character_map: Optional[Dict[str, str]] = None,
        scene_id_map: Optional[Dict[int, str]] = None,
    ) -> List[FramePrompt]:
        """
        生成帧级提示词列表，image/video 分离。
        参考火宝架构：每个场景生成首帧+关键帧+末帧。

        Args:
            scenes: 场景字典列表，每项含 scene_num / description / dialogue /
                    character_ids / scene_id 等字段
            character_map: character_id -> prompt_fragment 映射
            scene_id_map: scene_num -> scene_id 映射

        Returns:
            FramePrompt 列表
        """
        character_map = character_map or {}
        scene_id_map = scene_id_map or {}
        result: List[FramePrompt] = []

        for scene in scenes:
            scene_num = scene.get("scene_num", 1)
            description = scene.get("description", "")
            dialogue = scene.get("dialogue", "")
            char_ids: List[str] = scene.get("character_ids", [])
            scene_id = scene.get("scene_id", scene_id_map.get(scene_num, ""))

            # 角色提示片段
            char_fragment = ", ".join(
                character_map[cid] for cid in char_ids if cid in character_map
            )

            base_image = self._build_image_base(description, char_fragment)
            base_video = self._build_video_base(description, dialogue, char_fragment)
            style_suffix = self._get_style_prompt()

            # 首帧
            result.append(FramePrompt(
                frame_type=FrameType.FIRST,
                scene_num=scene_num,
                frame_index=0,
                image_prompt=f"{base_image}, establishing shot, {style_suffix}",
                video_prompt=f"{base_video}, {self.FRAME_MOTION_HINTS[FrameType.FIRST]}",
                character_ids=char_ids,
                scene_id=scene_id,
                duration=2.0,
            ))

            # 关键帧
            result.append(FramePrompt(
                frame_type=FrameType.KEY,
                scene_num=scene_num,
                frame_index=1,
                image_prompt=f"{base_image}, dramatic moment, {style_suffix}",
                video_prompt=f"{base_video}, {self.FRAME_MOTION_HINTS[FrameType.KEY]}",
                character_ids=char_ids,
                scene_id=scene_id,
                duration=scene.get("duration", 3.0),
            ))

            # 末帧
            result.append(FramePrompt(
                frame_type=FrameType.LAST,
                scene_num=scene_num,
                frame_index=2,
                image_prompt=f"{base_image}, scene ending, {style_suffix}",
                video_prompt=f"{base_video}, {self.FRAME_MOTION_HINTS[FrameType.LAST]}",
                character_ids=char_ids,
                scene_id=scene_id,
                duration=2.0,
            ))

        return result

    def _build_image_base(self, description: str, char_fragment: str) -> str:
        """构建图像基础提示词"""
        parts = [p for p in [description, char_fragment] if p]
        parts.append("high quality, 8k, detailed, masterpiece, vertical 9:16")
        return ", ".join(parts)

    def _build_video_base(self, description: str, dialogue: str, char_fragment: str) -> str:
        """构建视频基础提示词（更注重动态和情绪）"""
        parts = [p for p in [description, char_fragment] if p]
        if dialogue:
            # 从对话推断情绪
            mood = self._infer_mood_from_dialogue(dialogue)
            if mood:
                parts.append(mood)
        parts.append("cinematic, smooth motion, high quality video")
        return ", ".join(parts)

    def _infer_mood_from_dialogue(self, dialogue: str) -> str:
        """从对话文本推断情绪提示"""
        for mood_cn, mood_en in self.MOOD_KEYWORDS.items():
            if mood_cn in dialogue:
                return mood_en
        return ""

    def _parse_scenes(self, script: str) -> List[Dict]:
        """解析剧本中的场景"""
        scenes = []
        scene_blocks = re.split(r'场景\d+:', script)

        for i, block in enumerate(scene_blocks[1:], 1):
            lines = block.strip().split('\n')
            description, dialogue = "", ""

            for line in lines:
                line = line.strip()
                if not line:
                    continue
                if '[' in line and ']' in line:
                    description += line + " "
                elif ':' in line and not line.startswith('#'):
                    dialogue += line + " "

            scenes.append({
                "scene_num": i,
                "description": description.strip(),
                "dialogue": dialogue.strip(),
                "character_ids": [],
                "scene_id": "",
            })

        return scenes

    def _build_prompt(self, scene: Dict) -> str:
        """构建完整提示词（兼容旧接口）"""
        parts = []
        desc = scene.get("description", "")
        if desc:
            parts.append(desc)
        if scene.get("dialogue"):
            parts.append(self._extract_character_hint(scene["dialogue"]))
        parts.append(self._get_style_prompt())
        parts.append(self._get_mood_prompt())
        parts.append("high quality, 8k, detailed, masterpiece")
        return ", ".join(parts)

    def _extract_character_hint(self, dialogue: str) -> str:
        hints = []
        if any(w in dialogue for w in ["男主", "男生", "男人", "他"]):
            hints.append("handsome male character")
        if any(w in dialogue for w in ["女主", "女生", "女人", "她"]):
            hints.append("beautiful female character")
        if any(w in dialogue for w in ["妈妈", "母亲", "爸", "父亲"]):
            hints.append("middle-aged character")
        if any(w in dialogue for w in ["老师", "医生", "警察"]):
            hints.append("professional attire")
        return ", ".join(hints) if hints else "character"

    def _get_style_prompt(self) -> str:
        style_map = {
            "情感": "cinematic, romantic, soft lighting, emotional",
            "悬疑": "dark, mysterious, suspenseful, thriller",
            "搞笑": "comedy, funny, bright, humorous",
            "科幻": "sci-fi, futuristic, technology, neon lights",
        }
        return style_map.get(self.style, "cinematic, high quality")

    def _get_mood_prompt(self) -> str:
        return "expressive, detailed face, professional photography"


class PromptOptimizer:
    """提示词优化器 - 针对不同平台优化"""

    @staticmethod
    def for_midjourney(prompt: str) -> str:
        return f"{prompt}, --ar 9:16 --v 6 --style expressive"

    @staticmethod
    def for_stable_diffusion(prompt: str) -> str:
        return prompt

    @staticmethod
    def for_dalle(prompt: str) -> str:
        return f"{prompt}, cinematic shot, high quality"

    @staticmethod
    def for_kling(prompt: str) -> str:
        return f"{prompt}, high quality, cinematic"

    @staticmethod
    def for_seedream(prompt: str) -> str:
        """优化为豆包 Seedream 图像格式"""
        return f"{prompt}, high quality, 8k, vertical 9:16"

    @staticmethod
    def for_seedance(prompt: str) -> str:
        """优化为豆包 Seedance 视频格式"""
        return f"{prompt}, smooth motion, cinematic, high quality video"
