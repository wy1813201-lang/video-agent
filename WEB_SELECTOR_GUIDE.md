# Web 人工选择界面使用指南

## 📌 概述

Web 人工选择界面提供了一个可视化的方式来选择最佳的剧本版本，替代了原来的命令行界面。

## 🎨 界面特点

### 1. 美观的卡片式布局
- 渐变紫色背景
- 响应式设计，自动适配屏幕大小
- 卡片悬停效果
- 选中状态带有 ✓ 标记

### 2. 清晰的参数展示
每个版本卡片显示：
- **版本标题**：版本 1、版本 2
- **版本名称**：快节奏版、标准版
- **参数网格**：
  - 冲突时间（立即冲突/早期冲突）
  - 反转次数（2-3个）
  - 情绪强度（极端情绪/高强度）
  - Hook风格（震惊式/悬念式）
- **内容预览**：显示前300字的剧本内容

### 3. 交互式选择
- 点击卡片选中版本
- 输入选择理由
- 确认提交或跳过选择

## 🚀 使用方式

### 方式 1：在真实流程中自动启动

当运行完整生成流程时，如果评分低于 8.5，会自动启动 Web 界面：

```bash
cd ~/.openclaw/workspace/ai-short-drama-automator
python main.py generate --topic "测试短剧" --style 情感 --episodes 1
```

**流程**：
1. Meta Director 评分 → 发现有维度 < 8.5
2. 触发实验模式 → 生成多个版本
3. 🌐 自动打开浏览器 → 显示 Web 选择界面
4. 你在浏览器中选择 → 输入理由 → 提交
5. 系统继续使用选中版本 → 生成分镜、视频

### 方式 2：单独测试 Web 界面

```bash
python test_web_selector.py
```

这会启动一个测试服务器，展示 Web 界面的样子。

### 方式 3：查看静态预览

```bash
open web_selector_preview.html
```

这是一个静态预览，不需要启动服务器，可以看到界面的样子。

## 📂 相关文件

### 后端代码
- `src/web_human_selector.py` - Web 选择器实现
  - `WebHumanSelector` 类：提供 Flask 服务器
  - `select_best_script()` 方法：启动选择流程

### 前端界面
- `templates/selector.html` - HTML 模板
  - 响应式布局
  - JavaScript 交互逻辑
  - 实时数据加载

### 测试文件
- `test_web_selector.py` - Web 界面测试脚本
- `generate_web_preview.py` - 生成静态预览
- `web_selector_preview.html` - 静态预览文件

## 🔧 技术实现

### 后端（Flask）
```python
from src.web_human_selector import WebHumanSelector

selector = WebHumanSelector(port=5000)
selected = selector.select_best_script(versions)

# selected 包含:
# - version_id: 选中的版本ID
# - reason: 选择理由
# - content: 选中的剧本内容
```

### 前端（HTML + JavaScript）
- 使用 Fetch API 获取版本数据
- 动态渲染版本卡片
- 提交选择到后端
- 等待用户操作完成

### 通信流程
```
浏览器                    Flask 服务器
  |                           |
  |-- GET /api/versions -->   |
  |<-- 返回版本数据 --------   |
  |                           |
  |-- POST /api/select -->    |
  |   (version_id + reason)   |
  |<-- 确认成功 ------------   |
  |                           |
  |   (关闭浏览器)            |
  |                           |
  |                      返回选择结果
```

## 🎯 与 CLI 版本对比

### CLI 版本（原版）
```
============================================================
🧪 实验版本选择
============================================================

【版本 1】script_ep01_v1
参数: 快节奏版
...

请选择最佳版本 (1-2) 或输入 0 跳过: 1
请说明选择理由: 开头更有冲击力
```

**优点**：简单、无需浏览器
**缺点**：不够直观、难以对比

### Web 版本（新版）
- ✅ 可视化卡片布局
- ✅ 并排对比所有版本
- ✅ 实时预览内容
- ✅ 美观的交互界面
- ✅ 更容易做出决策

## 💡 使用建议

### 1. 首次使用
建议先打开静态预览熟悉界面：
```bash
open web_selector_preview.html
```

### 2. 实际使用
在 `main.py` 中，系统会自动选择使用 Web 界面（如果 Flask 可用）：
```python
# 优先使用 Web 界面
if WebHumanSelector:
    selector = WebHumanSelector()
    selected = selector.select_best_script(versions)
else:
    # 降级到 CLI 界面
    selected = HumanSelector.select_best_script(versions)
```

### 3. 选择理由的重要性
选择理由会被记录到生产记录中，用于：
- 数据分析：了解什么样的内容更受欢迎
- AI 学习：未来训练模型时的标注数据
- 团队协作：其他人可以看到你的选择依据

**好的理由示例**：
- ✅ "开头更有冲击力，立即抓住观众注意力"
- ✅ "情绪递进更自然，符合短剧节奏"
- ✅ "悬念设置更好，能引发观众好奇心"

**不好的理由示例**：
- ❌ "感觉好"
- ❌ "随便选的"
- ❌ "不知道"

## 🔮 未来扩展

### 短期可实现
- [ ] 添加版本评分功能（让用户给每个版本打分）
- [ ] 显示 Meta Director 的评分详情
- [ ] 支持多人投票选择
- [ ] 添加版本对比功能（并排显示差异）

### 中期计划
- [ ] 集成视频预览（如果有视频版本）
- [ ] 添加历史选择记录查看
- [ ] 支持自定义参数调整
- [ ] 实时生成新版本

### 长期愿景
- [ ] AI 推荐最佳版本
- [ ] 基于历史数据预测平台表现
- [ ] 自动 A/B 测试
- [ ] 完全自动化决策

## 📊 数据记录

选择结果会被保存到 `data/production_records/*.json`：

```json
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
```

## 🎉 总结

Web 人工选择界面提供了一个**直观、美观、易用**的方式来选择最佳版本，大大提升了人工评选的体验。

**核心价值**：
1. 可视化对比 → 更容易做出决策
2. 美观的界面 → 提升使用体验
3. 记录选择理由 → 积累数据资产
4. 灵活扩展 → 未来可以添加更多功能

现在你有了一个完整的 **8.5 标准 + Web 人工评选** 系统！
