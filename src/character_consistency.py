"""
角色一致性模块
确保跨场景的角色外观、服装、性格保持一致
参考火宝短剧架构优化：增加 seed_value、role、reference_images、voice_style 字段
"""

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class CharacterTrait:
    """角色特征数据结构"""
    name: str                          # 角色名称（如：女主、男主、妈妈）
    appearance: str = ""               # 外貌描述（发型、肤色、五官）
    outfit: str = ""                   # 服装描述
    personality: str = ""              # 性格特征
    age_range: str = ""                # 年龄段
    gender: str = ""                   # 性别
    extra_tags: List[str] = field(default_factory=list)  # 额外提示词标签

    # === 火宝架构新增字段 ===
    seed_value: Optional[int] = None   # 图像生成种子值，确保角色外观一致性
    role: str = ""                     # 角色定位（如：protagonist/antagonist/supporting）
    reference_images: List[str] = field(default_factory=list)  # 参考图路径或URL列表
    voice_style: str = ""              # 语音风格（如：温柔女声、低沉男声）

    # === IP-Adapter 专用 ===
    ip_adapter_scale: float = 0.7     # IP-Adapter 一致性强度 (0-1)
    use_ip_adapter: bool = True        # 是否启用 IP-Adapter

    def to_prompt_fragment(self) -> str:
        """转换为图像提示词片段"""
        parts = []
        if self.appearance:
            parts.append(self.appearance)
        if self.outfit:
            parts.append(self.outfit)
        if self.age_range:
            parts.append(self.age_range)
        if self.extra_tags:
            parts.extend(self.extra_tags)
        return ", ".join(parts)

    def to_dict(self) -> dict:
        """序列化为字典，用于持久化"""
        return {
            "name": self.name,
            "appearance": self.appearance,
            "outfit": self.outfit,
            "personality": self.personality,
            "age_range": self.age_range,
            "gender": self.gender,
            "extra_tags": self.extra_tags,
            "seed_value": self.seed_value,
            "role": self.role,
            "reference_images": self.reference_images,
            "voice_style": self.voice_style,
            "ip_adapter_scale": self.ip_adapter_scale,
            "use_ip_adapter": self.use_ip_adapter,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CharacterTrait":
        """从字典反序列化"""
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


# 默认角色模板库
DEFAULT_CHARACTER_TEMPLATES: Dict[str, CharacterTrait] = {
    "女主": CharacterTrait(
        name="女主",
        appearance="beautiful young woman, long black hair, fair skin, expressive eyes",
        outfit="elegant casual wear",
        personality="determined, emotional",
        age_range="early 20s",
        gender="female",
        extra_tags=["protagonist", "detailed face"],
        seed_value=42001,
        role="protagonist",
        reference_images=[],
        voice_style="温柔女声",
    ),
    "男主": CharacterTrait(
        name="男主",
        appearance="handsome young man, short dark hair, strong jawline",
        outfit="smart casual outfit",
        personality="confident, mysterious",
        age_range="mid 20s",
        gender="male",
        extra_tags=["male protagonist", "detailed face"],
        seed_value=42002,
        role="protagonist",
        reference_images=[],
        voice_style="低沉男声",
    ),
    "妈妈": CharacterTrait(
        name="妈妈",
        appearance="middle-aged woman, gentle face, warm smile",
        outfit="homely comfortable clothes",
        personality="caring, warm",
        age_range="late 40s",
        gender="female",
        extra_tags=["mother figure"],
        seed_value=42003,
        role="supporting",
        reference_images=[],
        voice_style="温和女声",
    ),
    "爸爸": CharacterTrait(
        name="爸爸",
        appearance="middle-aged man, mature face, kind eyes",
        outfit="casual shirt",
        personality="steady, protective",
        age_range="late 40s",
        gender="male",
        extra_tags=["father figure"],
        seed_value=42004,
        role="supporting",
        reference_images=[],
        voice_style="沉稳男声",
    ),
    "反派": CharacterTrait(
        name="反派",
        appearance="sharp features, cold eyes, intimidating presence",
        outfit="formal business attire",
        personality="cunning, ruthless",
        age_range="30s to 40s",
        gender="male",
        extra_tags=["antagonist", "villain"],
        seed_value=42005,
        role="antagonist",
        reference_images=[],
        voice_style="冷酷男声",
    ),
}

# 角色名称关键词映射
CHARACTER_KEYWORDS: Dict[str, List[str]] = {
    "女主": ["女主", "她", "女生", "女孩", "主角（女）"],
    "男主": ["男主", "他", "男生", "男孩", "主角（男）"],
    "妈妈": ["妈妈", "母亲", "妈", "老妈"],
    "爸爸": ["爸爸", "父亲", "爸", "老爸"],
    "反派": ["反派", "坏人", "对手", "仇人"],
}


class CharacterExtractor:
    """从剧本中提取角色信息"""

    def __init__(self, custom_templates: Optional[Dict[str, CharacterTrait]] = None):
        self.templates = {**DEFAULT_CHARACTER_TEMPLATES}
        if custom_templates:
            self.templates.update(custom_templates)

    def extract_characters(self, script: str) -> Dict[str, CharacterTrait]:
        """
        从剧本文本中识别出现的角色，返回角色名 -> CharacterTrait 映射
        """
        found: Dict[str, CharacterTrait] = {}

        for role_key, keywords in CHARACTER_KEYWORDS.items():
            for kw in keywords:
                if kw in script:
                    found[role_key] = self.templates[role_key]
                    break

        # 尝试提取自定义角色名（格式：角色名: 台词）
        custom_names = re.findall(r'^([^\[\]#\n:：]{1,8})[：:].+', script, re.MULTILINE)
        for name in custom_names:
            name = name.strip()
            if name in ("旁白", "字幕", "画外音") or name in found:
                continue
            if name not in self.templates:
                found[name] = CharacterTrait(
                    name=name,
                    appearance="character with distinct features",
                    outfit="appropriate attire",
                    personality="expressive",
                    extra_tags=["supporting character", "detailed face"],
                    role="supporting",
                )

        return found

    def update_character(self, role_key: str, trait: CharacterTrait):
        """手动更新或添加角色模板"""
        self.templates[role_key] = trait


class PromptEnhancer:
    """
    图像提示词增强器
    将角色特征注入到场景提示词中，确保跨场景一致性
    """

    def __init__(self, characters: Dict[str, CharacterTrait]):
        self.characters = characters
        # 尝试导入 prompt_builder 的角色一致性功能
        try:
            from src.prompt_builder import CharacterConsistencyPrompt
            self.consistency_prompt = CharacterConsistencyPrompt
        except ImportError:
            self.consistency_prompt = None

    def enhance(
        self,
        base_prompt: str,
        scene_text: str,
        use_ip_adapter: bool = True,
        use_lora: bool = False,
        lora_name: str = None,
    ) -> str:
        """
        根据场景文本中出现的角色，增强基础提示词

        Args:
            base_prompt: 基础提示词
            scene_text: 场景描述文本
            use_ip_adapter: 是否添加 IP-Adapter 提示词
            use_lora: 是否添加 LoRA 提示词
            lora_name: LoRA 名称（如果使用 LoRA）
        """
        character_fragments = []

        for role_key, keywords in CHARACTER_KEYWORDS.items():
            if role_key not in self.characters:
                continue
            for kw in keywords:
                if kw in scene_text:
                    fragment = self.characters[role_key].to_prompt_fragment()
                    if fragment:
                        character_fragments.append(fragment)
                    break

        for name, trait in self.characters.items():
            if name in CHARACTER_KEYWORDS:
                continue
            if name in scene_text:
                fragment = trait.to_prompt_fragment()
                if fragment:
                    character_fragments.append(fragment)

        if not character_fragments:
            # 无角色，也需要基础一致性
            if self.consistency_prompt and use_ip_adapter:
                return self.consistency_prompt.build_consistent_prompt(
                    base_prompt, enhance_face=True
                )
            return base_prompt

        character_str = " | ".join(character_fragments)
        enhanced = f"{base_prompt}, {character_str}, consistent character design"

        # 添加角色一致性增强
        if self.consistency_prompt:
            # 尝试获取第一个出现的角色名
            char_name = None
            for role_key, keywords in CHARACTER_KEYWORDS.items():
                for kw in keywords:
                    if kw in scene_text:
                        char_name = self.characters.get(role_key, CharacterTrait(name=role_key)).name
                        break
                if char_name:
                    break

            enhanced = self.consistency_prompt.build_consistent_prompt(
                enhanced,
                character_name=char_name,
                use_ip_adapter=use_ip_adapter,
                use_lora=use_lora,
                lora_name=lora_name,
                enhance_face=True,
            )

        return enhanced

    def enhance_batch(
        self,
        prompts: List[str],
        scene_texts: List[str],
        use_ip_adapter: bool = True,
        use_lora: bool = False,
        lora_name: str = None,
    ) -> List[str]:
        """批量增强提示词列表"""
        if len(prompts) != len(scene_texts):
            raise ValueError("prompts 和 scene_texts 长度必须一致")
        return [
            self.enhance(p, s, use_ip_adapter, use_lora, lora_name)
            for p, s in zip(prompts, scene_texts)
        ]
