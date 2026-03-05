#!/usr/bin/env python3
"""
Meta Director 测试脚本

演示 Meta Director 的审核和实验功能
"""

import asyncio
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.meta_director import MetaDirector, DecisionType, ContentType
from src.experiment_engine import ExperimentEngine, ExperimentParamsGenerator
from src.human_selector import HumanSelector


def test_script_review():
    """测试剧本审核"""
    print("\n" + "=" * 60)
    print("测试 1: 剧本审核")
    print("=" * 60)

    director = MetaDirector({
        "min_score": 7.0,
        "enable_experiments": True,
        "experiment_count": 2
    })

    # 测试剧本1：高质量剧本
    good_script = """第1集：重生归来

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

    decision = director.review_script(good_script)
    print(f"\n剧本1 审核结果:")
    print(f"  决策: {decision.decision_type.value}")
    print(f"  总分: {decision.score.overall:.1f}/10")
    print(f"  Hook吸引力: {decision.score.hook_strength:.1f}/10")
    print(f"  剧情结构: {decision.score.plot_structure:.1f}/10")
    print(f"  情绪节奏: {decision.score.emotion_rhythm:.1f}/10")
    print(f"  理由: {decision.reason}")

    # 测试剧本2：低质量剧本
    bad_script = """第1集

场景1: 早上起床了
对话: 今天天气不错

场景2: 去上学
对话: 路上遇到了同学
"""

    decision2 = director.review_script(bad_script)
    print(f"\n剧本2 审核结果:")
    print(f"  决策: {decision2.decision_type.value}")
    print(f"  总分: {decision2.score.overall:.1f}/10")
    print(f"  理由: {decision2.reason}")


def test_storyboard_review():
    """测试分镜审核"""
    print("\n" + "=" * 60)
    print("测试 2: 分镜审核")
    print("=" * 60)

    director = MetaDirector({
        "min_score": 7.0,
        "enable_experiments": True
    })

    # 测试分镜数据
    storyboard_data = {
        "director_intent": {
            "main_emotion": "复仇/愤怒",
            "visual_style": "高端时尚"
        },
        "characters": {
            "女主": {
                "character_id": "char_001",
                "name": "女主",
                "face_identity": "年轻女性，坚毅眼神",
                "clothing_style": "职业套装"
            }
        },
        "film_storyboard": [
            {
                "shot_id": "s1_shot1",
                "shot_type": "establishing",
                "description": "建立镜头"
            },
            {
                "shot_id": "s1_shot2",
                "shot_type": "medium",
                "description": "中景"
            },
            {
                "shot_id": "s1_shot3",
                "shot_type": "close-up",
                "description": "特写"
            },
            {
                "shot_id": "s2_shot1",
                "shot_type": "medium",
                "description": "中景"
            },
            {
                "shot_id": "s2_shot2",
                "shot_type": "close-up",
                "description": "特写"
            },
            {
                "shot_id": "s3_shot1",
                "shot_type": "detail",
                "description": "细节"
            },
            {
                "shot_id": "s3_shot2",
                "shot_type": "medium",
                "description": "中景"
            },
            {
                "shot_id": "s4_shot1",
                "shot_type": "close-up",
                "description": "特写"
            },
            {
                "shot_id": "s4_shot2",
                "shot_type": "establishing",
                "description": "建立镜头"
            },
            {
                "shot_id": "s4_shot3",
                "shot_type": "medium",
                "description": "中景"
            }
        ]
    }

    decision = director.review_storyboard(storyboard_data)
    print(f"\n分镜审核结果:")
    print(f"  决策: {decision.decision_type.value}")
    print(f"  总分: {decision.score.overall:.1f}/10")
    print(f"  镜头逻辑: {decision.score.shot_logic:.1f}/10")
    print(f"  理由: {decision.reason}")


def test_experiment_params():
    """测试实验参数生成"""
    print("\n" + "=" * 60)
    print("测试 3: 实验参数生成")
    print("=" * 60)

    print("\n剧本实验参数:")
    script_params = ExperimentParamsGenerator.generate_script_params()
    for idx, params in enumerate(script_params, 1):
        print(f"\n  版本 {idx}: {params.get('name')}")
        print(f"    冲突时间: {params.get('conflict_timing')}")
        print(f"    反转次数: {params.get('reversal_count')}")
        print(f"    情绪强度: {params.get('emotion_intensity')}")
        print(f"    Hook风格: {params.get('hook_style')}")

    print("\n分镜实验参数:")
    storyboard_params = ExperimentParamsGenerator.generate_storyboard_params()
    for idx, params in enumerate(storyboard_params, 1):
        print(f"\n  版本 {idx}: {params.get('name')}")
        print(f"    镜头数量调整: {params.get('shot_count_multiplier')}")
        print(f"    特写比例: {params.get('closeup_ratio')}")
        print(f"    运镜风格: {params.get('camera_motion')}")


def test_human_selector():
    """测试人工选择器"""
    print("\n" + "=" * 60)
    print("测试 4: 人工选择器（演示）")
    print("=" * 60)

    # 模拟版本数据
    versions = [
        {
            "version_id": "script_v1",
            "params": {
                "name": "快节奏版",
                "conflict_timing": "immediate",
                "reversal_count": 3,
                "emotion_intensity": "extreme",
                "hook_style": "shock"
            },
            "content": "第1集：重生复仇\n\n场景1: [震惊开场]\n女主: （尖叫）不！这不可能！\n旁白: 她死了，又活了...\n\n场景2: [立即冲突]\n男主: （冷笑）你以为你能逃得掉？\n女主: （愤怒）这一世，我要你付出代价！"
        },
        {
            "version_id": "script_v2",
            "params": {
                "name": "标准版",
                "conflict_timing": "early",
                "reversal_count": 2,
                "emotion_intensity": "high",
                "hook_style": "mystery"
            },
            "content": "第1集：重生归来\n\n场景1: [悬念开场]\n女主: （疑惑）这是...哪里？\n旁白: 一切似乎都不对劲...\n\n场景2: [早期冲突]\n妈妈: 你怎么了？\n女主: （震惊）妈妈？你还活着？"
        }
    ]

    print("\n这是一个交互式测试，将显示选择界面")
    print("（实际运行时会等待用户输入）")
    print("\n模拟版本数据:")
    for idx, v in enumerate(versions, 1):
        print(f"\n版本 {idx}: {v['params']['name']}")
        print(f"  参数: {v['params']}")


def test_production_record():
    """测试生产记录"""
    print("\n" + "=" * 60)
    print("测试 5: 生产记录")
    print("=" * 60)

    director = MetaDirector({
        "min_score": 7.0,
        "records_dir": "test_output/records"
    })

    # 开始生产
    record_id = director.start_production("重生千金复仇记", 1)
    print(f"\n生产记录ID: {record_id}")

    # 审核剧本
    script = """第1集：重生归来
场景1: 女主重生了
场景2: 发现真相
场景3: 开始复仇
"""
    decision = director.review_script(script)
    print(f"\n剧本审核: {decision.decision_type.value} ({decision.score.overall:.1f}/10)")

    # 保存记录
    director.save_record()
    print(f"\n✓ 生产记录已保存到: {director.records_dir}")


def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("Meta Director 功能测试")
    print("=" * 60)

    try:
        test_script_review()
        test_storyboard_review()
        test_experiment_params()
        test_human_selector()
        test_production_record()

        print("\n" + "=" * 60)
        print("✅ 所有测试完成")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
