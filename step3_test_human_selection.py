#!/usr/bin/env python3
"""
步骤3：测试人工选择流程

展示完整的人工干预流程：
1. 剧本评分低于 8.5
2. 触发实验模式
3. 生成多个版本（模拟）
4. 人工选择界面
5. 记录选择结果
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.meta_director import MetaDirector
from src.human_selector import HumanSelector

print("=" * 60)
print("步骤3：测试人工选择流程")
print("=" * 60)

# 创建 Meta Director
director = MetaDirector({
    "min_score": 8.5,
    "enable_experiments": True,
    "experiment_count": 2
})

print("\n✓ Meta Director 已创建（8.5 标准）")

# 步骤 1：审核剧本
print("\n" + "-" * 60)
print("步骤 1：审核剧本")
print("-" * 60)

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

print(f"\n剧本内容（前100字）:")
print(test_script[:100] + "...")

decision = director.review_script(test_script)

print(f"\n审核结果:")
print(f"  决策类型: {decision.decision_type.value}")
print(f"  总分: {decision.score.overall:.1f}/10")
print(f"  详细评分:")
print(f"    - Hook吸引力: {decision.score.hook_strength:.1f}/10")
print(f"    - 剧情结构: {decision.score.plot_structure:.1f}/10")
print(f"    - 情绪节奏: {decision.score.emotion_rhythm:.1f}/10")
print(f"  理由: {decision.reason}")

if decision.decision_type.value == "approve":
    print(f"\n✅ 结论: 所有维度达到8.5，直接通过！")
    print("\n⚠️ 不会触发人工选择")
    sys.exit(0)
elif decision.decision_type.value == "experiment":
    print(f"\n🧪 结论: 有维度低于8.5，触发实验模式！")
    print("\n→ 接下来会生成多个实验版本，然后进入人工选择")
else:
    print(f"\n❌ 结论: 质量过低")
    sys.exit(1)

# 步骤 2：模拟生成实验版本
print("\n" + "-" * 60)
print("步骤 2：生成实验版本（模拟）")
print("-" * 60)

print("\n在真实流程中，这里会调用 LLM 重新生成剧本")
print("现在我们模拟生成 2 个版本：")

# 模拟版本 1：快节奏版
version1 = {
    "version_id": "script_ep01_v1",
    "params": {
        "name": "快节奏版",
        "conflict_timing": "immediate",
        "reversal_count": 3,
        "emotion_intensity": "extreme",
        "hook_style": "shock"
    },
    "content": """第1集：重生复仇

场景1: [震惊开场·立即冲突]
女主: （尖叫）不！这不可能！我死了...又活了？
旁白: 她死了，又活了...时间倒流到十年前！
女主: （暴怒）这一世，我要让所有人付出代价！

场景2: [极端情绪·快速反转]
妈妈: 你怎么了？
女主: （崩溃）妈妈！你还活着！（泪流满面）
妈妈: （震惊）孩子，你怎么了？
女主: （突然冷静）没事...我只是太高兴了。

场景3: [立即对抗·强烈冲突]
男主: （出场）大家好，我是...
女主: （冷笑）是你！害我家破人亡的人！
男主: （疑惑）你...你在说什么？
女主: （愤怒）这一世，我不会再让你得逞！

场景4: [震惊结尾]
女主: （内心）复仇的火焰，已经点燃！
旁白: 她的复仇，才刚刚开始...
字幕: 下一集，真相揭晓！
"""
}

# 模拟版本 2：标准版
version2 = {
    "version_id": "script_ep01_v2",
    "params": {
        "name": "标准版",
        "conflict_timing": "early",
        "reversal_count": 2,
        "emotion_intensity": "high",
        "hook_style": "mystery"
    },
    "content": """第1集：重生归来

场景1: [悬念开场]
女主: （疑惑）这是...哪里？
旁白: 一切似乎都不对劲...
女主: （震惊）等等...这是十年前的房间！

场景2: [早期冲突·情绪递进]
妈妈: 起来了？快来吃早餐。
女主: （震惊）妈妈？你还活着？
妈妈: （担心）你怎么了？是不是做噩梦了？
女主: （泪流满面）妈妈...（紧紧抱住）

场景3: [悬念反转]
同学: 听说今天有新同学转来...
男主: （出场）大家好，我是...
女主: （内心）是他...上一世的那个人...
女主: （警惕）你好...（内心：我要查清真相）

场景4: [悬念结尾]
女主: （内心）既然重生了，我一定要查清真相，保护家人！
旁白: 真相，究竟是什么？
字幕: 敬请期待下一集
"""
}

versions = [version1, version2]

print(f"\n✓ 已生成 {len(versions)} 个版本")
for idx, v in enumerate(versions, 1):
    print(f"  版本 {idx}: {v['params']['name']}")

# 步骤 3：人工选择（这里是关键！）
print("\n" + "-" * 60)
print("步骤 3：人工选择界面（关键步骤！）")
print("-" * 60)

print("\n⚠️ 接下来会进入交互式界面")
print("   系统会展示所有版本的参数和内容预览")
print("   你需要输入数字选择最佳版本")
print("   并说明选择理由")
print("\n按 Enter 继续...")
input()

# 🔥 这里是人工选择发生的地方！
selected = HumanSelector.select_best_script(versions)

# 步骤 4：记录选择结果
print("\n" + "-" * 60)
print("步骤 4：记录选择结果")
print("-" * 60)

if selected:
    print(f"\n✓ 你选择了: {selected['version_id']}")
    print(f"✓ 选择理由: {selected['reason']}")
    print(f"\n选中的剧本内容（前200字）:")
    print(selected['content'][:200] + "...")

    # 在真实流程中，这个选择会被记录到生产记录中
    print(f"\n💾 在真实流程中，这个选择会被保存到:")
    print(f"   data/production_records/*.json")
    print(f"\n   记录内容包括:")
    print(f"   - 所有版本的参数")
    print(f"   - 你选择的版本ID")
    print(f"   - 你的选择理由")
    print(f"   - 用于未来的数据分析和AI学习")
else:
    print(f"\n⚠️ 你跳过了选择，将使用原版本")

print("\n" + "=" * 60)
print("步骤3完成！")
print("=" * 60)

print("\n💡 人工选择流程总结:")
print("   1. Meta Director 评分 → 发现有维度 < 8.5")
print("   2. 触发实验模式 → 生成多个版本")
print("   3. 🔥 HumanSelector 展示界面 → 人工选择最佳版本")
print("   4. 记录选择理由 → 保存到生产记录")
print("   5. 使用选中版本 → 继续后续流程")
