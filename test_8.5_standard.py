#!/usr/bin/env python3
"""
测试 8.5 标准：所有维度都必须达到 8.5 才通过
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.meta_director import MetaDirector

print("=" * 60)
print("测试 8.5 标准：所有维度必须达到 8.5")
print("=" * 60)

director = MetaDirector({
    "min_score": 8.5,
    "enable_experiments": True
})

# 测试1：高质量剧本（应该通过）
print("\n" + "-" * 60)
print("测试 1: 高质量剧本（预期：通过）")
print("-" * 60)

excellent_script = """第1集：重生归来

场景1: [清晨·卧室·震惊开场]
女主: （尖叫）不！这不可能！我重生了？
旁白: 当她再次睁开眼，时间回到了那个改变命运的早晨...
女主: （泪流满面）这次，我一定要改变一切！

场景2: [客厅·立即冲突]
妈妈: 起来了？快来吃早餐。
女主: （泪流满面）妈...妈妈...(上一世，妈妈已经死了...)
妈妈: （震惊）怎么了？傻孩子，你怎么哭了？
女主: （愤怒）我不会再让悲剧重演！

场景3: [学校·反转]
同学: 听说今天有新同学转来...
男主: （出场）大家好，我是...
女主: （内心）是他！就是这个人，上一世害我家破人亡！
女主: （冷笑）原来是你...这一世，我不会再上当！
男主: （疑惑）你...认识我？

场景4: [结尾·钩子]
女主: （内心）既然重生了，这一世我一定要保护好家人，让他付出代价！
旁白: 复仇的序幕，就此拉开...
字幕: 敬请期待下一集
"""

decision1 = director.review_script(excellent_script)
print(f"\n审核结果:")
print(f"  决策: {decision1.decision_type.value}")
print(f"  总分: {decision1.score.overall:.1f}/10")
print(f"  详细评分:")
print(f"    - Hook吸引力: {decision1.score.hook_strength:.1f}/10")
print(f"    - 剧情结构: {decision1.score.plot_structure:.1f}/10")
print(f"    - 情绪节奏: {decision1.score.emotion_rhythm:.1f}/10")
print(f"  理由: {decision1.reason}")

if decision1.decision_type.value == "approve":
    print(f"\n✅ 结论: 所有维度达到8.5，直接通过！")
elif decision1.decision_type.value == "experiment":
    print(f"\n🧪 结论: 有维度低于8.5，触发人工评选！")
else:
    print(f"\n❌ 结论: 质量过低，需要重新生成")

# 测试2：中等质量剧本（应该触发人工评选）
print("\n" + "-" * 60)
print("测试 2: 中等质量剧本（预期：触发人工评选）")
print("-" * 60)

medium_script = """第1集：重生归来

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

decision2 = director.review_script(medium_script)
print(f"\n审核结果:")
print(f"  决策: {decision2.decision_type.value}")
print(f"  总分: {decision2.score.overall:.1f}/10")
print(f"  详细评分:")
print(f"    - Hook吸引力: {decision2.score.hook_strength:.1f}/10")
print(f"    - 剧情结构: {decision2.score.plot_structure:.1f}/10")
print(f"    - 情绪节奏: {decision2.score.emotion_rhythm:.1f}/10")
print(f"  理由: {decision2.reason}")

if decision2.decision_type.value == "approve":
    print(f"\n✅ 结论: 所有维度达到8.5，直接通过！")
elif decision2.decision_type.value == "experiment":
    print(f"\n🧪 结论: 有维度低于8.5，触发人工评选！")
else:
    print(f"\n❌ 结论: 质量过低，需要重新生成")

# 测试3：低质量剧本（应该触发人工评选）
print("\n" + "-" * 60)
print("测试 3: 低质量剧本（预期：触发人工评选）")
print("-" * 60)

bad_script = """第1集

场景1: 早上起床了
对话: 今天天气不错

场景2: 去上学
对话: 路上遇到了同学
"""

decision3 = director.review_script(bad_script)
print(f"\n审核结果:")
print(f"  决策: {decision3.decision_type.value}")
print(f"  总分: {decision3.score.overall:.1f}/10")
print(f"  详细评分:")
print(f"    - Hook吸引力: {decision3.score.hook_strength:.1f}/10")
print(f"    - 剧情结构: {decision3.score.plot_structure:.1f}/10")
print(f"    - 情绪节奏: {decision3.score.emotion_rhythm:.1f}/10")
print(f"  理由: {decision3.reason}")

if decision3.decision_type.value == "approve":
    print(f"\n✅ 结论: 所有维度达到8.5，直接通过！")
elif decision3.decision_type.value == "experiment":
    print(f"\n🧪 结论: 有维度低于8.5，触发人工评选！")
else:
    print(f"\n❌ 结论: 质量过低，需要重新生成")

print("\n" + "=" * 60)
print("测试完成！")
print("=" * 60)
print("\n💡 新规则说明：")
print("   - 所有维度（Hook/剧情/情绪）都必须 ≥ 8.5 才直接通过")
print("   - 任何维度 < 8.5，触发人工评选（生成多个版本供选择）")
print("   - 人工评选时会展示所有版本，由人工选择最佳版本")
