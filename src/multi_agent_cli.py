#!/usr/bin/env python3
"""
多代理分析系统 - 命令行工具
用法: python multi_agent_cli.py "你的话题" "新闻内容"
"""

import asyncio
import json
import sys
import requests
from typing import List, Dict, Any


# ============ 配置区 ============
# 在这里填入你的 API Key
LLM_API_KEY = ""  # MiniMax API Key
LLM_BASE_URL = "https://api.minimax.chat/v1/text/chatcompletion_pro"
LLM_MODEL = "abab6.5s-chat"
# ==============================


AGENT_PROMPTS = {
    "market": """你是市场分析专家。分析以下新闻/趋势，回答：
1. 这个市场有多大？（规模、增长速度）
2. 目标用户是谁？需求是什么？
3. 商业变现机会有哪些？
输出 JSON: {"analysis": "...", "score": 0-10, "recommendation": "干/不干/再看看", "evidence": [], "concerns": []}""",

    "tech": """你是技术分析专家。分析以下趋势/机会，回答：
1. 技术门槛有多高？普通人能上手吗？
2. 需要什么技能/工具？
3. 技术风险有哪些？
输出 JSON: {"analysis": "...", "score": 0-10, "recommendation": "干/不干/再看看", "evidence": [], "concerns": []}""",

    "platform": """你是平台分析专家。分析以下趋势/机会，回答：
1. 哪个平台在支持这个领域？平台给不给流量？
2. 规则是什么？有没有风险？
输出 JSON: {"analysis": "...", "score": 0-10, "recommendation": "干/不干/再看看", "evidence": [], "concerns": []}""",

    "competitor": """你是竞争分析专家。分析以下趋势/机会，回答：
1. 有多少人已经在做了？是红海还是蓝海？
2. 还有没有入场机会？
输出 JSON: {"analysis": "...", "score": 0-10, "recommendation": "干/不干/再看看", "evidence": [], "concerns": []}"""
}


def call_llm(prompt: str) -> str:
    """调用 LLM"""
    if not LLM_API_KEY:
        return None
    
    headers = {
        "Authorization": f"Bearer {LLM_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": LLM_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 1500
    }
    
    try:
        resp = requests.post(LLM_BASE_URL, headers=headers, json=data, timeout=60)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"LLM Error: {e}")
        return None


def parse_json_response(text: str) -> Dict:
    """解析 JSON 响应"""
    try:
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(text[start:end])
    except:
        pass
    return {"analysis": text[:200], "score": 5, "recommendation": "再看看", "evidence": [], "concerns": []}


async def analyze(topic: str, news: str):
    """执行分析"""
    print(f"\n🔍 主题: {topic}")
    print("=" * 50)
    
    # 并行调用各代理
    tasks = []
    for name, prompt in AGENT_PROMPTS.items():
        full_prompt = f"主题：{topic}\n\n新闻背景：{news}\n\n{prompt}"
        tasks.append((name, full_prompt))
    
    results = []
    for name, prompt in tasks:
        print(f"📡 {name} 代理分析中...")
        response = call_llm(prompt)
        if response:
            result = parse_json_response(response)
            result["agent"] = name
            results.append(result)
            print(f"   ✅ {name}: {result.get('score', '?')}/10 - {result.get('recommendation', '')}")
        else:
            print(f"   ❌ {name}: API 未配置")
            results.append({"agent": name, "score": 5, "recommendation": "再看看", "analysis": "API未配置"})
    
    # 生成总结
    if results:
        scores = [r.get("score", 5) for r in results]
        avg_score = sum(scores) / len(scores)
        
        if avg_score >= 7:
            rec = "✅ 干"
        elif avg_score >= 4:
            rec = "🤔 再看看"
        else:
            rec = "❌ 不干"
        
        print("\n" + "=" * 50)
        print(f"🎯 最终结论: {rec} (评分: {avg_score:.1f}/10)")
        print("=" * 50)
        
        # 各维度详情
        print("\n📊 各维度分析:")
        for r in results:
            emoji = "✅" if r.get("score", 5) >= 6 else "❌" if r.get("score", 5) < 4 else "🤔"
            print(f"  {emoji} {r['agent']}: {r.get('score', '?')}/10")
        
        # 证据汇总
        all_evidence = []
        for r in results:
            all_evidence.extend(r.get("evidence", []))
        
        if all_evidence:
            print("\n📌 关键证据:")
            for e in all_evidence[:5]:
                print(f"  • {e}")
    else:
        print("\n⚠️ 请配置 LLM_API_KEY 后使用")
        print("   1. 获取 MiniMax API Key")
        print("   2. 修改脚本开头的 LLM_API_KEY 变量")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python multi_agent_cli.py \"话题\" \"新闻内容\"")
        print("示例: python multi_agent_cli.py \"AI短剧值得做吗\" \"AI仿真人剧百强率从7%升到38%\"")
        sys.exit(1)
    
    topic = sys.argv[1]
    news = sys.argv[2] if len(sys.argv) > 2 else "无"
    
    asyncio.run(analyze(topic, news))
