#!/usr/bin/env python3
"""
多代理分析系统 - 基于 MetaGPT 理念
专注于新闻分析和收益机会判断
"""

import os
import json
import asyncio
import requests
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum


# LLM 调用函数
def call_llm(prompt: str, model: str = "abab6.5s-chat") -> str:
    """调用 MiniMax LLM"""
    url = "https://api.minimax.chat/v1/text/chatcompletion_pro"
    headers = {
        "Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJtb2RlbCI6ImFiYWI2LjVzIiwiYWNjb3VudCI6IjEwNDY4NDlEIiwiZXhwIjoxNzUwOTM4MDQ0fQ.JPk5zL4R_VKKpFkL0N6T6K3K1K3K1K3K1K3K1K3K1K",
        "Content-Type": "application/json"
    }
    data = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 2000,
        "temperature": 0.7
    }
    
    try:
        resp = requests.post(url, headers=headers, json=data, timeout=60)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"LLM 调用失败: {e}"


class AgentRole(Enum):
    COORDINATOR = "coordinator"      # 协调者
    MARKET_ANALYST = "market"        # 市场分析
    TECH_ANALYST = "tech"           # 技术分析
    PLATFORM_ANALYST = "platform"   # 平台分析
    COMPETITOR_ANALYST = "competitor"  # 竞争分析
    SUMMARIZER = "summarizer"       # 总结者


@dataclass
class AgentResult:
    role: AgentRole
    analysis: str
    score: float  # 0-10 机会评分
    recommendation: str  # 干/不干/再看看
    evidence: List[str] = field(default_factory=list)
    concerns: List[str] = field(default_factory=list)


@dataclass
class FinalReport:
    topic: str
    overall_score: float
    recommendation: str
    agent_results: List[AgentResult]
    summary: str
    action_items: List[str]


# 代理系统提示词
AGENT_PROMPTS = {
    AgentRole.COORDINATOR: """你是一个项目协调者，负责管理多个专业分析代理。
你的任务是：
1. 将任务分配给合适的代理
2. 收集各代理的分析结果
3. 发现分析之间的矛盾并进行交叉验证
4. 最终整合所有意见，给出简单结论

记住：最终结论一定要简单：干 / 不干 / 再看看""",

    AgentRole.MARKET_ANALYST: """你是市场分析专家。
分析以下新闻/趋势，回答：
1. 这个市场有多大？（规模、增长速度）
2. 目标用户是谁？需求是什么？
3. 商业变现机会有哪些？
4. 机会评分（0-10分）

只输出分析结果，不需要总结。""",

    AgentRole.TECH_ANALYST: """你是技术分析专家。
分析以下趋势/机会，回答：
1. 技术门槛有多高？
2. 普通人能上手吗？
3. 需要什么技能/工具？
4. 技术风险有哪些？
5. 机会评分（0-10分）

只输出分析结果，不需要总结。""",

    AgentRole.PLATFORM_ANALYST: """你是平台分析专家。
分析以下趋势/机会，回答：
1. 哪个平台在支持这个领域？
2. 平台给不给流量？
3. 规则是什么？有没有风险？
4. 机会评分（0-10分）

只输出分析结果，不需要总结。""",

    AgentRole.COMPETITOR_ANALYST: """你是竞争分析专家。
分析以下趋势/机会，回答：
1. 有多少人已经在做了？
2. 是红海还是蓝海？
3. 还有没有入场机会？
4. 机会评分（0-10分）

只输出分析结果，不需要总结。""",

    AgentRole.SUMMARIZER: """你是总结专家。
基于各维度的分析结果，给出最终结论。

分析结果：
{results}

请输出：
1. 整体评分（加权平均）
2. 最终建议：干 / 不干 / 再看看
3. 一句话总结
4. 具体行动建议（如果干的话）

记住：一定要简单，老百姓能看懂。""",
}


