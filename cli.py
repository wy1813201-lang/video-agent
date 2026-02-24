#!/usr/bin/env python3
"""
视频生成工作流 CLI
支持实时监控和用户干预
"""

import asyncio
import json
import os
import sys
from datetime import datetime

# 添加 src 到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from workflow_manager import WorkflowManager, Stage
from feishu_notifier import FeishuNotifier
from src.script_generator import ScriptGenerator

# 飞书配置
FEISHU_USER_ID = "ou_f6704c00c53276b4ac879bc66056981a"

class InteractiveWorkflow:
    """交互式工作流"""
    
    def __init__(self):
        self.manager = WorkflowManager(notify_callback=self.on_update)
        self.notifier = FeishuNotifier(user_id=FEISHU_USER_ID)
        self.script_gen = None
        self.config = None
    
    def on_update(self, message: str):
        """收到进度更新"""
        print(f"\n{'='*50}")
        print(message)
        print('='*50)
        
        # 发送到飞书
        try:
            self.notifier.send_text(message, FEISHU_USER_ID)
        except Exception as e:
            print(f"飞书通知失败: {e}")
    
    async def start(self, topic: str = "重生千金复仇记"):
        """开始工作流"""
        
        print(f"\n🚀 启动视频生成工作流")
        print(f"📺 主题: {topic}")
        
        # 加载配置
        config_path = os.path.join(os.path.dirname(__file__), "config", "api_keys.json")
        api_config = {}
        if os.path.exists(config_path):
            with open(config_path) as f:
                api_config = json.load(f)
        
        # 创建剧本生成器
        self.config = type('Config', (), {
            'topic': topic,
            'style': '情感',
            'episodes': 3,
            'duration_per_episode': 60,
            'openai_api_key': None,
            'anthropic_api_key': api_config.get('script', {}).get('custom_opus', {}).get('api_key')
        })()
        
        self.script_gen = ScriptGenerator(self.config, api_config)
        
        # ========== 阶段 1: 剧本 ==========
        await self.manager.update_progress(
            Stage.SCRIPT, 0.05,
            "正在生成剧本...",
            "第1集", 3, 0
        )
        
        print("\n📝 生成剧本中...")
        episodes = []
        for i in range(1, 4):
            script = await self.script_gen.generate_episode(topic, i, 3)
            episodes.append(script)
            await self.manager.update_progress(
                Stage.SCRIPT, 0.05 + i*0.03,
                f"第{i}集已完成",
                f"第{i}集", 3, i
            )
        
        self.manager.state.script = "\n\n---\n\n".join(episodes)
        self.manager.state.needs_approval = True
        
        await self.manager.update_progress(
            Stage.SCRIPT, 0.15,
            "✅ 剧本生成完成，等待审批",
            "3集已完成", 3, 3
        )
        
        # 打印剧本供确认
        print("\n" + "="*50)
        print("生成的剧本:")
        print("="*50)
        for i, ep in enumerate(episodes, 1):
            print(f"\n--- 第{i}集 ---")
            print(ep[:500] + "..." if len(ep) > 500 else ep)
        
        # 等待用户输入
        print("\n" + "="*50)
        print("请确认剧本: ")
        print("  [y] 批准继续")
        print("  [n] 重新生成")
        print("  [q] 退出")
        print("="*50)
        
        # 发送飞书消息等待确认
        self.notifier.send_text(
            f"📝 **剧本已生成**\n\n"
            f"主题: {topic}\n"
            f"集数: 3集\n\n"
            f"请回复:\n"
            f"  - `y` 批准继续\n"
            f"  - `n` 重新生成\n"
            f"  - `q` 退出",
            FEISHU_USER_ID
        )
        
        # 这里暂停等待用户输入
        user_input = input("\n输入指令 [y/n/q]: ").strip().lower()
        
        if user_input == 'q':
            print("❌ 已退出")
            return
        elif user_input == 'n':
            print("🔄 重新生成...")
            self.manager.state.needs_approval = True
            await self.start(topic)
            return
        
        # 批准继续
        self.manager.approve()
        
        # ========== 阶段 2: 提示词 ==========
        await self.manager.update_progress(
            Stage.IMAGE_PROMPTS, 0.2,
            "正在生成图像提示词...",
            "处理中", 12, 0
        )
        
        # 生成提示词
        prompts = []
        for i, ep in enumerate(episodes, 1):
            # 简单提取场景
            scenes = ep.split("场景")
            for j, scene in enumerate(scenes[1:], 1):
                prompt = f"cinematic scene, {scene[:100]}, high quality, 8k, detailed"
                prompts.append(prompt)
                await self.manager.update_progress(
                    Stage.IMAGE_PROMPTS, 0.2 + len(prompts)/12 * 0.1,
                    f"已生成 {len(prompts)} 个提示词",
                    f"场景{len(prompts)}", 12, len(prompts)
                )
        
        self.manager.state.prompts = prompts
        
        # 打印提示词
        print("\n" + "="*50)
        print("生成的图像提示词:")
        print("="*50)
        for i, p in enumerate(prompts[:6], 1):
            print(f"{i}. {p[:80]}...")
        
        await self.manager.update_progress(
            Stage.IMAGE_PROMPTS, 0.3,
            "✅ 提示词生成完成",
            f"{len(prompts)}个场景", 12, 12
        )
        
        print("\n⚠️  后续阶段需要视频生成 API")
        print("当前支持的 API:")
        print("  - 可灵 AI (app.klingai.com)")
        print("  - 即梦 AI (jimeng.jianying.com)")
        
        self.notifier.send_text(
            "📊 **工作流暂停**\n\n"
            "✅ 剧本生成完成\n"
            "✅ 图像提示词生成完成\n\n"
            "⏸️ 等待视频生成 API...\n"
            "获取后可灵/即梦 API 后可继续",
            FEISHU_USER_ID
        )
        
        return self.manager.state


async def main():
    workflow = InteractiveWorkflow()
    
    topic = "重生千金复仇记"
    if len(sys.argv) > 1:
        topic = sys.argv[1]
    
    await workflow.start(topic)


if __name__ == "__main__":
    asyncio.run(main())
