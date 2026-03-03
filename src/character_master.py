"""
角色母版构建模块 (Character Master)
SOP 第二阶段：建立可复用角色资产，解决跨场景人物一致性问题

核心原则：
- 所有外貌描述必须使用【结构性语言】，禁止模糊词（帅气、漂亮等）
- 每个角色生成三视图、全/半身比例图、3种以上代表性表情
- 固定光影基准，作为后续所有图片/视频生成的锚点参考
"""

import json
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional

# 模糊描述词黑名单（禁止出现在角色描述中）
VAGUE_TERMS_BLACKLIST = [
    "帅气", "漂亮", "美丽", "好看", "英俊", "可爱", "迷人", "性感",
    "handsome", "beautiful", "pretty", "cute", "lovely", "gorgeous",
    "attractive", "charming", "sexy",
]

# 三视图 prompt 模板
VIEW_PROMPT_TEMPLATES = {
    "front": (
        "character design reference sheet, front view, full body, "
        "standing pose, neutral expression, white background, "
        "{anchor}, precise anatomy proportions, studio lighting"
    ),
    "side": (
        "character design reference sheet, side profile view, full body, "
        "standing pose, white background, "
        "{anchor}, precise anatomy proportions, studio lighting"
    ),
    "back": (
        "character design reference sheet, back view, full body, "
        "standing pose, white background, "
        "{anchor}, precise anatomy proportions, studio lighting"
    ),
    "half_body": (
        "character design reference sheet, half body portrait, front view, "
        "upper body visible, white background, "
        "{anchor}, studio lighting, clear face details"
    ),
    "full_body_proportion": (
        "character design reference sheet, full body proportion diagram, "
        "side by side front and back, height markers, "
        "{anchor}, white background, model sheet style"
    ),
}

# 表情 prompt 模板
EXPRESSION_PROMPT_TEMPLATES = {
    "neutral": (
        "character portrait, neutral expression, slight relaxed mouth, "
        "eyes looking forward, calm demeanor, "
        "{anchor}, {lighting_anchor}, close-up face, white background"
    ),
    "happy": (
        "character portrait, genuine happy smile, eyes slightly narrowed with joy, "
        "teeth not visible, warm upward-curved lips, "
        "{anchor}, {lighting_anchor}, close-up face, white background"
    ),
    "sad": (
        "character portrait, sad expression, slightly downturned eyebrows, "
        "lower lip slightly trembling, glistening eyes, restrained emotion, "
        "{anchor}, {lighting_anchor}, close-up face, white background"
    ),
    "determined": (
        "character portrait, determined resolute expression, "
        "tight jaw, direct steady gaze, eyebrows slightly furrowed, "
        "{anchor}, {lighting_anchor}, close-up face, white background"
    ),
    "surprised": (
        "character portrait, surprised expression, "
        "slightly widened eyes, parted lips, raised inner brows, "
        "{anchor}, {lighting_anchor}, close-up face, white background"
    ),
    "angry": (
        "character portrait, intense angry expression, "
        "furrowed brows, sharp piercing gaze, clenched jaw, "
        "{anchor}, {lighting_anchor}, close-up face, white background"
    ),
}


