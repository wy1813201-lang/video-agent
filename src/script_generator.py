"""
剧本生成器
使用 LLM 生成短剧剧本
支持自定义 API 端点
"""

import os
import json
import requests
from typing import Optional, Dict, Any

# 可以集成的 LLM 客户端
OPENAI_AVAILABLE = False
ANTHROPIC_AVAILABLE = False

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    pass

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    pass


class ScriptGenerator:
    """AI剧本生成器"""
    
    SYSTEM_PROMPT = """你是一个专业的小说家和剧本作家。
你擅长创作吸引人的短剧剧本，特别是:
- 情感剧: 爱情、家庭、复仇
- 悬疑剧: 推理、探案、惊悚
- 搞笑剧: 喜剧、段子
- 科幻剧: 未来、科幻

请生成适合AI视频生成的短剧剧本。
剧本格式:
1. 每集3-5个场景
2. 每个场景包含: 场景描述、对话
3. 对话要简洁有力，适合短视频节奏
4. 每集结束时要有悬念或反转
5. 前三分钟必须有情绪反转，具备极高的商业转化率

请用中文输出。"""
    
    def __init__(self, config, api_config=None):
        self.config = config
        self.api_config = api_config or {}
        
        # 初始化 LLM 客户端
        self.client = None
        self.client_type = None
        self.gemini_web_client = None
        self._market_report = None  # 缓存调研结果，同次运行复用

        # 初始化市场调研器
        market_cfg = self.api_config.get("market_research", {})
        try:
            from .market_researcher import MarketResearcher
        except ImportError:
            from market_researcher import MarketResearcher
        self.market_researcher = MarketResearcher(market_cfg)

        gemini_web = self.api_config.get("script", {}).get("gemini_web", {})
        self.gemini_web_config = gemini_web
        if gemini_web.get("enabled"):
            self.client_type = "gemini_web"
            return
        
        # 优先使用自定义 Opus 端点
        custom_opus = self.api_config.get("script", {}).get("custom_opus", {})
        if custom_opus.get("enabled") and custom_opus.get("api_key"):
            self.custom_opus = {
                "api_key": custom_opus["api_key"],
                "base_url": custom_opus.get("base_url", "http://47.253.7.24:3000"),
                "model": custom_opus.get("model", "claude-opus-4-6")
            }
            self.client_type = "custom_opus"
        elif config.openai_api_key and OPENAI_AVAILABLE:
            openai.api_key = config.openai_api_key
            self.client_type = "openai"
        elif config.anthropic_api_key and ANTHROPIC_AVAILABLE:
            self.client = anthropic.Anthropic(api_key=config.anthropic_api_key)
            self.client_type = "anthropic"
    
    async def _get_market_report(self) -> str:
        """获取市场调研摘要（同次运行缓存复用）"""
        if not self.market_researcher.enabled:
            return ""
        if self._market_report is None:
            try:
                report = await self.market_researcher.research(use_cache=True)
                self._market_report = self.market_researcher.format_for_prompt(report)
            except Exception as e:
                print(f"[ScriptGenerator] 市场调研获取失败: {e}，继续生成")
                self._market_report = ""
        return self._market_report

    async def generate_episode(
        self, 
        topic: str, 
        episode_num: int, 
        total_episodes: int
    ) -> str:
        """生成单集剧本（生成前自动注入市场调研结果）"""

        # 获取市场调研摘要
        market_context = await self._get_market_report()

        market_section = ""
        if market_context:
            market_section = f"\n\n{market_context}\n\n请基于以上市场调研数据，确保剧本题材符合当前热门趋势，前三分钟有情绪反转，具备高商业转化率。\n"

        user_prompt = f"""请为以下主题生成第{episode_num}集剧本:
主题: {topic}
风格: {self.config.style}
总集数: {total_episodes}
每集时长: {self.config.duration_per_episode}秒
{market_section}
请生成完整的剧本，包含场景描述和对话。每集内容要有变化，不要重复。"""
        
        try:
            if self.client_type == "gemini_web":
                return await self._generate_gemini_web(user_prompt, topic, episode_num, total_episodes)
            elif self.client_type == "custom_opus":
                return await self._generate_custom_opus(user_prompt)
            elif self.client_type == "openai":
                return await self._generate_openai(user_prompt)
            elif self.client_type == "anthropic":
                return await self._generate_anthropic(user_prompt)
            else:
                return self._generate_fallback(topic, episode_num)
        except Exception as e:
            raise RuntimeError(f"第{episode_num}集剧本生成失败: {e}") from e
    
    async def _generate_custom_opus(self, prompt: str) -> str:
        """使用自定义 Opus 端点生成"""
        url = f"{self.custom_opus['base_url']}/v1/messages"
        headers = {
            "Authorization": f"Bearer {self.custom_opus['api_key']}",
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01"
        }
        data = {
            "model": self.custom_opus["model"],
            "max_tokens": 4000,
            "system": self.SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": prompt}]
        }
        
        response = requests.post(url, headers=headers, json=data, timeout=120)
        response.raise_for_status()
        
        result = response.json()
        return result["content"][0]["text"]
    
    async def _generate_openai(self, prompt: str) -> str:
        """使用 OpenAI 生成"""
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ],
            temperature=0.8,
            max_tokens=2000
        )
        return response.choices[0].message.content
    
    async def _generate_anthropic(self, prompt: str) -> str:
        """使用 Anthropic Claude Opus 生成"""
        response = self.client.messages.create(
            model="claude-opus-4-6-20251114",
            system=self.SYSTEM_PROMPT,
            max_tokens=4000,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.8
        )
        return response.content[0].text

    async def _generate_gemini_web(
        self,
        prompt: str,
        topic: str,
        episode_num: int,
        total_episodes: int,
    ) -> str:
        """使用 Gemini 网页版生成结构化剧本，再转换为文本供工作流复用。"""
        if self.gemini_web_client is None:
            try:
                from .gemini_web_client import GeminiWebClient
            except ImportError:
                from gemini_web_client import GeminiWebClient

            self.gemini_web_client = GeminiWebClient(
                headless=self.gemini_web_config.get("headless", True),
                timeout_ms=self.gemini_web_config.get("timeout_ms", 120000),
                gemini_url=self.gemini_web_config.get("url", "https://gemini.google.com/app"),
            )

        provider_prompt = (
            f"{self.SYSTEM_PROMPT}\n\n"
            f"请重点生成第{episode_num}/{total_episodes}集，主题是“{topic}”。\n"
            f"{prompt}"
        )
        script_json = await self.gemini_web_client.generate_script(provider_prompt)
        return self._script_json_to_text(script_json, episode_num)

    async def close(self):
        """释放外部资源。"""
        if self.gemini_web_client:
            await self.gemini_web_client.close()

    def _script_json_to_text(self, script_json: Dict[str, Any], episode_num: int) -> str:
        """把 Gemini JSON 剧本转成现有文本流程可复用格式。"""
        title = script_json.get("title") or f"第{episode_num}集"
        summary = script_json.get("summary", "")
        scenes = script_json.get("scenes") or []

        lines = [f"{title}"]
        if summary:
            lines.append(f"梗概: {summary}")
        lines.append("")

        for idx, scene in enumerate(scenes, start=1):
            location = scene.get("location", "未知地点")
            description = scene.get("description", "")
            lines.append(f"场景{idx}: [{location}]")
            if description:
                lines.append(f"描述: {description}")

            for dialogue in scene.get("dialogues") or []:
                speaker = dialogue.get("speaker", "角色")
                line = dialogue.get("line", "")
                lines.append(f"{speaker}: {line}")
            lines.append("")

        return "\n".join(lines).strip()
    
    def _generate_fallback(self, topic: str, episode_num: int) -> str:
        """生成示例剧本"""
        templates = {
            "情感": self._emotion_template,
            "悬疑": self._mystery_template,
            "搞笑": self._comedy_template,
            "科幻": self._scifi_template
        }
        
        template = templates.get(self.config.style, self._emotion_template)
        return template(topic, episode_num)
    
    def _emotion_template(self, topic: str, episode_num: int) -> str:
        return f"""第{episode_num}集: 重生归来

场景1: [清晨·卧室]
旁白: 当她再次睁开眼，时间回到了十年前...
女主: 这是...十年前？我重生了？

场景2: [客厅]
妈妈: 起来了？快来吃早餐。
女主: (震惊)妈...妈妈...(上一世，妈妈已经...)
妈妈: 怎么了？傻孩子。

场景3: [学校]
同学: 听说今天有新同学转来...
男主: (出场)大家好，我是...
女主: (内心)是他！就是这个人，上一世害我家破人亡！

场景4: [结尾]
女主: (内心)既然重生了，这一世我一定要保护好家人，让他付出代价！
字幕: 敬请期待下一集"""

    def _mystery_template(self, topic: str, episode_num: int) -> str:
        return f"""第{episode_num}集: 神秘事件

场景1: [夜晚·办公室]
职员: 老板，账目不对...
老板: 别多说，照做就是。

场景2: [次日·警察局]
侦探: 这个月第几起了？
警察: 第三起了，作案手法一模一样。

场景3: [线索]
证人: 我看到了...一个穿红衣服的女人...
(画面模糊)

场景4: [结尾]
侦探: 凶手，似乎就在我们身边..."""

    def _comedy_template(self, topic: str, episode_num: int) -> str:
        return f"""第{episode_num}集: 乌龙事件

场景1: [早上·家里]
男主: 糟了！要迟到了！
(匆忙出门)

场景2: [路上]
男主: (骑车)让让！让让！
(撞到人)

场景3: [公司]
男主: (喘气)报告...我来晚了...
老板: 嗯，今天来得挺早嘛。
男主: 啊？"""

    def _scifi_template(self, topic: str, episode_num: int) -> str:
        return f"""第{episode_num}集: 穿越未来

场景1: [实验室]
博士: 时间机器成功了！
助手: 真的要发射吗？

场景2: [未来世界]
(闪光特效)
男主: 这是...哪里？
机器人: 欢迎来到2150年。

场景3: [真相]
博士(画外音): 如果你看到这个，说明你成功穿越了...
男主: 什么？"""
