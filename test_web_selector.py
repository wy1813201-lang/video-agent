#!/usr/bin/env python3
"""
测试 Web 人工选择界面

启动 Web 服务器，展示人工选择界面
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.web_human_selector import WebHumanSelector

print("=" * 60)
print("Web 人工选择界面测试")
print("=" * 60)

# 模拟版本数据
versions = [
    {
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
    },
    {
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
]

print("\n准备启动 Web 界面...")
print("版本数量:", len(versions))

# 创建 Web 选择器
selector = WebHumanSelector(port=5000)

print("\n🌐 Web 界面将在浏览器中打开")
print("   请在浏览器中选择最佳版本并说明理由")
print("   选择完成后，结果会显示在这里\n")

# 启动选择流程
selected = selector.select_best_script(versions)

if selected:
    print("\n" + "=" * 60)
    print("选择结果")
    print("=" * 60)
    print(f"\n✓ 选中版本: {selected['version_id']}")
    print(f"✓ 选择理由: {selected['reason']}")
    print(f"\n选中的剧本内容（前200字）:")
    print(selected['content'][:200] + "...")
else:
    print("\n⚠️ 未选择版本")

print("\n" + "=" * 60)
print("测试完成！")
print("=" * 60)