@dataclass
class CharacterMaster:
    """
    角色母版数据结构
    所有字段必须使用结构化的、可测量的描述语言
    """
    # ─── 基础标识 ──────────────────────────────────────────────────
    character_id: str                       # 唯一ID，贯穿全流程
    name: str                               # 角色中文名

    # ─── 外貌锚点（必须结构化，禁止模糊词）──────────────────────
    gender: str                             # male / female / non-binary
    age_range: str                          # 如 "early 20s" / "mid 30s"
    hair_color: str                         # 如 "jet black" / "platinum blonde"
    hair_style: str                         # 如 "waist-length straight" / "short layered bob"
    face_structure: str                     # 如 "oval face, high cheekbones, defined chin"
    skin_tone: str                          # 如 "fair porcelain skin, warm undertone"
    eye_description: str                    # 如 "large almond-shaped dark brown eyes"
    nose_description: str = ""              # 如 "straight nose, refined tip"
    lip_description: str = ""              # 如 "full lips, natural rose pink"
    height_proportion: str = ""            # 如 "tall 170cm, long legs, slim waist"
    body_type: str = ""                    # 如 "slender athletic build, narrow shoulders"

    # ─── 服装（主服装 + 细节）───────────────────────────────────
    outfit_primary: str = ""               # 主服装，如 "white chiffon A-line midi dress"
    outfit_collar: str = ""                # 领口类型，如 "V-neck, 3cm depth"
    outfit_sleeve: str = ""                # 袖型，如 "puff short sleeve, ruffled hem"
    outfit_texture: str = ""               # 面料细节，如 "semi-transparent chiffon with floral embroidery"
    outfit_accessories: List[str] = field(default_factory=list)  # 配饰

    # ─── 光影基准（固定不变）────────────────────────────────────
    lighting_anchor: str = (
        "soft left-side key light, 5600K daylight color temperature, "
        "low contrast ratio 2:1, subtle fill light from right"
    )

    # ─── 角色背景（供剧本/提示词参考）──────────────────────────
    personality: str = ""
    role_in_story: str = ""                # protagonist / antagonist / supporting
    extra_tags: List[str] = field(default_factory=list)

    # ─── 多视图 & 表情存储（图片路径，生成后填入）─────────────
    reference_images: Dict[str, str] = field(default_factory=dict)
    # key 示例: "front", "side", "back", "half_body", "expression_happy"

    def to_anchor_fragment(self) -> str:
        """
        输出固定的角色外貌锚点文本。
        所有后续 keyframe prompt 都必须 prepend 这段文本。
        """
        parts = [
            f"{self.age_range} {self.gender}",
            self.hair_color, self.hair_style, "hair",
            self.face_structure,
            self.skin_tone,
            self.eye_description,
        ]
        if self.nose_description:
            parts.append(self.nose_description)
        if self.lip_description:
            parts.append(self.lip_description)
        if self.height_proportion:
            parts.append(self.height_proportion)
        if self.body_type:
            parts.append(self.body_type)
        if self.outfit_primary:
            outfit_parts = [self.outfit_primary]
            if self.outfit_collar:
                outfit_parts.append(self.outfit_collar)
            if self.outfit_sleeve:
                outfit_parts.append(self.outfit_sleeve)
            if self.outfit_texture:
                outfit_parts.append(self.outfit_texture)
            parts.append("wearing " + ", ".join(outfit_parts))
        if self.outfit_accessories:
            parts.append("accessories: " + ", ".join(self.outfit_accessories))
        if self.extra_tags:
            parts.extend(self.extra_tags)
        return ", ".join(p.strip() for p in parts if p.strip())

    def build_view_prompts(self) -> Dict[str, str]:
        """生成三视图 + 全/半身比例图的完整 prompts"""
        anchor = self.to_anchor_fragment()
        return {
            view_key: template.format(anchor=anchor)
            for view_key, template in VIEW_PROMPT_TEMPLATES.items()
        }

    def build_expression_prompts(self) -> Dict[str, str]:
        """生成 6 种代表性表情的完整 prompts"""
        anchor = self.to_anchor_fragment()
        return {
            expr_key: template.format(
                anchor=anchor,
                lighting_anchor=self.lighting_anchor
            )
            for expr_key, template in EXPRESSION_PROMPT_TEMPLATES.items()
        }

    def build_outfit_detail_prompt(self) -> str:
        """生成服装结构细节图 prompt"""
        anchor = self.to_anchor_fragment()
        outfit_detail = ", ".join(filter(None, [
            self.outfit_primary,
            self.outfit_collar,
            self.outfit_sleeve,
            self.outfit_texture,
        ]))
        return (
            f"clothing design detail sheet, {outfit_detail}, "
            f"character wearing this outfit: {anchor}, "
            f"flat layout + worn view side by side, "
            f"fabric texture details, stitching visible, white background"
        )

    def validate(self) -> List[str]:
        """
        校验角色母版是否符合 SOP 规范。
        返回问题列表；空列表表示通过。
        """
        issues = []
        anchor = self.to_anchor_fragment()

        # 检测模糊词
        for term in VAGUE_TERMS_BLACKLIST:
            if term.lower() in anchor.lower():
                issues.append(f"锚点包含模糊词: '{term}'，请使用结构化描述")

        # 检查必填字段完整性
        required_fields = {
            "hair_color": self.hair_color,
            "hair_style": self.hair_style,
            "face_structure": self.face_structure,
            "skin_tone": self.skin_tone,
            "eye_description": self.eye_description,
            "outfit_primary": self.outfit_primary,
            "lighting_anchor": self.lighting_anchor,
        }
        for field_name, value in required_fields.items():
            if not value or not value.strip():
                issues.append(f"必填字段 '{field_name}' 为空")

        return issues

    def to_dict(self) -> dict:
        return asdict(self)

    def save_to_json(self, path: str) -> None:
        """持久化存储角色母版到 JSON（供后续项目复用）"""
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)
        print(f"[CharacterMaster] 角色母版已保存: {path}")

    @classmethod
    def load_from_json(cls, path: str) -> "CharacterMaster":
        """从 JSON 反序列化角色母版"""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls(**data)

    @classmethod
    def example(cls) -> "CharacterMaster":
        """
        返回内置示例角色（女主·林诗雨），用于开发测试。
        严格遵循 SOP 结构化描述规范。
        """
        return cls(
            character_id="char_001",
            name="林诗雨",
            gender="female",
            age_range="early 20s",
            hair_color="jet black",
            hair_style="waist-length straight with subtle inner curl at ends",
            face_structure="oval face, high soft cheekbones, gentle tapered chin, 1.6 facial height-to-width ratio",
            skin_tone="fair porcelain skin, neutral-cool undertone, subtle translucency",
            eye_description="large almond-shaped dark brown eyes, 12mm visible iris, single inner eyelid fold, expressive brow arch",
            nose_description="straight delicate nose, 40mm bridge length, refined rounded tip",
            lip_description="naturally shaped lips, 48mm width, soft rose-beige color, slight cupid's bow",
            height_proportion="approx 168cm, long leg-to-torso ratio 0.55, slender frame",
            body_type="slender build, 56kg, narrow 35cm shoulders, defined collarbone",
            outfit_primary="white chiffon A-line midi dress, hem at mid-calf",
            outfit_collar="V-neck, 8cm depth, narrow 3cm lapel trim",
            outfit_sleeve="cap sleeve, slight puff at shoulder seam",
            outfit_texture="semi-transparent chiffon with delicate white floral embroidery along hem",
            outfit_accessories=["thin gold chain bracelet on left wrist", "small pearl stud earrings"],
            lighting_anchor=(
                "soft left-side key light at 45 degrees, 5600K daylight color temperature, "
                "low contrast ratio 2:1, soft fill light from right, slight rim light on hair"
            ),
            personality="温柔坚韧，外柔内刚，善于倾听",
            role_in_story="protagonist",
            extra_tags=["consistent character", "detailed face", "IP-Adapter anchor"],
        )


