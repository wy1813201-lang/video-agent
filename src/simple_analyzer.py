#!/usr/bin/env python3
"""
简单多代理分析 - 使用当前会话模型
"""

ANALYZER_PROMPT = """你是一个多代理分析团队。请从以下4个维度分析这个问题：

话题：{topic}
新闻背景：{news}

请依次输出：

## 1. 市场分析
- 市场规模和增长
- 商业机会
（评分0-10）

## 2. 技术分析  
- 技术门槛
- 普通人能上手吗
（评分0-10）

## 3. 平台分析
- 哪个平台支持
- 流量情况
（评分0-10）

## 4. 竞争分析
- 竞争程度
- 入场机会
（评分0-10）

## 最终结论
- 整体评分（平均）
- 建议：干 / 不干 / 再看看
- 一句话总结
- 如果干，具体做什么

注意：结论一定要简单，老百姓能看懂。"""


def analyze(topic: str, news: str):
    """打印分析提示，用户自己填入内容"""
    print("=" * 60)
    print(f"📊 分析话题: {topic}")
    print("=" * 60)
    print("\n请把以下提示词复制到 AI 对话中使用：\n")
    print(ANALYZER_PROMPT.format(topic=topic, news=news))
    print("\n" + "=" * 60)


if __name__ == "__main__":
    import sys
    topic = sys.argv[1] if len(sys.argv) > 1 else "AI短剧值得做吗"
    news = sys.argv[2] if len(sys.argv) > 2 else "AI仿真人剧百强率从7%升到38%，2026年1月播放量达25.48亿"
    analyze(topic, news)
