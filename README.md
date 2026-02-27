# 🎬 VideoAgent - AI 短剧自动生成系统

一个一键生成 AI 短剧的自动化工具，支持剧本→图像→视频→特效合成完整流程。

---

## 📦 安装

### 1. 克隆项目

```bash
git clone https://github.com/wy1813201-lang/video-agent.git
cd video-agent
```

### 2. 安装依赖

```bash
pip install -r requirements.txt

# 还需要 FFmpeg（用于视频合成）
# macOS:
brew install ffmpeg

# Ubuntu:
sudo apt install ffmpeg
```

### 3. 配置 API Key

编辑 `config/api_keys.json`：

```json
{
  "script": {
    "custom_opus": {
      "enabled": true,
      "base_url": "http://你的Opus地址:3000/v1",
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
      "access_key": "AKLT...",
      "secret_key": "Tm1K...",
      "base_url": "https://visual.volcengineapi.com"
    }
  }
}
```

---

## 🚀 使用

### 方式一：命令行

```bash
# 生成完整短剧（剧本→图像→视频→合成）
python cli.py

# 仅生成剧本
python cli.py --step script

# 仅生成图像
python cli.py --step image

# 仅生成视频
python cli.py --step video

# 仅合成
python cli.py --step assemble
```

### 方式二：Python 代码

```python
from src.workflow_manager import WorkflowManager
from src.prompt_builder import create_xianxia_prompt

# 初始化
wm = WorkflowManager()

# 1. 生成剧本
script = wm.generate_script("仙侠题材，主角徒手摘星辰")

# 2. 生成图像
image_prompts = wm.generate_prompts(script)
images = wm.generate_images(image_prompts)

# 3. 生成视频
videos = wm.generate_videos(images)

# 4. 合成视频
final_video = wm.assemble_videos(videos)
```

### 方式三：单独使用特效

```python
from src.video_effects import VideoEffects

effects = VideoEffects()

# 电影感调色
effects.add_color_grade("input.mp4", "output.mp4", preset="cinematic")

# 添加缩放效果
effects.add_zoom_effect("input.mp4", "output.mp4", zoom_type="in")

# 添加字幕
effects.add_text_overlay("input.mp4", "output.mp4", "仙人降临")

# 变速（慢动作）
effects.add_slow_motion("input.mp4", "output.mp4", slow_factor=0.5)
```

---

## 🎨 提示词生成

### 仙侠风格提示词

```python
from src.prompt_builder import create_xianxia_prompt

# 生成仙侠风格视频提示词
prompt = create_xianxia_prompt("徒手摘星辰", duration=5)
print(prompt)
# 输出: "周身环绕金色光芒... depth of field, vertical video..."
```

### 支持的风格

- `xianxia` - 仙侠
- `scifi` - 科幻
- `romance` - 浪漫
- `action` - 动作

---

## 🎬 视频特效

| 特效 | 说明 | 示例 |
|------|------|------|
| `add_fade_transition` | 淡入淡出 | fade_in=0.5 |
| `add_dissolve_transition` | 溶解拼接 | 多视频 |
| `add_zoom_effect` | 缩放 | zoom_type="in" |
| `add_ken_burns` | 肯汀堡 | 电影感推拉 |
| `add_color_grade` | 调色 | preset="cinematic" |
| `add_pip` | 画中画 | position="top-right" |
| `add_text_overlay` | 字幕 | text="对话" |
| `speed_ramp` | 变速 | speed=0.5 |

### 调色预设

- `cinematic` - 电影感
- `warm` - 暖色调
- `cool` - 冷色调
- `vintage` - 复古
- `noir` - 黑白

---

## 📁 项目结构

```
video-agent/
├── config/
│   └── api_keys.json       # API 配置
├── src/
│   ├── workflow_manager.py # 主工作流
│   ├── script_generator.py # 剧本生成
│   ├── cozex_client.py     # 图像生成
│   ├── jimeng_client.py    # 视频生成
│   ├── prompt_builder.py   # 提示词生成
│   ├── video_effects.py    # 视频特效
│   └── ...
├── cli.py                  # 命令行入口
├── main.py                 # 主程序
└── output/                 # 输出目录
```

---

## 🔧 当前支持的 API

| 服务 | 状态 | 说明 |
|------|------|------|
| Opus | ✅ 可用 | 剧本生成 |
| Cozex | ✅ 可用 | 图像生成 |
| 即梦 (Jimeng) | ✅ 可用 | 视频生成 |
| 可灵 (Kling) | ⏳ 需配置 | 视频生成 |
| FFmpeg | ✅ 可用 | 视频合成 |

---

## 📝 常见问题

### Q: 视频生成失败
A: 检查 `config/api_keys.json` 中的 API Key 是否正确

### Q: FFmpeg 报错
A: 确保已安装 FFmpeg: `brew install ffmpeg`

### Q: 想用其他视频生成 API
A: 参考 `src/jimeng_client.py` 实现新的客户端

---

## 🤝 贡献

欢迎提交 PR！

```bash
# 开发流程
git checkout -b feature/新功能
# 修改代码
git commit -m "feat: 添加新功能"
git push origin feature/新功能
```
