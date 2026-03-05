#!/usr/bin/env python3
"""
测试统一审查系统

演示人物母版、视频片段、最终视频的审查流程
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.unified_review_system import UnifiedReviewSystem

print("=" * 60)
print("统一审查系统测试")
print("=" * 60)

# 创建审查系统
review_system = UnifiedReviewSystem(port=5001)

# 模拟数据
print("\n准备测试数据...")

# 0. 剧本数据
test_script = """第1集：重生归来

场景1: [清晨·卧室]
女主: （震惊）这是...十年前？我重生了？
旁白: 当她再次睁开眼，时间回到了那个改变命运的早晨...

场景2: [客厅·冲突]
妈妈: 起来了？快来吃早餐。
女主: （泪流满面）妈...妈妈...(上一世，妈妈已经...)
妈妈: 怎么了？傻孩子。

场景3: [学校·反转]
同学: 听说今天有新同学转来...
男主: （出场）大家好，我是...
女主: （内心）是他！就是这个人，上一世害我家破人亡！

场景4: [结尾·钩子]
女主: （内心）既然重生了，这一世我一定要保护好家人，让他付出代价！
字幕: 敬请期待下一集
"""

script_score = {
    "overall": 7.5,
    "hook_strength": 8.0,
    "plot_structure": 7.5,
    "emotion_rhythm": 7.0
}

# 1. 人物母版数据
characters = [
    {
        "name": "女主 - 苏念",
        "image_path": "output/characters/female_lead.png",
        "description": "25岁，职场精英，坚毅果敢，重生后决心改变命运"
    },
    {
        "name": "男主 - 陆沉",
        "image_path": "output/characters/male_lead.png",
        "description": "28岁，商业巨头，外表冷酷内心温柔，上一世的关键人物"
    },
    {
        "name": "女配 - 林婉儿",
        "image_path": "output/characters/female_support.png",
        "description": "24岁，女主闺蜜，善良单纯，关键时刻的助力"
    }
]

# 2. 视频片段数据
videos = [
    {
        "shot_id": "s1_shot1",
        "video_path": "output/videos/s1_shot1.mp4",
        "thumbnail_path": "output/videos/s1_shot1_thumb.png",
        "status": "completed"
    },
    {
        "shot_id": "s1_shot2",
        "video_path": "output/videos/s1_shot2.mp4",
        "thumbnail_path": "output/videos/s1_shot2_thumb.png",
        "status": "completed"
    },
    {
        "shot_id": "s1_shot3",
        "video_path": "output/videos/s1_shot3.mp4",
        "thumbnail_path": "output/videos/s1_shot3_thumb.png",
        "status": "processing"
    }
]

# 3. 最终视频数据
final_video = "output/final/episode_01.mp4"
metadata = {
    "duration": "60秒",
    "resolution": "1080x1920",
    "file_size": "15.2 MB",
    "fps": "30 fps"
}

# 选择测试类型
print("\n请选择测试类型:")
print("1. 剧本审查")
print("2. 人物母版审查")
print("3. 视频片段审查")
print("4. 最终视频审查")
print("5. 完整内容审查（所有内容）")

choice = input("\n请输入选项 (1-5): ").strip()

if choice == "1":
    print("\n启动剧本审查...")
    result = review_system.review_script(test_script, script_score)
elif choice == "2":
    print("\n启动人物母版审查...")
    result = review_system.review_characters(characters)
elif choice == "3":
    print("\n启动视频片段审查...")
    result = review_system.review_video_progress(videos)
elif choice == "4":
    print("\n启动最终视频审查...")
    result = review_system.review_final_video(final_video, metadata)
elif choice == "5":
    print("\n启动完整内容审查...")
    result = review_system.review_all(test_script, script_score, characters, videos, final_video)
else:
    print("\n无效选项，默认启动完整内容审查...")
    result = review_system.review_all(test_script, script_score, characters, videos, final_video)

# 显示结果
print("\n" + "=" * 60)
print("审查结果")
print("=" * 60)
print(f"\n状态: {result['status']}")
if result.get('feedback'):
    print(f"反馈: {result['feedback']}")
print(f"时间: {result['timestamp']}")

print("\n" + "=" * 60)
print("测试完成！")
print("=" * 60)
