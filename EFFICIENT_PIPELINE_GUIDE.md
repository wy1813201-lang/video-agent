# 高效生产流程指南

## 🎯 新流程概述

这是一个更高效的 AI 短剧生产流程，减少人工介入次数，提高自动化程度。

### 流程对比

**旧流程** (多次人工介入):
```
生成剧本 → 评分 < 8.5? → 实验模式 → 人工选择
    ↓
生成角色 → 人工审查
    ↓
生成视频 → 人工审查
    ↓
最终视频 → 人工审查
```

**新流程** (只2次人工介入):
```
生成3个剧本 → AI自动评分 → 只保留最高分
    ↓
生成角色母版 → 人工确认一次 ✋
    ↓
生成分镜 → 生成视频
    ↓
AI自动检测质量 → 输出3个最终版本
    ↓
人工选1个发布 ✋
```

---

## 📊 流程详解

### 阶段1: 生成3个剧本 → AI自动评分 → 选最高分

**目的**: 前期批量生成，AI自动筛选，无需人工介入

**实现**:
```python
from src.efficient_pipeline import EfficientPipeline

pipeline = EfficientPipeline()
pipeline.start_session("重生复仇")

# 生成3个剧本并自动选择最高分
selected_script = pipeline.generate_and_select_script(
    script_generator=script_gen,
    topic="重生复仇",
    style="情感"
)
```

**评分维度**:
- Hook吸引力 (0-10分)
- 剧情结构 (0-10分)
- 情绪节奏 (0-10分)
- 总分 = 平均分

**输出**:
```
[1/3] 生成剧本候选...
   总分: 7.2/10
   Hook: 7.0
   剧情: 7.5
   情绪: 7.0

[2/3] 生成剧本候选...
   总分: 8.5/10
   Hook: 9.0
   剧情: 8.5
   情绪: 8.0

[3/3] 生成剧本候选...
   总分: 6.8/10
   Hook: 6.5
   剧情: 7.0
   情绪: 7.0

✓ 自动选择最高分剧本: script_2
  总分: 8.5/10
```

---

### 阶段2: 生成角色母版 → 人工确认一次 ✋

**目的**: 角色是整个短剧的基础，必须人工把关

**实现**:
```python
# 生成角色
characters = pipeline.generate_characters(
    character_generator=char_gen,
    script=selected_script["content"]
)

# 请求人工确认 (自动弹出Web审查界面)
approved = pipeline.request_character_approval(characters)

if not approved:
    print("角色未通过，流程终止")
    return
```

**审查界面**:
- 自动弹出浏览器
- 显示所有角色的形象、名称、描述
- 人工点击 "通过" 或 "不通过"
- 通过后自动关闭，继续流程

---

### 阶段3: 生成分镜 → 生成视频

**目的**: 自动化生成，无需人工介入

**实现**:
```python
# 生成分镜和视频片段
video_clips = pipeline.generate_storyboard_and_videos(
    storyboard_manager=storyboard_mgr,
    script=selected_script["content"],
    characters=characters
)
```

**输出**:
```
[1/2] 生成分镜...
✓ 生成了 5 个镜头

[2/2] 生成视频片段...
  生成镜头 1/5...
  生成镜头 2/5...
  生成镜头 3/5...
  生成镜头 4/5...
  生成镜头 5/5...

✓ 生成了 5 个视频片段
```

---

### 阶段4: AI质量检测 → 输出3个最终版本

**目的**: AI自动生成多个风格版本，供人工选择

**实现**:
```python
# 生成3个不同风格的最终版本
final_versions = pipeline.generate_final_versions(video_clips)
```

**3个版本**:

1. **标准版** (平衡)
   - 转场时长: 0.8秒
   - BGM音量: 0.3
   - 调色风格: cinematic

2. **快节奏版** (激烈)
   - 转场时长: 0.4秒
   - BGM音量: 0.5
   - 调色风格: vibrant

3. **情感版** (柔和)
   - 转场时长: 1.2秒
   - BGM音量: 0.2
   - 调色风格: warm

**AI质量检测**:
- 自动评估转场自然度
- 自动评估音量平衡
- 自动评估调色质量
- 输出质量分 (0-10分)

**输出**:
```
[1/3] 生成标准版...
[2/3] 生成快节奏版...
[3/3] 生成情感版...

✓ 生成了 3 个最终版本
  - standard: 质量分 8.5/10
  - fast_paced: 质量分 8.0/10
  - emotional: 质量分 9.0/10
```

---

### 阶段5: 人工选1个发布 ✋

**目的**: 最终发布前，人工选择最佳版本

**实现**:
```python
# 请求人工选择 (自动弹出Web选择界面)
published = pipeline.request_final_selection(final_versions)

if published:
    print(f"✓ 发布版本: {published.version_id}")
    print(f"  质量分: {published.quality_score:.1f}/10")
```

**选择界面**:
- 自动弹出浏览器
- 并排显示3个版本
- 显示参数和质量分
- 可预览视频
- 输入选择理由
- 提交后自动关闭

---

## 🚀 使用方式

### 方式1: 完整流程测试

```bash
cd ~/.openclaw/workspace/ai-short-drama-automator
python test_efficient_pipeline.py
```

### 方式2: 集成到主程序

