#!/usr/bin/env python3
"""
测试高效生产流程

演示新流程:
1. 生成3个剧本 → AI自动评分 → 只保留最高分
2. 生成角色母版 → 人工确认一次
3. 生成分镜 → 生成视频
4. AI自动检测质量 → 输出3个最终版本
5. 人工选1个发布
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.efficient_pipeline import EfficientPipeline


# 模拟剧本生成器
class MockScriptGenerator:
    def generate_script(self, topic: str, style: str, episode_num: int) -> str:
        scripts = [
            # 剧本1 - 中等质量
            """第1集：重生归来

场景1: [清晨·卧室]
女主: 这是...十年前？
旁白: 当她再次睁开眼，时间回到了那个早晨。

场景2: [客厅]
妈妈: 起来了？快来吃早餐。
女主: 妈妈...(泪流满面)

场景3: [学校]
同学: 听说今天有新同学转来...
男主: 大家好，我是...
女主: 是他！

场景4: [结尾]
女主: 这一世我一定要改变命运！
字幕: 敬请期待下一集""",

            # 剧本2 - 高质量
            """第1集：重生复仇

场景1: [深夜·卧室]
女主: （震惊）这是...十年前？我重生了？！
旁白: 当她再次睁开眼，时间回到了那个改变命运的早晨...

场景2: [客厅·冲突]
妈妈: 起来了？快来吃早餐。
女主: （泪流满面）妈...妈妈...(上一世，妈妈已经死了...)
妈妈: （惊讶）怎么了？傻孩子。

场景3: [学校·反转]
同学: 听说今天有新同学转来...
男主: （出场）大家好，我是陆沉。
女主: （内心）是他！就是这个人，上一世害我家破人亡！

场景4: [结尾·钩子]
女主: （愤怒）既然重生了，这一世我一定要保护好家人，让他付出代价！
旁白: 复仇，从今天开始...
字幕: 敬请期待下一集""",

            # 剧本3 - 低质量
            """第1集：开始

场景1: [早上]
女主: 醒了。

场景2: [家里]
妈妈: 吃饭。
女主: 好。

场景3: [学校]
男主: 你好。
女主: 你好。

场景4: [结束]
女主: 明天见。"""
        ]

        # 循环返回不同剧本
        import random
        return random.choice(scripts)


# 模拟角色生成器
class MockCharacterGenerator:
    def generate_characters(self, script: str) -> list:
        return [
            {
                "name": "女主 - 苏念",
                "description": "25岁，职场精英，坚毅果敢，重生后决心改变命运",
                "image_path": "output/characters/female_lead.png"
            },
            {
                "name": "男主 - 陆沉",
                "description": "28岁，商业巨头，外表冷酷内心温柔，上一世的关键人物",
                "image_path": "output/characters/male_lead.png"
            },
            {
                "name": "女配 - 林婉儿",
                "description": "24岁，女主闺蜜，善良单纯，关键时刻的助力",
                "image_path": "output/characters/female_support.png"
            }
        ]


# 模拟分镜管理器
class MockStoryboardManager:
    def create_storyboard(self, script: str, characters: list) -> dict:
        return {
            "shots": [
                {"shot_id": "s1_shot1", "description": "女主醒来"},
                {"shot_id": "s1_shot2", "description": "女主震惊"},
                {"shot_id": "s1_shot3", "description": "女主和妈妈对话"},
                {"shot_id": "s1_shot4", "description": "男主出场"},
                {"shot_id": "s1_shot5", "description": "女主内心独白"}
            ]
        }


def main():
    print("="*60)
    print("高效生产流程测试")
    print("="*60)

    # 创建流程管理器
    pipeline = EfficientPipeline()

    # 开始会话
    topic = "重生复仇"
    pipeline.start_session(topic)

    # 创建模拟生成器
    script_gen = MockScriptGenerator()
    char_gen = MockCharacterGenerator()
    storyboard_mgr = MockStoryboardManager()

    try:
        # ============================================================
        # 阶段1: 生成3个剧本 → AI自动评分 → 选最高分
        # ============================================================
        selected_script = pipeline.generate_and_select_script(
            script_generator=script_gen,
            topic=topic,
            style="情感"
        )

        print(f"\n选中剧本预览:")
        print(selected_script["content"][:200] + "...")

        # ============================================================
        # 阶段2: 生成角色母版 → 人工确认
        # ============================================================
        characters = pipeline.generate_characters(
            character_generator=char_gen,
            script=selected_script["content"]
        )

        # 请求人工确认
        approved = pipeline.request_character_approval(characters)

        if not approved:
            print("\n✗ 角色母版未通过，流程终止")
            return

        # ============================================================
        # 阶段3: 生成分镜 → 生成视频
        # ============================================================
        video_clips = pipeline.generate_storyboard_and_videos(
            storyboard_manager=storyboard_mgr,
            script=selected_script["content"],
            characters=characters
        )

        # ============================================================
        # 阶段4: AI质量检测 → 输出3个最终版本
        # ============================================================
        final_versions = pipeline.generate_final_versions(video_clips)

        # ============================================================
        # 阶段5: 人工选1个发布
        # ============================================================
        published = pipeline.request_final_selection(final_versions)

        if published:
            print(f"\n✓ 发布版本: {published.version_id}")
            print(f"  视频路径: {published.video_path}")
            print(f"  质量分: {published.quality_score:.1f}/10")
            print(f"  选择理由: {published.selection_reason}")

        # 保存会话
        pipeline.save_session()

        # 显示摘要
        print(pipeline.get_session_summary())

    except KeyboardInterrupt:
        print("\n\n用户中断")
        pipeline.save_session()
    except Exception as e:
        print(f"\n\n错误: {e}")
        import traceback
        traceback.print_exc()
        pipeline.save_session()


if __name__ == "__main__":
    main()
