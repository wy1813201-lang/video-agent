"""
角色一致性模块
确保跨场景的角色外观、服装、性格保持一致
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


# 默认角色模板库
DEFAULT_CHARACTER_TEMPLATES: Dict[str, CharacterTrait] = {
    "女主": CharacterTrait(
        name="女主",
        appearance="beautiful young woman, long black hair, fair skin, expressive eyes",
        outfit="elegant casual wear",
        personality="determined, emotional",
        age_range="early 20s",
        gender="female",
        extra_tags=["protagonist", "detailed face"]
    ),
    "男主": CharacterTrait(
        name="男主",
        appearance="handsome young man, short dark hair, strong jawline",
        outfit="smart casual outfit",
        personality="confident, mysterious",
        age_range="mid 20s",
        gender="male",
        extra_tags=["male protagonist", "detailed face"]
    ),
    "妈妈": CharacterTrait(
        name="妈妈",
        appearance="middle-aged woman, gentle face, warm smile",
        outfit="homely comfortable clothes",
        personality="caring, warm",
        age_range="late 40s",
        gender="female",
        extra_tags=["mother figure"]
    ),
    "爸爸": CharacterTrait(
        name="爸爸",
        appearance="middle-aged man, mature face, kind eyes",
        outfit="casual shirt",
        personality="steady, protective",
        age_range="late 40s",
        gender="male",
        extra_tags=["father figure"]
    ),
    "反派": CharacterTrait(
        name="反派",
        appearance="sharp features, cold eyes, intimidating presence",
        outfit="formal business attire",
        personality="cunning, ruthless",
        age_range="30s to 40s",
        gender="male",
        extra_tags=["antagonist", "villain"]
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
            # 跳过已知关键词和旁白
            if name in ("旁白", "字幕", "画外音") or name in found:
                continue
            # 如果不在模板里，创建一个通用角色
            if name not in self.templates:
                found[name] = CharacterTrait(
                    name=name,
                    appearance="character with distinct features",
                    outfit="appropriate attire",
                    personality="expressive",
                    extra_tags=["supporting character", "detailed face"]
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

    def enhance(self, base_prompt: str, scene_text: str) -> str:
        """
        根据场景文本中出现的角色，增强基础提示词

        Args:
            base_prompt: 原始场景提示词
            scene_text:  对应的剧本场景文本（用于检测角色）

        Returns:
            注入了角色特征的增强提示词
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

        # 也检查自定义角色名
        for name, trait in self.characters.items():
            if name in CHARACTER_KEYWORDS:
                continue  # 已处理
            if name in scene_text:
                fragment = trait.to_prompt_fragment()
                if fragment:
                    character_fragments.append(fragment)

        if not character_fragments:
            return base_prompt

        character_str = " | ".join(character_fragments)
        return f"{base_prompt}, {character_str}, consistent character design"

    def enhance_batch(
        self, prompts: List[str], scene_texts: List[str]
    ) -> List[str]:
        """批量增强提示词列表"""
        if len(prompts) != len(scene_texts):
            raise ValueError("prompts 和 scene_texts 长度必须一致")
        return [
            self.enhance(p, s) for p, s in zip(prompts, scene_texts)
        ]
