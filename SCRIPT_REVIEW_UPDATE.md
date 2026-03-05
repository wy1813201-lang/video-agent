# 统一审查系统更新 - 添加剧本审查

## 🎉 更新内容

成功将**剧本审查**功能集成到统一审查系统中！

现在统一审查界面包含 **4 个标签页**：

1. 📝 **剧本审查**（新增）
2. 👥 **人物母版**
3. 🎥 **视频片段**
4. ✨ **最终视频**

---

## 📝 剧本审查功能

### 显示内容

1. **剧本完整内容**
   - 可滚动查看
   - 等宽字体显示
   - 保留原始格式

2. **Meta Director 评分**
   - 总分（0-10）
   - Hook吸引力（0-10）
   - 剧情结构（0-10）
   - 情绪节奏（0-10）

3. **评分状态**
   - ✓ 达标（≥ 8.5）- 绿色
   - ✗ 未达标（< 8.5）- 橙色/红色

### 界面特点

- 📊 **评分卡片**：网格布局展示所有评分
- 🎨 **颜色编码**：
  - 绿色：≥ 8.5（达标）
  - 橙色：7.0-8.5（警告）
  - 红色：< 7.0（不达标）
- 📱 **响应式设计**：自动适配屏幕大小

---

## 🔄 完整工作流程（更新）

```
生成剧本
    ↓
Meta Director 评分
    ↓
评分 < 8.5？
    ↓
🌐 自动打开浏览器（剧本审查界面）
    ↓
显示剧本内容 + 评分详情
    ↓
👤 人工审查 → 通过/不通过
    ↓
如果不通过 → 触发实验模式（生成多版本）
如果通过 → 继续
    ↓
生成人物母版
    ↓
🌐 自动打开浏览器（人物母版审查）
    ↓
👤 人工审查 → 通过/不通过
    ↓
生成视频片段
    ↓
🌐 自动打开浏览器（视频片段审查）
    ↓
👤 人工审查 → 通过/不通过
    ↓
合成最终视频
    ↓
🌐 自动打开浏览器（最终视频审查）
    ↓
👤 人工审查 → 通过/不通过
    ↓
完成！🎉
```

---

## 📂 更新的文件

### 后端代码
1. `src/unified_review_system.py`
   - 添加 `review_script()` 方法
   - 更新 `review_all()` 方法支持剧本参数
   - 更新 `MetaDirectorWithReview` 类

### 前端界面
2. `templates/unified_review.html`
   - 添加剧本审查标签页
   - 添加剧本内容展示样式
   - 添加评分卡片样式
   - 添加 `renderScript()` JavaScript 函数

### 测试文件
3. `test_unified_review.py`
   - 添加剧本测试数据
   - 添加剧本审查选项（选项1）

### 预览文件
4. `unified_review_preview.html`
   - 添加剧本审查标签页
   - 显示示例剧本和评分

---

## 🚀 使用方式

### 方式 1：单独审查剧本

```python
from src.unified_review_system import UnifiedReviewSystem

review_system = UnifiedReviewSystem()

# 剧本内容
script = """第1集：重生归来
场景1: ...
"""

# Meta Director 评分
score = {
    "overall": 7.5,
    "hook_strength": 8.0,
    "plot_structure": 7.5,
    "emotion_rhythm": 7.0
}

# 启动审查
result = review_system.review_script(script, score)

if result['status'] == 'approved':
    print("✓ 剧本通过审查")
else:
    print("❌ 剧本未通过")
```

### 方式 2：集成到 Meta Director

```python
from src.unified_review_system import MetaDirectorWithReview

meta_director = MetaDirectorWithReview(config)

# 生成剧本后自动审查
if meta_director.review_script(script, score):
    print("✓ 剧本通过")
    # 继续生成人物母版
else:
    print("❌ 剧本未通过，需要修改")
    # 重新生成或触发实验模式
```

### 方式 3：统一审查所有内容

```python
# 一次性审查所有内容
approved = meta_director.review_all(
    script=script,
    script_score=score,
    characters=characters,
    videos=videos,
    final_video=final_video_path
)
```

### 方式 4：测试

```bash
cd ~/.openclaw/workspace/ai-short-drama-automator
python test_unified_review.py

# 选择选项 1：剧本审查
# 或选择选项 5：完整内容审查（包含剧本）
```

---

## 🎯 审查要点

### 剧本审查检查项

1. **Hook吸引力（≥ 8.5）**
   - ✅ 开头是否有强烈冲突
   - ✅ 是否能立即抓住观众注意力
   - ✅ 是否有悬念或震惊元素

2. **剧情结构（≥ 8.5）**
   - ✅ 场景数量是否合理（3-5个）
   - ✅ 是否有明确的冲突和反转
   - ✅ 剧情是否连贯

3. **情绪节奏（≥ 8.5）**
   - ✅ 情绪变化是否明显
   - ✅ 是否有多种情绪类型
   - ✅ 情绪递进是否自然

4. **整体质量（≥ 8.5）**
   - ✅ 所有维度都达标
   - ✅ 符合短剧节奏
   - ✅ 适合竖屏观看

---

## 💡 使用建议

### 1. 审查时机
- **剧本生成后立即审查**：避免后续浪费资源
- **评分 < 8.5 时必须审查**：确保质量
- **可以跳过高分剧本**：≥ 8.5 可自动通过

### 2. 审查重点
- 重点关注**未达标的维度**（红色/橙色）
- 对比评分和实际内容是否匹配
- 提供具体的改进建议

### 3. 反馈建议
好的反馈示例：
- ✅ "Hook吸引力不足，建议在开头增加更强烈的冲突"
- ✅ "情绪节奏偏弱，建议增加情绪对比"
- ✅ "剧情结构合理，但第3场景可以更紧凑"

避免模糊反馈：
- ❌ "不好"
- ❌ "需要改进"

---

## 📊 界面预览

已在浏览器中打开更新后的预览：
- `unified_review_preview.html`

包含：
- 📝 剧本审查标签页（新增）
- 剧本内容展示
- 评分卡片（总分、Hook、剧情、情绪）
- 达标/未达标状态

---

## 🎉 总结

现在统一审查系统支持**完整的内容审查流程**：

✅ **剧本审查**（新增）- 内容 + 评分
✅ **人物母版审查** - 角色形象
✅ **视频片段审查** - 镜头质量
✅ **最终视频审查** - 成片效果

**核心价值**：
1. 一站式审查所有内容
2. 可视化评分展示
3. 自动弹出 + 自动关闭
4. 完整的决策记录

现在你有了一个**完整的质量控制系统**，从剧本到最终视频，每个环节都有人工把关！🎬✨

---

**更新时间**: 2026-03-04

**预览文件**: `unified_review_preview.html`（已在浏览器中打开）

**测试命令**: `python test_unified_review.py`（选择选项 1 或 5）
