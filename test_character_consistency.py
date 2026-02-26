"""
测试脚本：验证角色一致性图像生成流程
角色：林诗雨，22岁，长发飘逸，气质温柔，穿白色连衣裙
"""

import sys
import os
from pathlib import Path

# 确保 src 模块可导入
sys.path.insert(0, str(Path(__file__).parent))

from src.character_consistency import CharacterTrait, CharacterExtractor, PromptEnhancer
from src.cozex_client import CozexClient

# ── 1. 定义固定角色 ──────────────────────────────────────────────
LIN_SHIYU = CharacterTrait(
    name="林诗雨",
    appearance="beautiful 22-year-old Chinese woman, long flowing black hair, gentle temperament, fair skin, soft expressive eyes",
    outfit="white flowy dress, elegant and pure",
    personality="gentle, warm, graceful",
    age_range="22 years old",
    gender="female",
    extra_tags=["protagonist", "detailed face", "consistent character"]
)

# ── 2. 三个场景剧本 ──────────────────────────────────────────────
SCENES = [
    {
        "id": 1,
        "name": "咖啡馆初遇",
        "script": "林诗雨坐在窗边的咖啡馆里，阳光洒在她身上，她轻轻翻着书页，嘴角带着淡淡的微笑。",
        "base_prompt": "a young woman sitting by a cafe window, warm sunlight, reading a book, cozy interior, soft bokeh background, cinematic lighting"
    },
    {
        "id": 2,
        "name": "公园漫步",
        "script": "林诗雨漫步在樱花盛开的公园小径上，粉色花瓣随风飘落，她抬头望向天空，神情宁静。",
        "base_prompt": "a young woman walking in a cherry blossom park, pink petals falling, looking up at the sky, peaceful expression, spring atmosphere, dreamy"
    },
    {
        "id": 3,
        "name": "雨夜等待",
        "script": "夜晚，林诗雨站在路灯下，细雨打湿了她的发梢，她望着远处，眼神中带着一丝期待。",
        "base_prompt": "a young woman standing under a street lamp at night, light rain, wet hair, looking into the distance, hopeful expression, moody night scene, cinematic"
    }
]

# ── 3. 初始化角色一致性模块 ──────────────────────────────────────
custom_templates = {"林诗雨": LIN_SHIYU}
extractor = CharacterExtractor(custom_templates=custom_templates)

# 注册角色关键词（直接用名字匹配）
from src.character_consistency import CHARACTER_KEYWORDS
CHARACTER_KEYWORDS["林诗雨"] = ["林诗雨"]

characters = {"林诗雨": LIN_SHIYU}
enhancer = PromptEnhancer(characters=characters)

# ── 4. 生成增强提示词 ────────────────────────────────────────────
print("=" * 60)
print("角色一致性图像生成测试")
print("角色：林诗雨 | 22岁 | 长发飘逸 | 白色连衣裙")
print("=" * 60)

enhanced_prompts = []
for scene in SCENES:
    enhanced = enhancer.enhance(scene["base_prompt"], scene["script"])
    enhanced_prompts.append(enhanced)
    print(f"\n场景 {scene['id']}：{scene['name']}")
    print(f"增强提示词：{enhanced[:120]}...")

# ── 5. 调用 CozexClient 生成图像 ─────────────────────────────────
print("\n" + "=" * 60)
print("开始生成图像...")
print("=" * 60)

# 覆盖输出目录到 ~/Desktop/ShortDrama/test/
output_dir = Path("~/Desktop/ShortDrama/test").expanduser()
output_dir.mkdir(parents=True, exist_ok=True)

client = CozexClient()
client.output_dir = output_dir  # 重定向到 test 子目录

results = []
for i, (scene, prompt) in enumerate(zip(SCENES, enhanced_prompts)):
    print(f"\n[{i+1}/3] 生成场景：{scene['name']}")
    print(f"  提示词：{prompt[:80]}...")
    try:
        result = client.image_generation(prompt)
        saved_path = result.get("saved_path", "未知路径")
        results.append({"scene": scene["name"], "status": "success", "path": saved_path})
        print(f"  ✅ 成功 → {saved_path}")
    except Exception as e:
        results.append({"scene": scene["name"], "status": "failed", "error": str(e)})
        print(f"  ❌ 失败：{e}")

# ── 6. 汇报结果 ──────────────────────────────────────────────────
print("\n" + "=" * 60)
print("生成结果汇总")
print("=" * 60)
success = sum(1 for r in results if r["status"] == "success")
print(f"成功：{success}/3")
for r in results:
    status_icon = "✅" if r["status"] == "success" else "❌"
    if r["status"] == "success":
        print(f"  {status_icon} {r['scene']} → {r['path']}")
    else:
        print(f"  {status_icon} {r['scene']} → 错误：{r['error']}")

print(f"\n输出目录：{output_dir}")
print("=" * 60)
