"""Prompt Refiner 模块 - 将简单描述扩写为详细分镜描述
参考 Open-Sora Plan 的 Prompt Refiner 设计思路
"""
import json
import asyncio
from typing import Dict, Optional, List
from dataclasses import dataclass
from enum import Enum

class SceneType(Enum):
    """场景类型"""
    INDOOR = "室内"
    OUTDOOR = "室外"
    FANTASY = "奇幻"
    SCIFI = "科幻"

class LightingType(Enum):
    """光线类型"""
    NATURAL = "自然光"
    SOFT = "柔和光"
    DRAMATIC = "戏剧光"
    NEON = "霓虹光"

class CameraAngle(Enum):
    """镜头角度"""
    WIDE = "全景"
    MEDIUM = "中景"
    CLOSE = "近景"
    EXTREME_CLOSE = "特写"
    POV = "主观视角"

@dataclass
class RefinedPrompt:
    """精炼后的提示词"""
    scene: str           # 场景环境
    lighting: str        # 光线氛围
    character_appearance: str  # 角色外貌
    action: str         # 角色动作
    camera_angle: str   # 镜头语言
    emotion: str        # 情感基调
    full_prompt: str    # 完整提示词

class PromptRefiner:
    """Prompt 精炼器
    
    将用户输入的简单描述自动扩写为详细的视频生成提示词
    包含：场景、光线、角色、动作、镜头等维度
    """
    
    def __init__(self, api_config: dict = None):
        self.api_config = api_config or {}
        self.model = self.api_config.get("model", "opus")
    
    def _build_refinement_prompt(self, simple_description: str) -> str:
        """构建精炼提示词"""
        template = f"""你是一个专业的视频分镜提示词专家。请将以下简单的剧情描述扩写为详细的AI视频生成提示词。

要求：
1. 场景：详细描述环境（室内/室外、具体场所）
2. 光线：描述光照氛围（自然光、柔光、戏剧光等）
3. 角色：描述外貌特征、衣着打扮
4. 动作：描述角色正在做什么
5. 镜头：描述摄影机角度和运动
6. 情感：描述画面传递的情感

原始描述：{simple_description}

请以JSON格式输出，包含字段：
- scene: 场景描述
- lighting: 光线描述  
- character_appearance: 角色外貌
- action: 动作描述
- camera_angle: 镜头角度
- emotion: 情感基调
- full_prompt: 完整的英文提示词（用于AI视频生成）

只输出JSON，不要其他内容。"""
        return template
    
    async def refine(self, simple_description: str) -> RefinedPrompt:
        """异步精炼提示词
        
        Args:
            simple_description: 用户的简单描述
            
        Returns:
            RefinedPrompt: 精炼后的提示词对象
        """
        # TODO: 调用 LLM API 进行精炼
        # 目前返回基于规则的默认精炼结果
        
        return self._rule_based_refine(simple_description)
    
    def _rule_based_refine(self, description: str) -> RefinedPrompt:
        """基于规则的简单精炼（无API时的后备方案）"""
        description = description.lower()
        
        # 场景推断
        scene = "室内场景"
        if any(kw in description for kw in ["外面", "街头", "公园", "海边", "山"]):
            scene = "室外场景"
        if any(kw in description for kw in ["城堡", "魔法", "仙侠"]):
            scene = "奇幻场景"
        
        # 光线推断
        lighting = "柔和的自然光"
        if any(kw in description for kw in ["夜晚", "黑暗", "恐怖"]):
            lighting = "暗淡的冷色调光"
        if any(kw in description for kw in ["浪漫", "甜蜜"]):
            lighting = "温暖的柔光"
        
        # 镜头推断
        camera_angle = "中景"
        if any(kw in description for kw in ["特写", "脸", "眼睛"]):
            camera_angle = "面部特写"
        if any(kw in description for kw in ["全身", "站立", "走"]):
            camera_angle = "全身中景"
        
        # 情感推断
        emotion = "中性"
        if any(kw in description for kw in ["开心", "笑", "甜蜜", "浪漫"]):
            emotion = "愉悦"
        if any(kw in description for kw in ["悲伤", "哭", "难过"]):
            emotion = "悲伤"
        if any(kw in description for kw in ["紧张", "害怕", "恐怖"]):
            emotion = "紧张"
        
        full_prompt = f"{scene}, {lighting}, {description}, {camera_angle}, {emotion} mood, high quality, 8k, cinematic"
        
        return RefinedPrompt(
            scene=scene,
            lighting=lighting,
            character_appearance="角色特征待定",
            action=description,
            camera_angle=camera_angle,
            emotion=emotion,
            full_prompt=full_prompt
        )
    
    def refine_sync(self, simple_description: str) -> RefinedPrompt:
        """同步精炼版本"""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 在异步环境中，返回后备结果
                return self._rule_based_refine(simple_description)
            return asyncio.run(self.refine(simple_description))
        except RuntimeError:
            return asyncio.run(self.refine(simple_description))
    
    async def refine_batch(self, descriptions: List[str]) -> List[RefinedPrompt]:
        """批量精炼提示词"""
        tasks = [self.refine(desc) for desc in descriptions]
        return await asyncio.gather(*tasks)
    
    def refine_scene_prompts(self, script: str) -> List[str]:
        """从剧本提取场景并精炼提示词
        
        Args:
            script: 剧本文本
            
        Returns:
            List[str]: 精炼后的提示词列表
        """
        # 简单按行分割，实际应该用更智能的分镜提取
        scenes = []
        for line in script.split('\n'):
            line = line.strip()
            if line and not line.startswith('#') and len(line) > 5:
                scenes.append(line)
        
        if not scenes:
            scenes = ["场景描述"]
        
        # 精炼每个场景
        refined = []
        for scene in scenes:
            result = self._rule_based_refine(scene)
            refined.append(result.full_prompt)
        
        return refined


# 测试
if __name__ == "__main__":
    refiner = PromptRefiner()
    
    # 测试单个精炼
    print("🔍 测试提示词精炼:\n")
    
    test_cases = [
        "两人在咖啡馆相遇",
        "夜晚街头追逐",
        "城堡中的舞会",
        "病房里的诀别"
    ]
    
    for desc in test_cases:
        result = refiner.refine_sync(desc)
        print(f"📝 原始: {desc}")
        print(f"   场景: {result.scene}")
        print(f"   光线: {result.lighting}")
        print(f"   镜头: {result.camera_angle}")
        print(f"   情感: {result.emotion}")
        print(f"   完整: {result.full_prompt}")
        print()