class MultiAgentAnalyzer:
    """多代理分析系统"""

    def __init__(self, llm_client=None):
        self.llm_client = llm_client
        self.agents = {}

    async def analyze(self, topic: str, news_content: str) -> FinalReport:
        """执行多代理分析"""

        # 阶段1：并行调用各专业代理
        market_task = self._analyze_with_agent(
            AgentRole.MARKET_ANALYST, topic, news_content
        )
        tech_task = self._analyze_with_agent(
            AgentRole.TECH_ANALYST, topic, news_content
        )
        platform_task = self._analyze_with_agent(
            AgentRole.PLATFORM_ANALYST, topic, news_content
        )
        competitor_task = self._analyze_with_agent(
            AgentRole.COMPETITOR_ANALYST, topic, news_content
        )

        # 并行执行
        results = await asyncio.gather(
            market_task, tech_task, platform_task, competitor_task
        )

        # 阶段2：交叉验证 - 检查矛盾
        validated_results = self._cross_validate(results)

        # 阶段3：生成最终报告
        final_report = await self._generate_final_report(topic, validated_results)

        return final_report

    async def _analyze_with_agent(
        self, role: AgentRole, topic: str, context: str
    ) -> AgentResult:
        """单个代理分析"""
        prompt = f"""主题：{topic}

背景信息：
{context}

{AGENT_PROMPTS[role]}

请严格按照以下 JSON 格式输出，不要有其他内容：
{{
    "analysis": "分析内容",
    "score": 评分(0-10的数字),
    "recommendation": "干/不干/再看看",
    "evidence": ["证据1", "证据2"],
    "concerns": ["担忧1", "担忧2"]
}}"""

        # 调用 LLM
        loop = asyncio.get_event_loop()
        result_text = await loop.run_in_executor(None, call_llm, prompt)

        # 解析 JSON
        try:
            # 提取 JSON 部分
            start = result_text.find("{")
            end = result_text.rfind("}") + 1
            if start >= 0 and end > start:
                data = json.loads(result_text[start:end])
                return AgentResult(
                    role=role,
                    analysis=data.get("analysis", ""),
                    score=float(data.get("score", 5)),
                    recommendation=data.get("recommendation", "再看看"),
                    evidence=data.get("evidence", []),
                    concerns=data.get("concerns", [])
                )
        except:
            pass

        # 解析失败，返回原始结果
        return AgentResult(
            role=role,
            analysis=result_text[:500],
            score=5.0,
            recommendation="再看看",
            evidence=[],
            concerns=["解析失败"]
        )

    def _cross_validate(self, results: List[AgentResult]) -> List[AgentResult]:
        """交叉验证各代理结果"""
        # 检查评分差异
        scores = [r.score for r in results]
        if max(scores) - min(scores) > 4:
            # 差异过大，标记为不确定
            for r in results:
                if r.score < 5:
                    r.concerns.append("⚠️ 与其他维度评分差异过大")

        return results

    async def _generate_final_report(
        self, topic: str, results: List[AgentResult]
    ) -> FinalReport:
        """生成最终报告"""

        # 计算加权平均分
        weights = {
            AgentRole.MARKET_ANALYST: 0.3,
            AgentRole.TECH_ANALYST: 0.2,
            AgentRole.PLATFORM_ANALYST: 0.3,
            AgentRole.COMPETITOR_ANALYST: 0.2,
        }

        weighted_score = sum(
            r.score * weights.get(r.role, 0.1) for r in results
        )

        # 生成建议
        if weighted_score >= 7:
            recommendation = "✅ 干"
        elif weighted_score >= 4:
            recommendation = "🤔 再看看"
        else:
            recommendation = "❌ 不干"

        # 生成总结
        positive_results = [r for r in results if r.score >= 6]
        negative_results = [r for r in results if r.score < 4]

        if positive_results:
            summary = f"机会较大({weighted_score:.1f}分)，"
            summary += "、".join([r.role.value for r in positive_results])
            summary += "维度表现好"
        elif negative_results:
            summary = f"风险较大({weighted_score:.1f}分)，"
            summary += "、".join([r.role.value for r in negative_results])
            summary += "维度有担忧"
        else:
            summary = f"中性({weighted_score:.1f}分)，建议进一步观察"

        # 行动建议
        action_items = []
        if recommendation.startswith("✅"):
            action_items = [
                "立即开始小规模测试",
                "关注平台政策变化",
                "每周复盘进展"
            ]

        return FinalReport(
            topic=topic,
            overall_score=weighted_score,
            recommendation=recommendation,
            agent_results=results,
            summary=summary,
            action_items=action_items
        )

    def to_markdown(self, report: FinalReport) -> str:
        """转换为 Markdown 格式"""
        md = f"""# 📊 分析报告

**主题**: {report.topic}

---

## 🎯 最终结论

**{report.recommendation}** (评分: {report.overall_score:.1f}/10)

{report.summary}

---

## 📈 各维度分析

"""

        for r in report.agent_results:
            emoji = "✅" if r.score >= 6 else "❌" if r.score < 4 else "🤔"
            md += f"""### {emoji} {r.role.value.upper()}

- **评分**: {r.score}/10
- **建议**: {r.recommendation}
- **分析**: {r.analysis}

"""

        if report.action_items:
            md += """## 🚀 行动建议

"""
            for item in report.action_items:
                md += f"- {item}\n"

        return md


# 测试
async def main():
    analyzer = MultiAgentAnalyzer()

    report = await analyzer.analyze(
        topic="AI 短剧是否值得做？",
        news_content="""
        - AI 仿真人剧百强率从 7% 提升到 38%
        - 2026 年 1 月播放量达 25.48 亿
        - 抖音漫剧播放量超 700 亿，市场规模突破 200 亿
        - AI 赋能下生产环节缩短三分之一，效率提升 80%
        """
    )

    print(analyzer.to_markdown(report))


if __name__ == "__main__":
    asyncio.run(main())
