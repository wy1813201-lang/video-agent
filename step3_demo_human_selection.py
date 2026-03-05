#!/usr/bin/env python3
"""
步骤3：人工选择流程演示（自动版）

展示人工选择界面的样子，不需要实际输入
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.meta_director import MetaDirector

print("=" * 60)
print("步骤3：人工选择流程演示")
print("=" * 60)

# 步骤 1：审核剧本
print("\n" + "-" * 60)
print("步骤 1：Meta Director 审核剧本")
print("-" * 60)

director = MetaDirector({
    "min_score": 8.5,
    "enable_experiments": True
})

test_script = """第1集：重生归来

场景1: [清晨·卧室]
女主: （震惊）这是...十年前？我重生了？
旁白: 当她再次睁开眼，时间回到了那个改变命运的早晨...

场景2: [客厅·冲突]
妈妈: 起来了？快来吃早餐。
女主: （泪流满面）妈...妈妈...(上一世，妈妈已经...)

场景3: [学校·反转]
同学: 听说今天有新同学转来...
男主: （出场）大家好，我是...
女主: （内心）是他！就是这个人，上一世害我家破人亡！

场景4: [结尾·钩子]
女主: （内心）既然重生了，这一世我一定要保护好家人，让他付出代价！
"""

decision = director.review_script(test_script)

print(f"\n审核结果:")
print(f"  决策: {decision.decision_type.value}")
print(f"  总分: {decision.score.overall:.1f}/10")
print(f"  详细评分:")
print(f"    - Hook吸引力: {decision.score.hook_strength:.1f}/10 {'❌' if decision.score.hook_strength < 8.5 else '✅'}")
print(f"    - 剧情结构: {decision.score.plot_structure:.1f}/10 {'❌' if decision.score.plot_structure < 8.5 else '✅'}")
print(f"    - 情绪节奏: {decision.score.emotion_rhythm:.1f}/10 {'❌' if decision.score.emotion_rhythm < 8.5 else '✅'}")
print(f"\n  理由: {decision.reason}")

if decision.decision_type.value != "experiment":
    print(f"\n✅ 直接通过，不需要人工选择")
    sys.exit(0)

print(f"\n🧪 触发实验模式！")

# 步骤 2：生成实验版本（模拟）
print("\n" + "-" * 60)
print("步骤 2：生成实验版本")
print("-" * 60)

print("\n系统会调用 LLM 根据不同参数重新生成剧本：")
print("  版本 1: 快节奏版（immediate冲突 + extreme情绪 + shock开场）")
print("  版本 2: 标准版（early冲突 + high情绪 + mystery开场）")

# 步骤 3：展示人工选择界面
print("\n" + "-" * 60)
print("步骤 3：人工选择界面（🔥 关键步骤）")
print("-" * 60)

print("\n" + "=" * 60)
print("🧪 实验版本选择")
print("=" * 60)

print("\n【版本 1】script_ep01_v1")
print("参数: 快节奏版")
print("特点:")
print("  - 冲突时间: immediate")
print("  - 反转次数: 3")
print("  - 情绪强度: extreme")
print("  - Hook风格: shock")
print("\n预览:")
print("""第1集：重生复仇

场景1: [震惊开场·立即冲突]
女主: （尖叫）不！这不可能！我死了...又活了？
旁白: 她死了，又活了...时间倒流到十年前！
女主: （暴怒）这一世，我要让所有人付出代价！

场景2: [极端情绪·快速反转]
妈妈: 你怎么了？
女主: （崩溃）妈妈！你还活着！（泪流满面）
...""")

print("\n【版本 2】script_ep01_v2")
print("参数: 标准版")
print("特点:")
print("  - 冲突时间: early")
print("  - 反转次数: 2")
print("  - 情绪强度: high")
print("  - Hook风格: mystery")
print("\n预览:")
print("""第1集：重生归来

场景1: [悬念开场]
女主: （疑惑）这是...哪里？
旁白: 一切似乎都不对劲...
女主: （震惊）等等...这是十年前的房间！

场景2: [早期冲突·情绪递进]
妈妈: 起来了？快来吃早餐。
女主: （震惊）妈妈？你还活着？
...""")

print("\n" + "-" * 60)
print("👤 人工选择（这里需要人工输入）")
print("-" * 60)

print("\n系统提示: 请选择最佳版本 (1-2) 或输入 0 跳过: ")
print("👉 假设用户输入: 1")

print("\n系统提示: 请说明选择理由: ")
print("👉 假设用户输入: 开头更有冲击力，情绪更强烈，更能吸引观众")

# 步骤 4：记录选择
print("\n" + "-" * 60)
print("步骤 4：记录选择结果")
print("-" * 60)

print("\n✓ 已选择: script_ep01_v1")
print("✓ 理由: 开头更有冲击力，情绪更强烈，更能吸引观众")

print("\n💾 选择结果会被保存到生产记录:")
print("""
{
  "experiments": [
    {
      "version_id": "script_ep01_v1",
      "params": {
        "name": "快节奏版",
        "conflict_timing": "immediate",
        "reversal_count": 3,
        "emotion_intensity": "extreme",
        "hook_style": "shock"
      },
      "selected": true,
      "selection_reason": "开头更有冲击力，情绪更强烈，更能吸引观众"
    },
    {
      "version_id": "script_ep01_v2",
      "params": {...},
      "selected": false
    }
  ]
}
""")

# 步骤 5：继续流程
print("\n" + "-" * 60)
print("步骤 5：使用选中版本继续流程")
print("-" * 60)

print("\n✓ 使用 script_ep01_v1 继续生成分镜")
print("✓ 后续的分镜、视频生成都基于这个选中的剧本")

print("\n" + "=" * 60)
print("完整流程总结")
print("=" * 60)

print("""
1️⃣ Meta Director 审核
   ├─ 评分: Hook 8.0, 剧情 7.5, 情绪 7.0
   ├─ 判断: 有维度 < 8.5
   └─ 决策: 触发实验模式

2️⃣ 实验引擎生成多版本
   ├─ 调用 LLM 生成版本1（快节奏版）
   ├─ 调用 LLM 生成版本2（标准版）
   └─ 准备好所有版本

3️⃣ 🔥 人工选择界面（关键！）
   ├─ 展示所有版本的参数和预览
   ├─ 等待人工输入选择（1 或 2）
   ├─ 要求输入选择理由
   └─ 记录选择结果

4️⃣ 使用选中版本
   ├─ 替换原剧本
   ├─ 继续后续流程（分镜、视频）
   └─ 保存到生产记录

5️⃣ 数据积累
   └─ 所有选择和理由用于未来AI学习
""")

print("\n💡 人工选择发生的位置:")
print("   文件: src/human_selector.py")
print("   类: HumanSelector")
print("   方法: select_best_script()")
print("   调用位置: main.py 第 960-979 行")

print("\n💡 在真实运行中:")
print("   python main.py generate --topic '测试' --style 情感 --episodes 1")
print("   当评分 < 8.5 时，会自动弹出选择界面等待你输入")
