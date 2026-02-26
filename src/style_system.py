"""
全局风格系统
定义短剧风格模板，自动应用到图像/视频生成
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class StyleConfig:
    name: str
    name_en: str
    color_tone: str          # 色调描述
    scene_keywords: List[str]
    costume_keywords: List[str]
    lighting: str
    mood: str
    negative_prompt: str = ""
    aspect_ratio: str = "9:16"


# ── 内置风格模板 ──────────────────────────────────────────────────────────────

STYLE_TEMPLATES: Dict[str, StyleConfig] = {
    "古装": StyleConfig(
        name="古装",
        name_en="ancient_chinese",
        color_tone="warm golden tones, ink wash painting palette, muted earth tones",
        scene_keywords=[
            "ancient Chinese architecture", "palace courtyard", "bamboo forest",
            "traditional Chinese garden", "lantern-lit corridor", "misty mountains"
        ],
        costume_keywords=[
            "hanfu", "traditional Chinese robes", "jade accessories",
            "silk embroidery", "hair ornaments", "ancient Chinese attire"
        ],
        lighting="soft natural light, golden hour, candlelight, lantern glow",
        mood="epic, majestic, poetic, historical drama",
        negative_prompt="modern clothing, cars, phones, contemporary buildings",
    ),
    "现代": StyleConfig(
        name="现代",
        name_en="modern",
        color_tone="clean neutral tones, urban color palette, bright and crisp",
        scene_keywords=[
            "modern city", "office building", "luxury apartment", "coffee shop",
            "shopping mall", "rooftop terrace", "contemporary interior"
        ],
        costume_keywords=[
            "business casual", "designer clothing", "modern fashion",
            "suit", "casual wear", "trendy outfit"
        ],
        lighting="natural daylight, studio lighting, city lights at night",
        mood="contemporary, realistic, relatable, urban life",
        negative_prompt="ancient buildings, historical costumes",
    ),
    "科幻": StyleConfig(
        name="科幻",
        name_en="sci_fi",
        color_tone="cool blue and purple tones, neon accents, metallic sheen",
        scene_keywords=[
            "futuristic city", "space station", "holographic displays",
            "cyberpunk street", "laboratory", "alien landscape", "spacecraft interior"
        ],
        costume_keywords=[
            "futuristic suit", "tech armor", "holographic accessories",
            "cyberpunk outfit", "space suit", "advanced technology wearables"
        ],
        lighting="neon lights, bioluminescent glow, holographic blue light, dramatic rim lighting",
        mood="futuristic, technological, epic, mysterious",
        negative_prompt="ancient, historical, traditional clothing",
    ),
    "甜宠": StyleConfig(
        name="甜宠",
        name_en="sweet_romance",
        color_tone="pastel pink and warm tones, soft dreamy palette, rose gold",
        scene_keywords=[
            "flower garden", "cozy cafe", "sunset beach", "cherry blossom park",
            "romantic restaurant", "fairy light bedroom", "seaside"
        ],
        costume_keywords=[
            "cute casual wear", "floral dress", "soft knit sweater",
            "pastel colors", "romantic outfit", "sweet accessories"
        ],
        lighting="golden hour, soft bokeh, warm backlight, fairy lights",
        mood="sweet, romantic, heartwarming, dreamy, fluffy",
        negative_prompt="dark, gloomy, horror, violence",
    ),
    "虐恋": StyleConfig(
        name="虐恋",
        name_en="bittersweet_romance",
        color_tone="desaturated tones, cold blue-grey, occasional warm contrast",
        scene_keywords=[
            "rainy street", "empty hospital corridor", "dimly lit room",
            "foggy bridge", "abandoned building", "stormy sea"
        ],
        costume_keywords=[
            "formal wear", "dark clothing", "elegant but somber attire",
            "rain-soaked clothes", "hospital gown", "black dress"
        ],
        lighting="overcast sky, rain, dramatic shadows, single light source, cold moonlight",
        mood="melancholic, emotional, tragic, intense, heartbreaking",
        negative_prompt="bright cheerful colors, happy sunny scenes",
    ),
    "悬疑": StyleConfig(
        name="悬疑",
        name_en="thriller",
        color_tone="dark desaturated tones, high contrast, deep shadows",
        scene_keywords=[
            "dark alley", "abandoned warehouse", "foggy night street",
            "dimly lit office", "underground parking", "mysterious mansion"
        ],
        costume_keywords=[
            "trench coat", "dark formal wear", "detective outfit",
            "mysterious hooded figure", "business suit"
        ],
        lighting="low key lighting, harsh shadows, single spotlight, neon signs in fog",
        mood="suspenseful, mysterious, tense, dark, thrilling",
        negative_prompt="bright cheerful colors, happy scenes",
    ),
    "搞笑": StyleConfig(
        name="搞笑",
        name_en="comedy",
        color_tone="bright vivid colors, high saturation, warm tones",
        scene_keywords=[
            "busy street", "chaotic office", "family home", "school",
            "market", "park", "restaurant"
        ],
        costume_keywords=[
            "exaggerated outfit", "mismatched clothing", "funny costume",
            "casual everyday wear", "colorful accessories"
        ],
        lighting="bright natural light, even lighting, cheerful atmosphere",
        mood="funny, comedic, lighthearted, exaggerated, humorous",
        negative_prompt="dark, gloomy, horror, violence",
    ),
}


class StyleSystem:
    """全局风格系统 - 管理和应用风格到生成任务"""

    def __init__(self, default_style: str = "现代"):
        self.default_style = default_style
        self._active_style: Optional[str] = None

    def set_style(self, style_name: str):
        if style_name not in STYLE_TEMPLATES:
            available = list(STYLE_TEMPLATES.keys())
            raise ValueError(f"未知风格: {style_name}，可用风格: {available}")
        self._active_style = style_name

    def get_style(self, style_name: str = None) -> StyleConfig:
        name = style_name or self._active_style or self.default_style
        return STYLE_TEMPLATES.get(name, STYLE_TEMPLATES["现代"])

    def list_styles(self) -> List[str]:
        return list(STYLE_TEMPLATES.keys())

    def apply_to_image_prompt(self, base_prompt: str, style_name: str = None) -> str:
        """将风格应用到图像提示词"""
        style = self.get_style(style_name)
        scene = style.scene_keywords[0] if style.scene_keywords else ""
        costume = style.costume_keywords[0] if style.costume_keywords else ""
        parts = [
            base_prompt,
            scene,
            costume,
            style.color_tone,
            style.lighting,
            style.mood,
            f"aspect ratio {style.aspect_ratio}",
            "high quality, cinematic, 8k, masterpiece",
        ]
        return ", ".join(p for p in parts if p)

    def apply_to_video_prompt(self, base_prompt: str, style_name: str = None) -> str:
        """将风格应用到视频提示词"""
        style = self.get_style(style_name)
        parts = [
            base_prompt,
            style.color_tone,
            style.lighting,
            style.mood,
            "cinematic camera movement, smooth motion, high quality",
        ]
        return ", ".join(p for p in parts if p)

    def get_negative_prompt(self, style_name: str = None) -> str:
        style = self.get_style(style_name)
        base_negative = "blurry, low quality, distorted, watermark, text overlay"
        if style.negative_prompt:
            return f"{base_negative}, {style.negative_prompt}"
        return base_negative

    def get_style_summary(self, style_name: str = None) -> dict:
        style = self.get_style(style_name)
        return {
            "name": style.name,
            "color_tone": style.color_tone,
            "lighting": style.lighting,
            "mood": style.mood,
            "scenes": style.scene_keywords[:3],
            "costumes": style.costume_keywords[:3],
        }