```python
from src.efficient_pipeline import EfficientPipeline

# 创建流程
pipeline = EfficientPipeline(config={
    "output_dir": "output",
    "records_dir": "data/efficient_records"
})

# 开始会话
pipeline.start_session("重生复仇")

# 阶段1: 生成3个剧本，自动选最高分
selected_script = pipeline.generate_and_select_script(
    script_generator=script_gen,
    topic="重生复仇",
    style="情感"
)

# 阶段2: 生成角色，人工确认
characters = pipeline.generate_characters(char_gen, selected_script["content"])
if not pipeline.request_character_approval(characters):
    return  # 未通过，终止

# 阶段3: 生成分镜和视频
video_clips = pipeline.generate_storyboard_and_videos(
    storyboard_mgr,
    selected_script["content"],
    characters
)

# 阶段4: 生成3个最终版本
final_versions = pipeline.generate_final_versions(video_clips)

# 阶段5: 人工选择发布版本
published = pipeline.request_final_selection(final_versions)

# 保存会话
pipeline.save_session()
```

---

## 📂 相关文件

### 核心代码
- `src/efficient_pipeline.py` - 高效流程管理器
- `src/unified_review_system.py` - 统一审查系统 (角色确认)
- `src/web_human_selector.py` - Web选择器 (版本选择)

### 测试文件
- `test_efficient_pipeline.py` - 完整流程测试

### 数据记录
- `data/efficient_records/` - 会话记录保存目录

---

## 💡 核心优势

### 1. 减少人工介入
- **旧流程**: 4次人工审查 (剧本、角色、视频、最终)
- **新流程**: 2次人工确认 (角色、发布)
- **效率提升**: 50%

### 2. 前期AI筛选
- 生成3个剧本，AI自动评分
- 只保留最高分，无需人工对比
- 节省时间，提高质量

### 3. 后期多版本输出
- AI自动生成3个风格版本
- 人工只需选择，不需要重新生成
- 灵活性高，满足不同需求

### 4. 关键节点把关
- 角色母版: 影响整个短剧，必须人工确认
- 最终发布: 代表作品质量，必须人工选择
- 其他环节: AI自动化处理

---

## 🔄 完整流程图

```
用户输入主题
    ↓
┌─────────────────────────────────┐
│ 阶段1: 剧本生成 (AI自动)        │
│ - 生成3个剧本                   │
│ - AI评分 (Hook/剧情/情绪)       │
│ - 自动选择最高分                │
└─────────────────────────────────┘
    ↓
┌─────────────────────────────────┐
│ 阶段2: 角色母版 (人工确认) ✋   │
│ - 生成角色形象                  │
│ - 🌐 自动弹出审查界面           │
│ - 👤 人工确认: 通过/不通过      │
└─────────────────────────────────┘
    ↓
┌─────────────────────────────────┐
│ 阶段3: 分镜和视频 (AI自动)      │
│ - 生成分镜                      │
│ - 生成视频片段                  │
└─────────────────────────────────┘
    ↓
┌─────────────────────────────────┐
│ 阶段4: 最终版本 (AI自动)        │
│ - AI质量检测                    │
│ - 生成3个风格版本:              │
│   * 标准版 (平衡)               │
│   * 快节奏版 (激烈)             │
│   * 情感版 (柔和)               │
└─────────────────────────────────┘
    ↓
┌─────────────────────────────────┐
│ 阶段5: 发布选择 (人工选择) ✋   │
│ - 🌐 自动弹出选择界面           │
│ - 👤 人工选择1个版本发布        │
│ - 输入选择理由                  │
└─────────────────────────────────┘
    ↓
完成！🎉
```

---

## 📊 数据记录

每个会话都会保存完整记录:

```json
{
  "session_id": "重生复仇_20260305_143000",
  "topic": "重生复仇",
  "script_candidates": [
    {
      "script_id": "script_1",
      "score": 7.2,
      "dimensions": {
        "hook_strength": 7.0,
        "plot_structure": 7.5,
        "emotion_rhythm": 7.0
      }
    },
    {
      "script_id": "script_2",
      "score": 8.5,
      "dimensions": {
        "hook_strength": 9.0,
        "plot_structure": 8.5,
        "emotion_rhythm": 8.0
      }
    },
    {
      "script_id": "script_3",
      "score": 6.8,
      "dimensions": {
        "hook_strength": 6.5,
        "plot_structure": 7.0,
        "emotion_rhythm": 7.0
      }
    }
  ],
  "selected_script": {
    "script_id": "script_2",
    "score": 8.5
  },
  "characters": [...],
  "character_approved": true,
  "final_versions": [
    {
      "version_id": "standard",
      "quality_score": 8.5,
      "params": {...}
    },
    {
      "version_id": "fast_paced",
      "quality_score": 8.0,
      "params": {...}
    },
    {
      "version_id": "emotional",
      "quality_score": 9.0,
      "params": {...},
      "selected": true,
      "selection_reason": "情感版节奏更适合目标受众"
    }
  ],
  "published_version": {
    "version_id": "emotional",
    "video_path": "output/final/emotional.mp4"
  },
  "created_at": "2026-03-05T14:30:00",
  "completed_at": "2026-03-05T14:45:00"
}
```

---

## 🎉 总结

**新流程的核心价值**:

1. ✅ **更高效**: 人工介入从4次减少到2次
2. ✅ **更智能**: AI自动评分和质量检测
3. ✅ **更灵活**: 后期输出3个版本供选择
4. ✅ **更聚焦**: 人工只在关键节点把关
5. ✅ **更完整**: 记录所有决策数据

**适用场景**:
- 批量生产短剧内容
- 需要快速迭代
- 有明确的质量标准
- 希望减少人工成本

**与旧流程的兼容**:
- 可以随时切换回旧流程 (8.5严格标准 + 实验模式)
- 两套流程可以并存
- 根据项目需求选择合适的流程

---

**更新时间**: 2026-03-05

**测试命令**: `python test_efficient_pipeline.py`
