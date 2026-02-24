# 🎬 VideoAgent - AI 短剧自动生成器

> 用 AI 自动创作短剧：一键生成剧本 → AI 图像提示词 → 视频合成

## 功能特性

- 📝 **剧本生成** - 使用 LLM 生成原创短剧剧本
- 🎨 **提示词生成** - 自动生成适配 Midjourney/SD/可灵/即梦 的 AI 图像提示词
- 🎥 **视频合成** - 使用 FFmpeg 本地合成视频
- 🌐 **浏览器自动化** - 可扩展支持在线 AI 视频平台自动操作
- 📱 **多平台支持** - 适配多种国产 AI 视频工具

## 快速开始

### 1. 安装依赖

```bash
cd ai-short-drama-automator
pip install -r requirements.txt
```

### 2. 配置 API

请参考 [API_SETUP.md](./API_SETUP.md) 获取所需的 API Key。

### 3. 运行

```bash
# 生成剧本
python main.py

# 或自定义主题
python main.py --topic "重生千金复仇记" --episodes 3
```

## 项目结构

```
ai-short-drama-automator/
├── main.py                 # 主程序入口
├── src/
│   ├── script_generator.py  # 剧本生成模块
│   ├── prompt_builder.py    # AI 提示词生成
│   ├── video_assembler.py   # FFmpeg 视频合成
│   ├── browser_automation.py # 浏览器自动化
│   └── domestic_ai_video.py  # 国产AI视频工具
├── config/                  # 配置文件
├── output/                  # 生成的内容
├── prompts/                 # 提示词模板
├── requirements.txt         # Python 依赖
├── API_SETUP.md             # API 配置指南
└── README.md
```

## 支持的工具

### 剧本生成
- [x] OpenAI GPT
- [x] Anthropic Claude
- [x] MiniMax (国产)

### 视频生成 (需要 API)
- [ ] 可灵 AI - 国产最强视频生成
- [ ] 即梦 AI - 字节跳动
- [ ] 海螺 AI - MiniMax
- [ ] Runway ML - 国际
- [ ] Pika Labs - 国际
- [ ] Luma AI - 国际

### 本地视频处理
- [x] FFmpeg - 视频合成

## 使用示例

### 生成短剧剧本

```python
from main import ShortDramaAutomator, DramaConfig
import asyncio

config = DramaConfig(
    topic="重生千金复仇记",
    style="情感",
    episodes=3,
    openai_api_key="your-key"
)

automator = ShortDramaAutomator(config)
asyncio.run(automator.generate_drama())
```

### 使用浏览器自动化生成视频

```python
from src.browser_automation import AIVideoBrowser

browser = AIVideoBrowser(headless=False)
await browser.start()
job = await browser.generate_video("pika", "A sunset over ocean...")
```

## 当前进度

- ✅ 剧本生成框架完成
- ✅ 提示词生成完成
- ✅ 本地视频合成完成
- 🔄 浏览器自动化调试中
- ⏳ API 集成待配置

## 贡献

欢迎提交 Issue 和 Pull Request！

## License

MIT
