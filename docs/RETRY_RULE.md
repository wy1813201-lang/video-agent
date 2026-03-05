# 🔄 API 调用重试规则

## 规则

**每次 API 调用失败时，最多重试 3 次，如仍失败则结束调用并汇报问题。**

---

## 具体规则

| 情况 | 处理方式 |
|------|----------|
| 第1次调用失败 | 重试（+1） |
| 第2次调用失败 | 重试（+1） |
| 第3次调用失败 | **结束调用**，汇报问题 |
| 成功 | 继续下一步 |

---

## 适用场景

- ✦ 图片生成 API (CoZex)
- ✦ 视频生成 API (Jimeng/可灵)
- ✦ 剧本生成 API (Gemini/MiniMax/Opus)
- ✦ 其他外部 API 调用

---

## 汇报格式

当重试 3 次都失败时，应汇报：

```
❌ [API名称] 调用失败
   - 错误信息: xxx
   - 已重试: 3次
   - 建议: 检查API密钥/网络/配额
```

---

## 代码示例

```python
def call_api_with_retry(func, max_retries=3):
    for attempt in range(max_retries):
        try:
            return func()
        except Exception as e:
            if attempt == max_retries - 1:
                print(f"❌ API调用失败，已重试{max_retries}次: {e}")
                raise
            print(f"⚠️ 第{attempt+1}次失败，重试中...")
            time.sleep(2)
```

---

*规则记录时间: 2026-03-05*
