# 重试规则（按当前代码对齐）

旧版“三次失败就结束”太粗了，不符合现在仓库真实实现。

当前仓库实际有两层重试：

1. **底层 API 指数退避重试**：`src/retry_utils.py -> retry_async()`
2. **带质量门禁的重新生成**：`src/workflow_manager.py -> regenerate_with_retry()`

这两层不是一回事，别混写。

---

## 1. 底层 API 重试：`retry_async()`

对应文件：`src/retry_utils.py`

函数签名要点：

```python
async def retry_async(
    func,
    *,
    max_attempts=3,
    base_delay_sec=1.0,
    max_delay_sec=20.0,
    retry_exceptions=(Exception,),
    on_retry=None,
)
```

### 行为

- 默认最多尝试 `3` 次
- 使用**指数退避**，不是固定等 2 秒
- 退避时间计算：

```text
sleep = min(max_delay_sec, base_delay_sec * 2^(attempt - 1))
```

### 例子

如果：
- `max_attempts = 3`
- `base_delay_sec = 2.0`

那重试节奏就是：
- 第 1 次失败后：等 `2s`
- 第 2 次失败后：等 `4s`
- 第 3 次失败：直接抛错，不再重试

---

## 2. `main.py` 里的真实重试参数

`main.py` 会从 `config.yaml` 读取：

```yaml
pipeline:
  retry_max_attempts: 3
  retry_base_delay_sec: 2.0
```

也就是说，主线默认不是抽象的“最多 3 次”，而是：

- 最大尝试次数：`3`
- 初始退避：`2.0s`
- 第二次等待：`4.0s`
- 再失败就结束这次调用

---

## 3. 哪些地方已经接入了底层重试

### 关键帧生成

`main.py -> _generate_media_from_flow()` 里，Cozex 关键帧调用已经包了：

```python
image_result = await retry_async(...)
```

### 视频生成

`main.py -> _generate_video_for_shot()` 里，这两条都接了重试：

- `client.image_to_video(...)`
- `client.video_generation(...)`

也就是：
- i2v 调用会重试
- t2v fallback（若配置允许）也会重试

---

## 4. 上层“重新生成”规则：`regenerate_with_retry()`

对应文件：`src/workflow_manager.py`

这层不是简单的 API 重试，而是：

```text
generate → quality_check → 不过线则重新生成 → 再质检
```

默认规则：

- `MAX_REGEN_ATTEMPTS = 3`
- `QUALITY_THRESHOLD = 0.6`

### 触发条件

只要下面任一条件成立，就会继续重生：

- `quality.passed == False`
- `quality.score < 0.6`

### 结束条件

- 质量通过：立即返回
- 达到 3 次：返回最后一次结果，并告警

所以这里的“3 次”不是网络层意义的 retry，而是**内容层意义的重新生成**。

---

## 5. 视频阶段还有 QA 门禁

`main.py` 视频阶段除了 API 重试，还会做额外门禁：

### 图像前置检查
- `_quality_check_image()`
- 关键帧质量太低时，不适合走 i2v

### 视频结果检查
- `_quality_check_video()`
- 基于文件大小、时长、分辨率打轻量分

### 黑帧/低分门禁
- `_qa_video_gate()`
- 分数低于 `qa.min_video_score`
- 黑帧比例过高
- 视频缺失

如果 QA 没过，会被视为失败，进入 fallback 或抛错。

---

## 6. 当前实际策略总结

### A. 底层 API 调用失败

处理方式：

1. 指数退避
2. 最多 3 次
3. 仍失败则抛异常

### B. 内容生成成功但质量不过线

处理方式：

1. 记录质量问题
2. 重新生成
3. 最多 3 轮
4. 超过上限保留最后结果并告警

### C. i2v 失败时

处理方式取决于配置：

- 若 `fallback_to_t2v: true` → 尝试 t2v
- 若 `fallback_to_t2v: false` → 直接失败

而当前 `config.yaml` 默认是：

```yaml
video_generation:
  primary_method: "i2v"
  fallback_to_t2v: false
```

所以短剧 5.0 默认口径是：
**优先且基本只跑 i2v，不自动退回 t2v。**

---

## 7. 推荐汇报格式

当某次调用最终失败时，建议按下面格式记录，而不是只说“失败了”：

```text
❌ [阶段/服务] 调用失败
- item: shot_03
- attempts: 3
- retry_policy: exponential backoff (2s, 4s)
- last_error: <具体错误>
- qa_gate: <如有，填写 qa_score_low / qa_black_frames / missing_keyframe_url>
- next_action: <人工复核 / 降级 / 修配置>
```

---

## 8. 一句话总结

当前仓库真实重试策略不是一句“失败重试三次”就完了，而是：

**底层 API 用指数退避，上层内容生成再叠一层质量门禁和重新生成。**
