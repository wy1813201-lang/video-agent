# FEATURES.md - AI 短剧自动化工作流

## 项目概览

`ai-short-drama-automator` 是一个端到端的 AI 短剧视频生成系统，从剧本创作到最终视频合成全流程自动化，同时保留人工审批和质量把控节点。

---

## 完整工作流

```
剧本生成 → [审批] → 提示词生成 → [审批] → 图像生成 → [每4张审批] → 视频生成 → 合成
              ↑ 质量检测 + 重试贯穿全程
```

### 阶段详情

| 阶段 | 进度 | 说明 |
|------|------|------|
| 剧本生成 | 0–15% | LLM 生成多集剧本，支持情感/悬疑/搞笑/科幻风格 |
| 提示词生成 | 15–30% | 解析剧本场景，生成图像提示词，注入角色特征 |
| 图像生成 | 30–55% | 逐场景生成图像，每4张设审批点，失败自动重试 |
| 视频生成 | 55–90% | 逐帧生成视频片段，质量检测 + 自动重试 |
| 视频合成 | 90–100% | FFmpeg 合并所有片段为最终视频 |

---

## 核心模块

### `workflow_manager.py` - 工作流管理器

**审批点机制**
- 剧本生成后：人工审批，支持附带反馈重新生成
- 提示词生成后：人工审批
- 图像生成中：每完成 4 张触发一次审批
- 审批超时（默认 300 秒）自动继续

**质量检测回调**
```python
def my_quality_check(item_type: str, item_data) -> QualityResult:
    # item_type: 'image' | 'video' | 'script' | 'prompt'
    # 返回 QualityResult(passed, score, issues, suggestions)
    ...

manager = WorkflowManager(quality_callback=my_quality_check)
```

**重新生成机制**
- 质量分数低于阈值（默认 0.6）自动触发重试
- 最多重试 3 次（`MAX_REGEN_ATTEMPTS`）
- 超过上限使用最后一次结果并告警
- 追踪每个 item 的重试次数（`state.regen_counts`）

**状态查询**
```python
status = manager.get_status()
# 包含: stage, progress, quality_summary, regen_counts
```

---

### `character_consistency.py` - 角色一致性模块

**角色特征数据结构**
```python
@dataclass
class CharacterTrait:
    name: str          # 角色名
    appearance: str    # 外貌（发型、肤色、五官）
    outfit: str        # 服装
    personality: str   # 性格
    age_range: str     # 年龄段
    gender: str        # 性别
    extra_tags: List[str]  # 额外提示词
```

内置模板：女主、男主、妈妈、爸爸、反派

**角色提取器**
```python
extractor = CharacterExtractor()
characters = extractor.extract_characters(script_text)
# 自动识别剧本中出现的角色，返回 {角色名: CharacterTrait}
```

**提示词增强器**
```python
enhancer = PromptEnhancer(characters)
enhanced = enhancer.enhance(base_prompt, scene_text)
# 自动将角色特征注入提示词，确保跨场景外观一致
```

批量处理：
```python
enhanced_list = enhancer.enhance_batch(prompts, scene_texts)
```

---

### `script_generator.py` - 剧本生成器

支持多种 LLM 后端：
- 自定义 Opus 端点（优先）
- OpenAI GPT-4
- Anthropic Claude
- 内置模板（离线 fallback）

---

### `prompt_builder.py` - 提示词生成器

- 解析剧本场景结构
- 映射风格/情绪关键词
- 支持 Midjourney / Stable Diffusion / DALL-E / 可灵 格式输出

---

## 配置

`config/api_keys.json` 管理所有 API 密钥：

```json
{
  "script": { "custom_opus": { "enabled": true, "api_key": "..." } },
  "image":  { "midjourney":  { "enabled": false } },
  "video":  { "kling":       { "enabled": false },
              "google_veo":  { "enabled": true, "api_key": "..." } }
}
```

---

## 快速上手

```python
from src.workflow_manager import WorkflowManager
from src.character_consistency import CharacterExtractor, PromptEnhancer

# 1. 初始化工作流（可注入自定义质量检测）
manager = WorkflowManager(
    notify_callback=lambda msg: print(msg),
    quality_callback=my_quality_fn   # 可选
)

# 2. 运行
import asyncio
asyncio.run(manager.run_workflow(config))

# 3. 审批（在另一个协程/线程中调用）
manager.approve()
# 或拒绝并附反馈
manager.reject("女主发型需要改成短发")
```

---

## 可扩展点

- `generate_image` / `generate_video`：接入任意图像/视频 API
- `quality_callback`：接入视觉评估模型（如 CLIP、自定义打分器）
- `CharacterExtractor.update_character`：运行时动态修改角色设定
- `PromptOptimizer`：针对不同平台输出格式化提示词
