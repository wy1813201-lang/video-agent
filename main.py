#!/usr/bin/env python3
"""
AI Short Drama Automator
自动化生成AI短剧的框架
"""

import os
import json
import asyncio
from datetime import datetime
from typing import Optional, Dict, List
from dataclasses import dataclass, asdict

# 尝试导入可选依赖
try:
    from src.script_generator import ScriptGenerator
except ImportError:
    ScriptGenerator = None

try:
    from src.prompt_builder import PromptBuilder
except ImportError:
    PromptBuilder = None

try:
    from src.video_assembler import VideoAssembler
except ImportError:
    VideoAssembler = None


@dataclass
class DramaConfig:
    """短剧配置"""
    topic: str  # 主题
    style: str = "情感"  # 风格: 情感, 悬疑, 搞笑, 科幻
    episodes: int = 3  # 集数
    duration_per_episode: int = 60  # 每集秒数
    language: str = "zh"  # 语言
    
    # 输出设置
    output_dir: str = "output"
    resolution: str = "1080x1920"  # 竖屏
    
    # API 配置 (可选)
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    replicate_api_key: Optional[str] = None


@dataclass
class Episode:
    """单集内容"""
    episode_num: int
    title: str
    script: str
    image_prompts: List[str]
    video_path: Optional[str] = None


class ShortDramaAutomator:
    """AI短剧自动生成器"""
    
    def __init__(self, config: DramaConfig):
        self.config = config
        self.episodes: List[Episode] = []
        
        # 创建输出目录
        os.makedirs(config.output_dir, exist_ok=True)
        
        # 初始化各模块
        self.script_gen = None
        self.prompt_builder = None
        self.video_assembler = None
        
        # 加载 API 配置
        api_config = {}
        config_path = os.path.join(os.path.dirname(__file__), "config", "api_keys.json")
        if os.path.exists(config_path):
            with open(config_path) as f:
                api_config = json.load(f)
        
        if ScriptGenerator:
            self.script_gen = ScriptGenerator(config, api_config)
        if PromptBuilder:
            self.prompt_builder = PromptBuilder(config)
        if VideoAssembler:
            self.video_assembler = VideoAssembler(config)
    
    async def generate_drama(self) -> List[Episode]:
        """生成完整短剧"""
        print(f"🎬 开始生成短剧: {self.config.topic}")
        print(f"   风格: {self.config.style}, 集数: {self.config.episodes}")
        
        for i in range(1, self.config.episodes + 1):
            print(f"\n📝 生成第 {i} 集...")
            
            # 1. 生成剧本
            if self.script_gen:
                script = await self.script_gen.generate_episode(
                    topic=self.config.topic,
                    episode_num=i,
                    total_episodes=self.config.episodes
                )
            else:
                script = self._generate_placeholder_script(i)
            
            # 2. 生成图片提示词
            if self.prompt_builder:
                prompts = self.prompt_builder.generate_scene_prompts(script)
            else:
                prompts = self._generate_placeholder_prompts(script)
            
            episode = Episode(
                episode_num=i,
                title=f"第{i}集",
                script=script,
                image_prompts=prompts
            )
            self.episodes.append(episode)
            
            # 3. 生成视频 (需要外部工具)
            print(f"   ⚠️ 视频生成需要调用外部AI图像/视频API")
            print(f"   📝 提示词已生成: {len(prompts)} 个场景")
        
        print(f"\n✅ 短剧生成完成! 共 {len(self.episodes)} 集")
        return self.episodes
    
    def _generate_placeholder_script(self, episode_num: int) -> str:
        """生成占位剧本"""
        return f"""第{episode_num}集

场景1: [开场]
对话: 主人公醒来，发现自己在一个陌生的房间...

场景2: [发展]
对话: 这时，门突然打开了...

场景3: [结尾]
对话: 到底是谁？敬请期待下一集！
"""
    
    def _generate_placeholder_prompts(self, script: str) -> List[str]:
        """生成占位提示词"""
        scenes = script.split("场景")
        prompts = []
        for i, scene in enumerate(scenes[1:], 1):
            prompts.append(f"cinematic scene {i}, dramatic lighting, high quality, 8k")
        return prompts
    
    def save_results(self):
        """保存结果"""
        output_file = os.path.join(
            self.config.output_dir,
            f"drama_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        
        data = {
            "config": asdict(self.config),
            "episodes": [asdict(ep) for ep in self.episodes]
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print(f"💾 结果已保存到: {output_file}")
        return output_file


async def main():
    """测试运行"""
    # 加载 API 配置
    api_config = {}
    config_path = os.path.join(os.path.dirname(__file__), "config", "api_keys.json")
    anthropic_api_key = None
    
    if os.path.exists(config_path):
        with open(config_path) as f:
            api_config = json.load(f)
            custom_opus = api_config.get("script", {}).get("custom_opus", {})
            if custom_opus.get("enabled"):
                anthropic_api_key = custom_opus.get("api_key")
    
    config = DramaConfig(
        topic="重生千金复仇记",
        style="情感",
        episodes=3,
        output_dir="output",
        anthropic_api_key=anthropic_api_key
    )
    
    automator = ShortDramaAutomator(config)
    await automator.generate_drama()
    automator.save_results()


if __name__ == "__main__":
    asyncio.run(main())
