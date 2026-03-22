# 短剧 5.0 主线全流程（video-agent）

这份文档只描述**当前仓库里能对得上代码的主线**。

结论先放前面：当前主线不是旧的 8 宫格宣传图，也不是 `NEW_PIPELINE_SUMMARY.md` 里的高效原型，而是下面这条线：

```text
剧本生成
→ 角色母版
→ 两步分镜
→ 关键帧生成
→ i2v 视频生成
→ 单集/全集合成
→ 后期导演
→ 质量审核
→ 反馈闭环
```

涉及的核心文件：

- `cli.py`
- `main.py`
- `config.yaml`
- `src/workflow_manager.py`
- `src/storyboard_flow.py`
- `src/post_production_director.py`
- `src/retry_utils.py`
- `src/feedback_loop.py`

---

## 1. 两个执行入口

### A. SOP 入口：`cli.py`

`cli.py` 对应的是“角色优先 + 关键帧驱动”的阶段式工作流。

支持步骤：

```bash
python cli.py --step all
python cli.py --step script
python cli.py --step character
python cli.py --step storyboard
python cli.py --step keyframe
python cli.py --step video
python cli.py --step assemble
python cli.py --step audit
```

适合：
- 分步调试
- 手动补跑
- 验证每个阶段是否打通

### B. 自动化入口：`main.py`

`main.py` 是更重的编排器，负责把这些模块真正串起来：

- Story Bible
- Character Master
- 两步分镜
- Cozex 关键帧
- Jimeng 视频生成
- QA 门禁
- PostProductionDirector
- TaskStateManager 续跑

适合：
- 跑真实生产流程
- 处理多集连续性
- 自动化媒体生成与后期

---

## 2. 配置决定主线姿势

`config.yaml` 当前默认值已经很明确：

```yaml
storyboard:
  use_two_step_flow: true
  auto_generate_media: false
  enable_post_production_director: true

video_generation:
  primary_method: "i2v"
  fallback_to_t2v: false

pipeline:
  retry_max_attempts: 3
  retry_base_delay_sec: 2.0
  qa:
    enabled: true
    min_video_score: 0.6
```

这说明默认主线是：

1. 两步分镜打开
2. 视频生成默认强制 i2v
3. 默认有自动 QA
4. 默认有后期导演
5. 媒体自动生成默认关闭，需要按环境手动打开

---

## 3. 阶段说明

## 阶段 1：剧本生成

对应：
- `src/workflow_manager.py -> generate_script()`
- `main.py -> ScriptGenerator.generate_episode()`

能力：
- 按主题、风格、集数生成剧本
- 支持多集串联
- 可结合 Story Bible 补充上下文

典型调用：

```bash
python cli.py --step script --topic "重生千金复仇记" --style 情感 --episodes 3
```

在 `WorkflowManager.run_workflow()` 中，剧本后会先做一次质量检查，再进入人工审批。

---

## 阶段 2：角色母版

对应：
- `src/character_master.py`
- `src/character_description_generator.py`
- `main.py -> _create_character_masters()`

作用：
- 从剧本抽取主角/配角
- 生成角色母版锚点信息
- 为后续关键帧和视频一致性提供基础

这里是 5.0 主线跟旧版本最大的差别之一：
**不是先瞎生图，再补一致性；而是先定角色母版。**

---

## 阶段 3：两步分镜

对应：
- `src/storyboard_flow.py`
- `src/storyboard_manager.py`
- `main.py` 中的 `StoryboardFlowManager`

输出重点：
- `keyframe_image_prompt`
- `motion_prompt`
- `video_prompt`
- shot 级别的连续性信息

这一步的产物通常落在：

```text
output/storyboards/storyboard_flow_epXX.json
```

主线逻辑是：
- 先拆镜头
- 每个镜头先定关键帧静态画面
- 再定运动描述
- 为 i2v 做准备

---

## 阶段 4：关键帧生成

对应：
- `main.py -> _generate_media_from_flow()` 中 STEP1
- `src/cozex_client.py`
- `WorkflowManager.generate_all_keyframes()`

默认服务：
- `image.cozex`

行为：
- 根据 `shot.keyframe_image_prompt` 生成关键帧
- 结果写回 `shot.keyframe_image_path / url`
- 后续视频阶段优先复用关键帧

在 `WorkflowManager` 的 SOP 流程里，关键帧阶段会穿插审批点：
- 每 4 张一次
- 全部完成后再总审一次

---

## 阶段 5：视频生成（主线默认 i2v）

