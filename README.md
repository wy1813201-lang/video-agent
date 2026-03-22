# 🎬 video-agent

短剧 5.0 主线文档入口。当前仓库的可验证主线是：**角色优先 + 关键帧驱动 + i2v 视频生成 + 后期导演 + 质量审核/反馈闭环**。

> 先说结论：
> - `cli.py` = 面向 SOP 的分步入口。
> - `main.py` = 更完整的自动化编排器，负责故事圣经、角色母版、两步分镜、媒体生成、后期、任务续跑等。
> - `src/efficient_pipeline.py` = 单独存在的“高效生产流”原型，不是当前默认主线。

---

## 当前主线能力（短剧 5.0）

主线围绕 `src/workflow_manager.py` 的 `WorkflowManager` 与 `main.py` 的 `ShortDramaAutomator`。

### SOP 主线阶段

`WorkflowManager.Stage` 当前定义为：

1. 剧本生成 `SCRIPT`
2. 角色母版构建 `CHARACTER_MASTER`
3. 分镜拆解 `STORYBOARD`
4. 关键帧生成 `KEYFRAME`
5. 视频生成 `VIDEO_GEN`（主线默认 i2v）
6. 视频合成 `ASSEMBLY`
7. 质量审核 `QUALITY_AUDIT`
8. 反馈优化 `FEEDBACK_LOOP`

这就是现在要对齐的“短剧 5.0 主线”。不是旧 README 里那种“剧本→图像→视频→合成”四步简化版。

---

## 仓库里两个入口的关系

### 1) `cli.py`：SOP / 分步执行入口

适合手工跑阶段、局部调试、补跑某一步。

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

常用参数：

```bash
python cli.py --step all \
  --topic "重生千金复仇记" \
  --style 情感 \
  --episodes 3
```

如果已有角色母版：

```bash
python cli.py --step storyboard -c data/character_masters/xxx.json
```

### 2) `main.py`：完整自动化入口

适合按 `config.yaml` 驱动更完整的自动化流程：

- Story Bible 连续性
- Character Master 角色母版
- 两步分镜 `StoryboardFlowManager`
- 可选 Cozex 关键帧生成
- 可选 Jimeng i2v / t2v 生成
- QA 门禁
- PostProductionDirector 后期导演
- TaskStateManager 续跑

示例：

```bash
python main.py generate --topic "重生千金复仇记" --style 情感 --episodes 3
python main.py storyboard --script script.txt --episode 1 --title "重生千金复仇记"
python main.py compose --videos clip1.mp4 clip2.mp4 --bgm music.mp3
```

---

## 配置重点

主配置在 `config.yaml`，API 密钥在 `config/api_keys.json`。

### `config.yaml` 里当前和 5.0 主线直接相关的开关

- `storyboard.use_two_step_flow: true`
- `storyboard.auto_generate_media: false`
- `storyboard.enable_post_production_director: true`
- `video_generation.primary_method: "i2v"`
- `video_generation.fallback_to_t2v: false`
- `pipeline.retry_max_attempts: 3`
- `pipeline.qa.enabled: true`
- `story_bible.enabled: true`

这几个配置基本说明了当前默认姿势：
**先角色和分镜，再关键帧，再强制 i2v，最后走 QA 和后期。**

---

## 安装

```bash
git clone https://github.com/wy1813201-lang/video-agent.git
cd video-agent
pip install -r requirements.txt
```

系统依赖：

```bash
# macOS
brew install ffmpeg

# Ubuntu / Debian
sudo apt install ffmpeg
```

---

## API 配置

编辑 `config/api_keys.json`。当前仓库代码实际会读取这些大类：

- `script.*`：剧本生成
- `image.cozex`：关键帧图片
- `video.jimeng`：视频生成
- `character_consistency.*`：角色一致性 / IP-Adapter 相关配置

最小示例：

```json
{
  "script": {
    "custom_opus": {
      "enabled": true,
      "base_url": "http://your-endpoint:3000/v1",
      "api_key": "your-api-key"
    }
  },
  "image": {
    "cozex": {
      "enabled": true,
      "base_url": "https://api.cozex.cn/v1",
      "api_key": "your-api-key"
    }
  },
  "video": {
    "jimeng": {
      "enabled": true,
      "access_key": "AK...",
      "secret_key": "SK...",
      "base_url": "https://visual.volcengineapi.com"
    }
  }
}
```

---

## 推荐使用顺序

### 先验证 SOP 主线

```bash
python cli.py --step script
python cli.py --step character
python cli.py --step storyboard
```

### 再打开自动媒体生成

需要你在 `config.yaml` 中按需启用：

- `storyboard.auto_generate_media: true`
- `storyboard.auto_compose_episode: true`
- `storyboard.auto_compose_series: true`（可选）

### 最后再跑 `main.py generate`

因为真正的 API 调用、重试、QA、后期导演都在这里串起来。

---

## 项目结构（按当前主线重排理解）

```text
video-agent/
├── README.md
├── NEW_PIPELINE_SUMMARY.md          # 高效流程原型说明（非主线）
├── docs/
│   ├── FULL_PIPELINE.md             # 短剧 5.0 主线全流程
│   └── RETRY_RULE.md                # 实际重试策略
├── cli.py                           # SOP 分步入口
├── main.py                          # 完整自动化入口
├── config.yaml                      # 主配置
├── config/api_keys.json             # API 配置（需自行创建/填写）
├── src/
│   ├── workflow_manager.py          # 5.0 SOP 主线状态机
│   ├── character_master.py          # 角色母版
│   ├── story_bible.py               # 系列连续性
│   ├── storyboard_flow.py           # 两步分镜
│   ├── retry_utils.py               # 指数退避重试
│   ├── post_production_director.py  # 后期导演
│   ├── feedback_loop.py             # 反馈闭环
│   └── ...
└── output/
```

---

## 现状说明

### 已在主线中的能力

- 角色母版 / Story Bible / 两步分镜已接进主流程
- `retry_async` 指数退避已用于关键帧和视频生成
- 视频 QA 门禁已接入 `main.py`
- `FEEDBACK_LOOP` 已在 `WorkflowManager.run_workflow()` 中接入

### 仍然不是默认主线的部分

- `src/efficient_pipeline.py` 虽然可用，但更像独立原型
- “一次生成 3 个剧本 + 自动打分 + 只保留最高分 + 输出 3 个最终版本”这套逻辑**没有成为 `cli.py`/`main.py` 默认入口**

所以别把那个原型文档当成当前仓库主线。那会把人带沟里。

---

## 相关文档

- `docs/FULL_PIPELINE.md`：短剧 5.0 主线全流程
- `docs/RETRY_RULE.md`：真实重试规则
- `NEW_PIPELINE_SUMMARY.md`：高效流程原型现状
- `EFFICIENT_PIPELINE_GUIDE.md`：原型详细说明

---

## 一句话总结

这个仓库现在的主线，不是旧四步流，也不是高效原型流；
**真正该对齐的是“角色优先 + 关键帧驱动 + i2v + QA/反馈闭环”的短剧 5.0 SOP。**
