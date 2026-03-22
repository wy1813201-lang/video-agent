# 高效流程原型总结（非默认主线）

这份文件保留，但定位得改正。

它描述的是 `src/efficient_pipeline.py` 这条**高效生产原型流**，不是当前 `video-agent` 的默认主线。短剧 5.0 默认主线请看：

- `README.md`
- `docs/FULL_PIPELINE.md`

---

## 1. 这份文档对应什么

对应代码：

- `src/efficient_pipeline.py`
- `test_efficient_pipeline.py`
- `EFFICIENT_PIPELINE_GUIDE.md`

它实现/声明的思路是：

```text
生成 3 个剧本
→ 自动评分
→ 只保留最高分
→ 生成角色母版
→ 人工确认一次
→ 生成分镜与视频
→ 生成 3 个最终版本
→ 人工选择发布版本
```

这个思路本身没问题，甚至挺猛，但要说实话：
**它现在更像一个独立原型，而不是仓库默认生产入口。**

---

## 2. 原型流的核心能力

## 阶段 1：3 个剧本候选 + 自动评分

`EfficientPipeline.generate_and_select_script()`

评分维度：
- Hook 吸引力
- 剧情结构
- 情绪节奏

评分逻辑目前是代码内启发式规则，不是外部评审模型：
- `_check_hook_strength()`
- `_check_plot_structure()`
- `_check_emotion_rhythm()`

也就是说，当前“AI 自动评分”这个说法偏乐观，严格点说更接近：
**规则打分 + 自动选最高分。**

---

## 阶段 2：角色母版 + 人工确认

- `generate_characters()`
- `request_character_approval()`

这里会调用：
- `src.unified_review_system.UnifiedReviewSystem`

这部分思路和当前短剧 5.0 主线并不冲突，因为主线本来也强调角色母版先行。

---

## 阶段 3：分镜与视频生成

- `generate_storyboard_and_videos()`

但这里要实话实说：
- 它调用的是一个比较抽象的 `storyboard_manager.create_storyboard()`
- `_generate_video_for_shot()` 目前是占位实现，直接返回路径字符串

所以这一步在原型里更像“流程骨架”，不是与 `main.py` 等价的真实生产实现。

---

## 阶段 4：生成 3 个最终版本

- `generate_final_versions()`

输出版本：
- `standard`
- `fast_paced`
- `emotional`

对应质量检测：
- `_detect_quality()`

同样，这里的“质量检测”也是规则式估分，不是读取真实视频内容后的模型评审。

---

## 阶段 5：人工选择发布版本

- `request_final_selection()`

会调用：
- `src.web_human_selector.WebHumanSelector`

这部分是可落地的人机交互壳，但它依赖前面的视频版本确实存在。

---

## 3. 为什么它不是默认主线

原因很直接：

### 1) `cli.py` 没接它
`cli.py` 当前走的是 `WorkflowManager` 的 SOP 流。

### 2) `main.py` 没接它
`main.py` 当前主流程是 Story Bible / 角色母版 / 两步分镜 / 关键帧 / i2v / QA / 后期导演。

### 3) 核心环节仍有占位实现
原型里至少这些地方还不是与主线等价的真实落地：
- 单镜头视频生成
- 最终版本合成
- 质量检测

### 4) 它和主线存在职责重叠
仓库现在已经有：
- `MetaDirector`
- `WorkflowManager`
- `PostProductionDirector`
- `FeedbackLoop`

如果再把 `EfficientPipeline` 宣布成默认主线，文档会直接打架。

---

## 4. 现在该怎么理解它

正确定位：

- **它是并行高效流原型**
- **可以作为未来接入方向**
- **可以吸收其“少人工介入”的设计思想**
- **但当前不能当作仓库已经全面落地的主线事实**

最靠谱的说法是：

> `EfficientPipeline` 展示了一种更激进的生产流：前端自动选剧本，后端自动出多版本，中间只保留关键人工确认点。当前仓库已具备部分基础模块，但尚未把该原型完整并入默认入口。

---

## 5. 与短剧 5.0 主线的关系

### 已被主线吸收的思想

- 角色母版必须前置
- 人工节点尽量收缩到关键位置
- 质量评估要进入主流程

### 还没被主线完整吸收的部分

- 固定生成 3 个剧本候选并自动选优
- 固定输出 3 个最终版本让人工选择
- 用同一套 session record 统一串完整生产闭环

---

## 6. 当前诚实结论

### 已完成 / 已存在
- `src/efficient_pipeline.py` 文件存在
- 会话记录机制存在
- 角色审批 / 最终版本选择接口存在
- 原型测试文件与说明文档存在

### 尚未证明是主线已落地
- 未接入 `cli.py`
- 未接入 `main.py`
- 视频生成/合成/质量评估仍有占位性质
- 还没有成为仓库默认执行路径

---

## 7. 一句话总结

`NEW_PIPELINE_SUMMARY.md` 现在正确的定位不是“新主线已完成”，而是：

**高效生产流原型已搭出骨架，但短剧 5.0 默认主线仍然是 WorkflowManager/main.py 那条角色优先、关键帧驱动、i2v + QA + 反馈闭环的路线。**
