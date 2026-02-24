# API 配置说明

本项目支持多种 AI 视频生成平台，请在运行前配置相应的 API。

## 需要的 API 清单

### 1. 视频生成 API（必须至少配置一个）

| 平台 | 用途 | 获取方式 | 免费额度 |
|------|------|----------|----------|
| **可灵 AI (Kling)** | 视频生成 | https://app.klingai.com | 每天66积分 |
| **即梦 AI (Jimeng)** | 视频生成 | https://jimeng.jianying.com | 部分免费 |
| **海螺 AI (Hailuo)** | 视频生成 | https://hailuoai.com | 部分免费 |
| **Runway** | 视频生成 | https://runwayml.com | 免费试用 |
| **Pika** | 视频生成 | https://pika.art | 免费试用 |
| **Luma** | 视频生成 | https://lumalabs.ai | 免费试用 |

### 2. 剧本生成 API（可选，推荐配置）

| 平台 | 用途 | 获取方式 |
|------|------|----------|
| **OpenAI API** | GPT-4 生成剧本 | https://platform.openai.com |
| **Claude API** | Claude 生成剧本 | https://www.anthropic.com |
| **MiniMax API** | 国产 LLM | https://platform.minimaxi.com |

### 3. 图像生成 API（可选）

| 平台 | 用途 | 获取方式 |
|------|------|----------|
| **Midjourney** | 图像生成 | Discord |
| **Stable Diffusion** | 图像生成 | 本地/云端部署 |
| **DALL-E** | 图像生成 | OpenAI |

## 环境变量配置

```bash
# 视频生成
export KLING_API_KEY="your-kling-api-key"
export RUNWAY_API_KEY="your-runway-api-key"
export PIKA_API_KEY="your-pika-api-key"

# 剧本生成
export OPENAI_API_KEY="sk-..."
export ANTHROPIC_API_KEY="sk-ant-..."

# 图像生成
export MIDJOURNEY_API_KEY="your-midjourney-token"
```

## 配置文件

在 `config/api_keys.json` 中配置：

```json
{
  "video": {
    "kling": {
      "enabled": false,
      "api_key": "your-key"
    },
    "jimeng": {
      "enabled": false,
      "cookies": "your-cookies"
    }
  },
  "script": {
    "openai": {
      "enabled": false,
      "api_key": "sk-..."
    },
    "anthropic": {
      "enabled": false,
      "api_key": "sk-ant-..."
    }
  }
}
```

## 获取 API Key 的步骤

### 可灵 AI (Kling)
1. 访问 https://app.klingai.com
2. 注册账号
3. 在「个人中心」→「开发者选项」获取 API Key
4. 每日免费 66 积分

### 即梦 AI (Jimeng)
1. 访问 https://jimeng.jianying.com
2. 登录账号
3. 目前主要通过网页端使用，API 陆续开放中

### OpenAI
1. 访问 https://platform.openai.com
2. 创建 API Key
3. 充值或使用免费额度

### Claude
1. 访问 https://www.anthropic.com
2. 进入 API 控制台
3. 创建 API Key

## 当前状态

- [ ] 可灵 API
- [ ] 即梦 API  
- [ ] 海螺 API
- [ ] OpenAI API
- [ ] Claude API

请在获取 API Key 后更新配置文件。
