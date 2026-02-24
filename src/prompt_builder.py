"""
提示词生成器
为AI图像生成工具创建提示词
"""

import re
from typing import List, Dict
from dataclasses import dataclass


@dataclass
class ScenePrompt:
    """场景提示词"""
    scene_num: int
    description: str
    character_prompt: str
    environment_prompt: str
    mood_prompt: str
    full_prompt: str


class PromptBuilder:
    """AI图像提示词生成器"""
    
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
    
    def __init__(self, config):
        self.config = config
        self.style = config.style
    
    def generate_scene_prompts(self, script: str) -> List[str]:
        """从剧本生成场景提示词"""
        scenes = self._parse_scenes(script)
        prompts = []
        
        for scene in scenes:
            prompt = self._build_prompt(scene)
            prompts.append(prompt)
        
        return prompts
    
    def _parse_scenes(self, script: str) -> List[Dict]:
        """解析剧本中的场景"""
        scenes = []
        
        # 按场景分割
        scene_blocks = re.split(r'场景\d+:', script)
        
        for i, block in enumerate(scene_blocks[1:], 1):
            lines = block.strip().split('\n')
            
            description = ""
            dialogue = ""
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                if '[' in line and ']' in line:
                    # 场景描述
                    description += line + " "
                elif ':' in line and not line.startswith('#'):
                    # 对话
                    dialogue += line + " "
            
            scenes.append({
                "scene_num": i,
                "description": description.strip(),
                "dialogue": dialogue.strip()
            })
        
        return scenes
    
    def _build_prompt(self, scene: Dict) -> str:
        """构建完整的提示词"""
        parts = []
        
        # 基础描述
        desc = scene.get("description", "")
        if desc:
            parts.append(desc)
        
        # 角色提示
        if scene.get("dialogue"):
            parts.append(self._extract_character_hint(scene["dialogue"]))
        
        # 风格
        parts.append(self._get_style_prompt())
        
        # 情绪
        parts.append(self._get_mood_prompt())
        
        # 技术参数
        parts.append("high quality, 8k, detailed, masterpiece")
        
        return ", ".join(parts)
    
    def _extract_character_hint(self, dialogue: str) -> str:
        """从对话中提取角色提示"""
        # 简化处理
        hints = []
        
        if any(word in dialogue for word in ["男主", "男生", "男人", "他"]):
            hints.append("handsome male character")
        if any(word in dialogue for word in ["女主", "女生", "女人", "她"]):
            hints.append("beautiful female character")
        if any(word in dialogue for word in ["妈妈", "母亲", "爸", "父亲"]):
            hints.append("middle-aged character")
        if any(word in dialogue for word in ["老师", "医生", "警察"]):
            hints.append("professional attire")
            
        return ", ".join(hints) if hints else "character"
    
    def _get_style_prompt(self) -> str:
        """获取风格提示"""
        style_map = {
            "情感": "cinematic, romantic, soft lighting, emotional",
            "悬疑": "dark, mysterious, suspenseful, thriller",
            "搞笑": "comedy, funny, bright, humorous",
            "科幻": "sci-fi, futuristic, technology, neon lights",
        }
        return style_map.get(self.style, "cinematic, high quality")
    
    def _get_mood_prompt(self) -> str:
        """获取情绪提示"""
        return "expressive, detailed face, professional photography"


class PromptOptimizer:
    """提示词优化器 - 针对不同平台优化"""
    
    # Midjourney 提示词模板
    MIDJOURNEY_TEMPLATE = """
    {subject}, {environment}, {style}, {lighting}, {mood}, 
    --ar 9:16 --v 6 --style expressive
    """
    
    # Stable Diffusion 提示词模板
    STABLE_DIFFUSION_TEMPLATE = """
    {subject}, {environment}, {style}, {lighting}, {mood}
    """
    
    # DALL-E 提示词模板
    DALLE_TEMPLATE = """
    {subject}, {environment}, {style}, cinematic shot, high quality
    """
    
    @staticmethod
    def for_midjourney(prompt: str) -> str:
        """优化为 Midjourney 格式"""
        return f"{prompt}, --ar 9:16 --v 6 --style expressive"
    
    @staticmethod
    def for_stable_diffusion(prompt: str) -> str:
        """优化为 Stable Diffusion 格式"""
        return prompt
    
    @staticmethod
    def for_dalle(prompt: str) -> str:
        """优化为 DALL-E 格式"""
        return f"{prompt}, cinematic shot, high quality"
    
    @staticmethod
    def for_kling(prompt: str) -> str:
        """优化为可灵 AI 格式"""
        return f"{prompt}, high quality, cinematic"
