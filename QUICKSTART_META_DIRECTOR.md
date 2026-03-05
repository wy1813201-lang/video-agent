# Meta Director 快速开始

## 🚀 快速测试

### 1. 运行测试脚本

```bash
cd ~/.openclaw/workspace/ai-short-drama-automator
python test_meta_director.py
```

这将测试所有 Meta Director 功能：
- ✅ 剧本审核（高质量 vs 低质量）
- ✅ 分镜审核
- ✅ 实验参数生成
- ✅ 人工选择器演示
- ✅ 生产记录保存

### 2. 启用 Meta Director

编辑 `config.yaml`：

```yaml
meta_director:
  enabled: true  # 改为 true
```

### 3. 运行完整流程

```bash
python main.py generate --topic "重生千金复仇记" --style 情感 --episodes 1
```

## 📊 预期输出

### 剧本审核示例

```
📝 第 1 集
   ✓ 剧本生成完成 (2847 字)

   🎯 [Meta Director] 剧本审核
      决策: approve
      评分: 8.5/10
      理由: 质量良好，总分8.5/10
```

### 触发实验模式

如果评分在 6.0-8.0 之间：

```
   🎯 [Meta Director] 剧本审核
      决策: experiment
      评分: 6.8/10
      理由: Hook吸引力不足(6.5/10)

      🧪 触发实验模式，生成多个版本

   🧪 [实验引擎] 开始生成剧本变体

      [版本 1] 生成中...
      参数: 快节奏版
      ✓ 生成成功 (2654 字)

      [版本 2] 生成中...
      参数: 标准版
      ✓ 生成成功 (2789 字)

============================================================
🧪 实验版本选择
============================================================

【版本 1】script_ep01_v1
参数: 快节奏版
特点:
  - 冲突时间: immediate
  - 反转次数: 3
  - 情绪强度: extreme
  - Hook风格: shock

预览:
第1集：重生复仇

场景1: [震惊开场]
女主: （尖叫）不！这不可能！
旁白: 她死了，又活了...
...

【版本 2】script_ep01_v2
参数: 标准版
特点:
  - 冲突时间: early
  - 反转次数: 2
  - 情绪强度: high
  - Hook风格: mystery

预览:
第1集：重生归来

场景1: [悬念开场]
女主: （疑惑）这是...哪里？
...

请选择最佳版本 (1-2) 或输入 0 跳过: 1
请说明选择理由: 开头更有冲击力，情绪更强烈

      ✓ 已选择: script_ep01_v1
      理由: 开头更有冲击力，情绪更强烈
```

### 分镜审核示例

```
   ✓ 两步分镜生成: 12 个镜头 → output/storyboards/storyboard_flow_ep01.json

   🎯 [Meta Director] 分镜审核
      决策: approve
      评分: 8.2/10
      理由: 质量良好，总分8.2/10
```

### 生产记录

```
📊 Meta Director 生产记录已保存
```

查看记录：

```bash
cat data/production_records/重生千金复仇记_ep01_*.json
```

输出示例：

```json
{
  "record_id": "重生千金复仇记_ep01_20260304_143022",
  "topic": "重生千金复仇记",
  "episode_num": 1,
  "decisions": [
    {
      "decision_type": "experiment",
      "score": {
        "overall": 6.8,
        "hook_strength": 6.5,
        "plot_structure": 7.0,
        "emotion_rhythm": 7.0
      },
      "reason": "Hook吸引力不足(6.5/10)",
      "timestamp": "2026-03-04T14:30:22",
      "content_type": "script"
    },
    {
      "decision_type": "approve",
      "score": {
        "overall": 8.2,
        "shot_logic": 8.5
      },
      "reason": "质量良好，总分8.2/10",
      "timestamp": "2026-03-04T14:32:15",
      "content_type": "storyboard"
    }
  ],
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
      "selection_reason": "开头更有冲击力，情绪更强烈"
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
      "selected": false
    }
  ],
  "final_version_id": "script_ep01_v1",
  "platform_data": {},
  "created_at": "2026-03-04T14:30:00"
}
```

## 🎛️ 配置选项

### 调整评分标准

```yaml
meta_director:
  enabled: true
  min_score: 8.0  # 提高到 8.0，更严格
  enable_experiments: true
  experiment_count: 3  # 生成 3 个版本
```

### 禁用实验模式

```yaml
meta_director:
  enabled: true
  min_score: 7.0
  enable_experiments: false  # 只审核，不生成实验版本
```

## 📈 评分标准参考

### 剧本评分

| 维度 | 满分 | 说明 |
|------|------|------|
| Hook吸引力 | 10 | 开头100字内的冲突强度 |
| 剧情结构 | 10 | 场景数量、冲突、反转 |
| 情绪节奏 | 10 | 情绪类型多样性 |

**通过标准**：总分 ≥ 7.0

### 分镜评分

| 维度 | 满分 | 说明 |
|------|------|------|
| 镜头逻辑 | 10 | 镜头类型合理性 |
| 镜头数量 | 10 | 8-15个为最佳 |
| 角色一致性 | 10 | 角色描述完整性 |

**通过标准**：总分 ≥ 7.0

## 🔧 故障排除

### 问题1：Meta Director 未启用

**症状**：运行时没有看到审核信息

**解决**：
```bash
# 检查配置
grep -A 5 "meta_director:" config.yaml

# 确保 enabled: true
```

### 问题2：实验版本生成失败

**症状**：显示 "实验引擎未启用"

**原因**：可能是 API 配置问题

**解决**：
```bash
# 检查 API 配置
cat config/api_keys.json | grep -A 10 "script"
```

### 问题3：人工选择界面不显示

**症状**：自动使用第一个版本

**原因**：HumanSelector 导入失败

**解决**：
```bash
# 测试导入
python -c "from src.human_selector import HumanSelector; print('OK')"
```

## 📚 下一步

1. **积累数据**：运行多次生成，积累决策数据
2. **分析记录**：查看 `data/production_records/` 中的记录
3. **优化参数**：根据实际效果调整 `min_score` 和实验参数
4. **录入平台数据**：手动添加播放量等数据到记录中

## 💡 提示

- 第一次运行建议设置 `episodes: 1`，快速测试
- 实验模式会增加 API 调用成本，注意控制
- 生产记录可用于未来的数据分析和模型训练
- 人工选择的理由很重要，会用于未来的学习

## 🎯 成功标志

运行成功后，你应该看到：

✅ Meta Director 已启用
✅ 剧本审核完成（有评分）
✅ 分镜审核完成（有评分）
✅ 生产记录已保存
✅ 在 `data/production_records/` 中有 JSON 文件

恭喜！Meta Director 已成功集成到你的短剧生成系统中！
