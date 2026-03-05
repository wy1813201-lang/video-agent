#!/usr/bin/env python3
"""
步骤1：测试剧本审核功能
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.meta_director import MetaDirector

print("=" * 60)
print("步骤1：测试剧本审核功能")
print("=" * 60)

# 创建 Meta Director
director = MetaDirector({
    "min_score": 7.0,
    "enable_experiments": True
})

print("\n✓ Meta Director 已创建")
print(f"  最低通过分数: 7.0")
print(f"  实验模式: 启用")

# 测试一个高质量剧本
print("\n" + "-" * 60)
print("测试剧本1：高质量剧本")
print("-" * 60)

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

print(f"\n剧本内容（前100字）:")
print(good_script[:100] + "...")

# 审核剧本
decision = director.review_script(good_script)

print(f"\n审核结果:")
print(f"  决策类型: {decision.decision_type.value}")
print(f"  总分: {decision.score.overall:.1f}/10")
print(f"  详细评分:")
print(f"    - Hook吸引力: {decision.score.hook_strength:.1f}/10")
print(f"    - 剧情结构: {decision.score.plot_structure:.1f}/10")
print(f"    - 情绪节奏: {decision.score.emotion_rhythm:.1f}/10")
print(f"  理由: {decision.reason}")

if decision.decision_type.value == "approve":
    print(f"\n✅ 结论: 剧本通过审核！")
elif decision.decision_type.value == "experiment":
    print(f"\n🧪 结论: 触发实验模式，需要生成多个版本")
else:
    print(f"\n❌ 结论: 剧本未通过，需要重新生成")

# 测试一个低质量剧本
print("\n" + "-" * 60)
print("测试剧本2：低质量剧本")
print("-" * 60)

bad_script = """第1集

场景1: 早上起床了
对话: 今天天气不错

场景2: 去上学
对话: 路上遇到了同学
"""

print(f"\n剧本内容:")
print(bad_script)

# 审核剧本
decision2 = director.review_script(bad_script)

print(f"\n审核结果:")
print(f"  决策类型: {decision2.decision_type.value}")
print(f"  总分: {decision2.score.overall:.1f}/10")
print(f"  详细评分:")
print(f"    - Hook吸引力: {decision2.score.hook_strength:.1f}/10")
print(f"    - 剧情结构: {decision2.score.plot_structure:.1f}/10")
print(f"    - 情绪节奏: {decision2.score.emotion_rhythm:.1f}/10")
print(f"  理由: {decision2.reason}")

if decision2.decision_type.value == "approve":
    print(f"\n✅ 结论: 剧本通过审核！")
elif decision2.decision_type.value == "experiment":
    print(f"\n🧪 结论: 触发实验模式，需要生成多个版本")
else:
    print(f"\n❌ 结论: 剧本未通过，需要重新生成")

print("\n" + "=" * 60)
print("步骤1完成！")
print("=" * 60)
