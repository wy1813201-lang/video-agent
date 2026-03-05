# 🎬 AI 短剧自动生成器 - 完整流程文档

## 项目位置
```
~/.openclaw/workspace/ai-short-drama-automator/
```

---

## 📋 完整工作流程

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        AI 短剧生成完整流程                              │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    │
│  │ 1. 市场   │───▶│ 2. 剧本   │───▶│ 3. 分镜   │───▶│ 4. 图片   │    │
│  │ 调研     │    │ 生成      │    │ 生成      │    │ 生成      │    │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘    │
│       │              │              │              │              │
│       ▼              ▼              ▼              ▼              │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    │
│  │ 热门网文  │    │ Gemini   │    │ 分镜板   │    │ CoZex    │    │
│  │ 分析      │    │/Opus API │    │ 审批     │    │ API      │    │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘    │
│                                                                     │
│       │              │              │              │              │
│       ▼              ▼              ▼              ▼              │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    │
│  │ 5. 视频   │───▶│ 6. 合成   │───▶│ 7. 后期   │───▶│ 8. 输出   │    │
│  │ 生成      │    │ 视频      │    │ 制作      │    │ 最终成品  │    │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘    │
│       │              │              │              │              │
│       ▼              ▼              ▼              ▼              │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐                   │
│  │ Jimeng   │    │ FFmpeg   │    │ 飞书     │                   │
│  │/可灵 API │    │ 拼接     │    │ 通知     │                   │
│  └──────────┘    └──────────┘    └──────────┘                   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 🔧 详细步骤说明

### 第1步：市场调研 (MarketResearcher)
```
命令: 自动执行（generate 时调用）
```
- 分析热门网络小说趋势
- 提取热门题材、套路、人物设定
- 输出: `output/market_research/`

---

### 第2步：剧本生成 (ScriptGenerator)
```
命令: python main.py generate --topic "豪门虐恋" --style 情感 --episodes 1
```
**支持的方式：**
| 方式 | 配置 | 说明 |
|------|------|------|
| Gemini 网页 | `gemini_web.enabled: true` | 调用浏览器中的 Gemini |
| MiniMax API | `minimax.enabled: true` | 国内模型 API |
| Opus 代理 | `custom_opus.enabled: true` | Claude 模型 |

**问题解决：**
- ❌ 429 限流 → 切换 API 或等待
- ❌ 浏览器不可用 → 改用其他 API

---

### 第3步：分镜生成 (StoryboardGenerator)
```
命令: python main.py storyboard --script output/xxx.json --episode 1 --title "标题" --approve-all
```
- 将剧本拆分成镜头
- 生成每个镜头的描述、对白、构图
- 输出: `output/storyboards/storyboard_xxx.json`

---

### 第4步：图片生成 (ImageGenerator)
```
调用: CoZex API
```
**配置 (config/api_keys.json):**
```json
"cozex": {
    "enabled": true,
    "api_key": "sk-xxx",
    "image_model": "doubao-seedream-5-0-260128"
}
```

**命令（手动）:**
```bash
# 使用 2048x2048 (最少 3686400 像素)
curl -X POST "https://api.cozex.cn/v1/images/generations" \
  -H "Authorization: Bearer $API_KEY" \
  -d '{"model":"doubao-seedream-5-0-260128","prompt":"...","size":"2048x2048"}'
```

**输出位置:** `/Users/you/Desktop/ShortDrama/images/`

---

### 第5步：视频生成 (VideoGenerator)
```
调用: Jimeng/可灵 API
```
**配置:**
```json
"jimeng": {
    "enabled": true,
    "api_key": "xxx",
    "default_model": "jimeng_t2v_v30"
}
```

**支持模型:**
- `jimeng_t2v_v30` (720p)
- `jimeng_t2v_720p` (1080p)

---

### 第6步：视频合成 (VideoComposer)
```
命令: python main.py compose --videos clip1.mp4 clip2.mp4 --bgm music.mp3
```
- 使用 FFmpeg 拼接多个视频片段
- 添加背景音乐 (BGM)
- 添加转场效果
- 输出: `output/episode_xx_final.mp4`

---

### 第7步：后期制作 (PostProductionDirector)
- 字幕生成
- 音效添加
- 调色处理

---

### 第8步：输出与通知
- 飞书通知 → 发送视频到群
- 邮件通知 → 发送视频到邮箱

---

## 📁 项目结构

```
ai-short-drama-automator/
├── main.py                 # 主程序入口
├── config/
│   ├── api_keys.json       # API 配置
│   └── config.yaml         # 主配置
├── src/                    # 源代码
│   ├── script_generator.py     # 剧本生成
│   ├── storyboard_manager.py   # 分镜管理
│   ├── cozex_client.py        # 图片 API
│   ├── jimeng_client.py       # 视频 API
│   ├── video_composer.py      # 视频合成
│   ├── feishu_notifier.py     # 飞书通知
│   └── ...
├── output/
│   ├── storyboards/        # 分镜文件
│   ├── market_research/   # 市场调研
│   └── *.mp4              # 生成的视频
└── data/                  # 数据目录
```

---

## 🚀 快速开始

### 方式一：一键生成
```bash
cd ~/.openclaw/workspace/ai-short-drama-automator

# 生成短剧（含市场调研、剧本、分镜）
python main.py generate --topic "重生千金复仇记" --style 情感 --episodes 1

# 合成视频
python main.py compose --videos output/clip1.mp4 output/clip2.mp4 --bgm music.mp3
```

### 方式二：分步执行
```bash
# 1. 生成分镜
python main.py storyboard --script gemini_script.json --episode 1 --title "豪门虐恋"

# 2. 生成图片（手动调用 API）
python scripts/generate_images.py

# 3. 生成视频
python scripts/generate_videos.py

# 4. 合成
python main.py compose --videos clip1.mp4 clip2.mp4 --bgm BGM.mp3
```

---

## ⚠️ 常见问题

| 问题 | 原因 | 解决 |
|------|------|------|
| 剧本生成失败 | 浏览器不可用/API 限流 | 切换 API (gemini_web/minimax/custom_opus) |
| 图片生成失败 | size 像素不足 | 使用 2048x2048 |
| 视频生成失败 | API 密钥错误 | 检查 config/api_keys.json |
| 视频拼接失败 | 无音频流 | 使用 `v=1:a=0` 参数 |

---

## 📊 API 配置

| 服务 | 配置项 | 模型 |
|------|--------|------|
| 图片 | cozex | doubao-seedream-5-0-260128 |
| 视频 | jimeng | jimeng_t2v_v30 |
| 剧本 | minimax/custom_opus/gemini_web | - |

---

*最后更新: 2026-03-05*
