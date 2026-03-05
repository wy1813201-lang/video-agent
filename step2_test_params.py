#!/usr/bin/env python3
"""
步骤2：测试实验参数生成
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.experiment_engine import ExperimentParamsGenerator

print("=" * 60)
print("步骤2：测试实验参数生成")
print("=" * 60)

print("\n当剧本评分在6.0-8.0之间时，系统会生成多个实验版本")
print("每个版本使用不同的参数来优化内容")

# 生成剧本实验参数
print("\n" + "-" * 60)
print("剧本实验参数")
print("-" * 60)

script_params = ExperimentParamsGenerator.generate_script_params()

for idx, params in enumerate(script_params, 1):
    print(f"\n版本 {idx}: {params.get('name')}")
    print(f"  冲突时间: {params.get('conflict_timing')}")
    print(f"    - immediate: 第一句话就有冲突")
    print(f"    - early: 前10秒内出现冲突")
    print(f"  反转次数: {params.get('reversal_count')} 个")
    print(f"  情绪强度: {params.get('emotion_intensity')}")
    print(f"    - extreme: 极端化情绪（暴怒、崩溃）")
    print(f"    - high: 高强度情绪")
    print(f"  Hook风格: {params.get('hook_style')}")
    print(f"    - shock: 震惊式（死亡、背叛）")
    print(f"    - mystery: 悬念式（秘密、真相）")
    print(f"  场景数量: {params.get('scene_count')} 个")

# 生成分镜实验参数
print("\n" + "-" * 60)
print("分镜实验参数")
print("-" * 60)

storyboard_params = ExperimentParamsGenerator.generate_storyboard_params()

for idx, params in enumerate(storyboard_params, 1):
    print(f"\n版本 {idx}: {params.get('name')}")
    print(f"  镜头数量调整: {params.get('shot_count_multiplier')}")
    print(f"    - 1.2 = 增加20%镜头")
    print(f"    - 0.9 = 减少10%镜头")
    print(f"  特写比例: {params.get('closeup_ratio')}")
    print(f"    - 0.5 = 50%特写镜头")
    print(f"    - 0.3 = 30%特写镜头")
    print(f"  运镜风格: {params.get('camera_motion')}")
    print(f"    - dynamic: 动态运镜（跟踪、环绕）")
    print(f"    - stable: 稳定运镜（推拉、固定）")
    print(f"  剪辑速度: {params.get('cut_speed')}")

print("\n" + "=" * 60)
print("步骤2完成！")
print("=" * 60)
print("\n💡 说明：这些参数会用于生成不同风格的变体版本")
print("   系统会根据这些参数调用LLM重新生成内容")