class CharacterMasterRegistry:
    """
    角色母版注册表
    管理一部剧中所有角色母版，支持按 ID 查询
    """

    def __init__(self, registry_dir: str = "data/character_masters"):
        self.registry_dir = Path(registry_dir)
        self.registry_dir.mkdir(parents=True, exist_ok=True)
        self._cache: Dict[str, CharacterMaster] = {}

    def register(self, master: CharacterMaster) -> None:
        """注册并持久化角色母版"""
        issues = master.validate()
        if issues:
            raise ValueError(
                f"角色母版 '{master.name}' 未通过 SOP 校验:\n"
                + "\n".join(f"  - {i}" for i in issues)
            )
        path = self.registry_dir / f"{master.character_id}.json"
        master.save_to_json(str(path))
        self._cache[master.character_id] = master
        print(f"[CharacterMasterRegistry] 注册角色: {master.name} ({master.character_id})")

    def get(self, character_id: str) -> Optional[CharacterMaster]:
        """按 ID 获取角色母版（优先从缓存，否则从磁盘）"""
        if character_id in self._cache:
            return self._cache[character_id]
        path = self.registry_dir / f"{character_id}.json"
        if path.exists():
            master = CharacterMaster.load_from_json(str(path))
            self._cache[character_id] = master
            return master
        return None

    def get_by_name(self, name: str) -> Optional[CharacterMaster]:
        """按名字模糊搜索角色母版"""
        # 先搜缓存
        for master in self._cache.values():
            if master.name == name:
                return master
        # 再搜磁盘
        for json_file in self.registry_dir.glob("*.json"):
            try:
                master = CharacterMaster.load_from_json(str(json_file))
                if master.name == name:
                    self._cache[master.character_id] = master
                    return master
            except Exception:
                continue
        return None

    def list_all(self) -> List[CharacterMaster]:
        """列出所有已注册角色"""
        masters = []
        for json_file in self.registry_dir.glob("*.json"):
            try:
                master = CharacterMaster.load_from_json(str(json_file))
                masters.append(master)
                self._cache[master.character_id] = master
            except Exception:
                continue
        return masters

    def get_anchors_map(self) -> Dict[str, str]:
        """返回 {character_id: anchor_fragment} 映射，供批量 prompt 构建使用"""
        return {
            cid: master.to_anchor_fragment()
            for cid, master in self._cache.items()
        }