对应：
- `main.py -> _generate_video_for_shot()`
- `src/jimeng_client.py`
- `src/retry_utils.py`

关键规则：

- `config.yaml` 默认 `primary_method: i2v`
- 默认 `fallback_to_t2v: false`
- 也就是说，短剧 5.0 主线默认是**关键帧驱动的视频生成**

实际决策逻辑：

1. 先检查关键帧质量 `_quality_check_image()`
2. 关键帧可用时走 `image_to_video()`
3. 若配置允许，才 fallback 到 `video_generation()` 的 t2v
4. 生成结果再过视频质量检查 `_quality_check_video()`
5. 若启用 QA，再过 `_qa_video_gate()`

也就是说，代码不是“无脑调视频 API”，而是：

```text
关键帧质量判断 → i2v 尝试 → 视频质量判断 → QA 门禁 → 必要时重试/回退
```

---

## 阶段 6：合成

对应：
- `src/video_composer.py`
- `main.py -> _compose_episode_if_needed()`
- `main.py -> _compose_series_if_needed()`

支持：
- 单集片段拼接
- 全集拼接
- 过渡转场
- BGM / voiceover
- 字幕烧录（如果字幕已经生成）

入口示例：

```bash
python main.py compose --videos clip1.mp4 clip2.mp4 --bgm music.mp3
```

---

## 阶段 7：后期导演

对应：
- `src/post_production_director.py`
- `main.py -> _run_post_production_if_needed()`

默认由 `config.yaml` 打开：

```yaml
storyboard:
  enable_post_production_director: true
```

它不是独立于主线外的彩蛋，而是当前主线的一部分。

主要负责：
- 时间线规划
- 配音计划
- 音乐计划
- 最终成片路径输出

前提：
- 有 `storyboard_flow_path`
- 有视频片段

缺一个都不会执行。

---

## 阶段 8：质量审核 + 反馈闭环

对应：
- `WorkflowManager.run_sop_quality_audit()`
- `WorkflowManager.run_feedback_optimization()`
- `src/feedback_loop.py`

`WorkflowManager.Stage` 里已经有：
- `QUALITY_AUDIT`
- `FEEDBACK_LOOP`

所以短剧 5.0 主线不是“生成完就结束”，而是有一层闭环：

1. 先做 SOP 合规审计
2. 再做视频质量评估
3. 如果发现问题，自动应用优化动作
4. 必要时执行重做 `_execute_regen()`
5. 最多限制闭环次数，避免无限循环

这部分是现在仓库里最接近“生产闭环”的东西。

---

## 4. 重试、QA、审批分别在哪

### 重试
- `src/retry_utils.py`
- `WorkflowManager.regenerate_with_retry()`
- `main.py` 中关键帧 / i2v / t2v 调用

### QA
- `_quality_check_image()`
- `_quality_check_video()`
- `_qa_video_gate()`
- `run_sop_quality_audit()`
- `run_feedback_optimization()`

### 审批
- `WorkflowManager.wait_for_approval()`
- `main.py -> _wait_for_review()`
- 角色母版与关键帧阶段都可能卡审批

---

## 5. 当前主线与高效原型的边界

`src/efficient_pipeline.py` 确实存在，但它描述的是另一套思路：

- 一次生成 3 个剧本并自动打分
- 只保留最高分
- 直接输出 3 个最终版本供人工挑选

这套逻辑目前：
- 有代码
- 有测试/说明文档
- 但**不是 `cli.py` 或 `main.py` 的默认入口**

所以在仓库主线文档里，最多把它当“并行原型/实验流”，不能当默认事实来写。

---

## 6. 推荐落地顺序

如果你要按当前主线真跑，建议顺序是：

### 第一步：先验证前半段

```bash
python cli.py --step script
python cli.py --step character
python cli.py --step storyboard
```

### 第二步：验证关键帧

```bash
python cli.py --step keyframe
```

### 第三步：确认 `config.yaml` 后开启自动媒体生成

把这些改成你需要的值：

```yaml
storyboard:
  auto_generate_media: true
  auto_compose_episode: true
```

### 第四步：跑完整自动化

```bash
python main.py generate --topic "重生千金复仇记" --style 情感 --episodes 3
```

---

## 7. 一句话总结

当前 `video-agent` 的短剧 5.0 主线，核心不是“多版本自动选优”，而是：

**角色先定住，分镜拆清楚，关键帧先落地，再用 i2v 拉视频，最后靠 QA + 后期 + 反馈闭环把成片收口。**
