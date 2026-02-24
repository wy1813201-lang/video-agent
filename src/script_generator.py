"""
剧本生成器
使用 LLM 生成短剧剧本
"""

import os
from typing import Optional

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

请用中文输出。"""
    
    def __init__(self, config):
        self.config = config
        
        # 初始化 LLM 客户端
        self.client = None
        
        if config.openai_api_key and OPENAI_AVAILABLE:
            openai.api_key = config.openai_api_key
            self.client = "openai"
        elif config.anthropic_api_key and ANTHROPIC_AVAILABLE:
            self.client = anthropic.Anthropic(config.anthropic_api_key)
    
    async def generate_episode(
        self, 
        topic: str, 
        episode_num: int, 
        total_episodes: int
    ) -> str:
        """生成单集剧本"""
        
        user_prompt = f"""请为以下主题生成第{episode_num}集剧本:
主题: {topic}
风格: {self.config.style}
总集数: {total_episodes}
每集时长: {self.config.duration_per_episode}秒

请生成完整的剧本，包含场景描述和对话。"""
        
        if self.client == "openai":
            return await self._generate_openai(user_prompt)
        elif self.client == "anthropic":
            return await self._generate_anthropic(user_prompt)
        else:
            return self._generate_fallback(topic, episode_num)
    
    async def _generate_openai(self, prompt: str) -> str:
        """使用 OpenAI 生成"""
        try:
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
        except Exception as e:
            return f"OpenAI API 错误: {e}"
    
    async def _generate_anthropic(self, prompt: str) -> str:
        """使用 Anthropic 生成"""
        try:
            response = self.client.messages.create(
                model="claude-3-opus-20240229",
                system=self.SYSTEM_PROMPT,
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text
        except Exception as e:
            return f"Anthropic API 错误: {e}"
    
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
