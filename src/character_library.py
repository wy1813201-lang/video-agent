"""
角色库
参考火宝短剧架构：持久化角色库，支持跨项目复用
"""

import json
import os
from typing import Dict, List, Optional

from character_consistency import CharacterTrait, DEFAULT_CHARACTER_TEMPLATES


class CharacterLibrary:
    """
    持久化角色库
    - 支持跨项目复用角色
    - 合并默认模板与自定义角色
    - 提供按 ID / 名称 / 角色定位查询
    """

    def __init__(self, library_path: str = "data/character_library.json"):
        self.library_path = library_path
        self.characters: Dict[str, CharacterTrait] = {}
        self._load()

    def _load(self):
        """加载角色库，合并默认模板"""
        # 先加载默认模板
        self.characters = {
            k: v for k, v in DEFAULT_CHARACTER_TEMPLATES.items()
        }
        # 再从文件覆盖/追加
        if os.path.exists(self.library_path):
            try:
                with open(self.library_path, encoding="utf-8") as f:
                    data = json.load(f)
                for cid, cdata in data.items():
                    self.characters[cid] = CharacterTrait.from_dict(cdata)
            except Exception:
                pass

    def save(self):
        """持久化角色库到文件"""
        os.makedirs(os.path.dirname(self.library_path) or ".", exist_ok=True)
        with open(self.library_path, "w", encoding="utf-8") as f:
            json.dump(
                {cid: c.to_dict() for cid, c in self.characters.items()},
                f, ensure_ascii=False, indent=2
            )

    def get(self, character_id: str) -> Optional[CharacterTrait]:
        """按 ID 获取角色"""
        return self.characters.get(character_id)

    def get_prompt_fragment(self, character_id: str) -> str:
        """直接获取角色提示词片段，用于注入 image/video prompt"""
        char = self.get(character_id)
        return char.to_prompt_fragment() if char else ""

    def get_seed(self, character_id: str) -> Optional[int]:
        """获取角色的 seed_value，用于图像生成保持一致性"""
        char = self.get(character_id)
        return char.seed_value if char else None

    def get_voice_style(self, character_id: str) -> str:
        """获取角色语音风格"""
        char = self.get(character_id)
        return char.voice_style if char else ""

    def add(self, character_id: str, trait: CharacterTrait):
        """添加或更新角色"""
        self.characters[character_id] = trait

    def remove(self, character_id: str) -> bool:
        """删除角色（默认模板不可删除）"""
        if character_id in DEFAULT_CHARACTER_TEMPLATES:
            return False
        if character_id in self.characters:
            del self.characters[character_id]
            return True
        return False

    def find_by_role(self, role: str) -> List[CharacterTrait]:
        """按角色定位查找（protagonist / antagonist / supporting）"""
        return [c for c in self.characters.values() if c.role == role]

    def find_by_name(self, name: str) -> Optional[CharacterTrait]:
        """按角色名查找"""
        for c in self.characters.values():
            if c.name == name:
                return c
        return None

    def resolve_ids(self, character_ids: List[str]) -> Dict[str, str]:
        """
        将角色 ID 列表解析为 {id: prompt_fragment} 映射
        供 PromptBuilder.generate_frame_prompts() 使用
        """
        return {
            cid: self.get_prompt_fragment(cid)
            for cid in character_ids
            if cid in self.characters
        }

    def list_all(self) -> List[Dict]:
        """列出所有角色（用于 UI 展示）"""
        return [
            {"id": cid, **c.to_dict()}
            for cid, c in self.characters.items()
        ]
