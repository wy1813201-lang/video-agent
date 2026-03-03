#!/usr/bin/env python3
"""
Heartbeat 任务：每2小时执行一次
1. 美伊战争监测
2. 小红书调研
3. GitHub 调研
4. 飞书推送

使用方式：
  python3 scripts/heartbeat_tasks.py
"""

import os
import json
import asyncio
import subprocess
from datetime import datetime
from pathlib import Path

# 配置
WORKSPACE = Path.home() / ".openclaw" / "workspace"
OUTPUT_DIR = WORKSPACE / "heartbeat_output"
FEISHU_GROUP_ID = "oc_adb546cce54a6ec1a29b4a6d14154c29"

# 创建输出目录
OUTPUT_DIR.mkdir(exist_ok=True)

# 搜索结果存储
RESULTS = {
    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "iran_war": [],
    "xiaohongshu": {},
    "github": {},
    "summary": ""
}


async def search_iran_war():
    """搜索美伊战争最新消息 - 使用 curl"""
    print("[1/4] 搜索美伊战争最新消息...")
    
    # 使用 Bing News API 或 Google News RSS
    queries = [
        "Iran Israel war 2026",
        "美伊冲突 最新",
    ]
    
    results = []
    for query in queries:
        try:
            # 尝试获取 Google News RSS
            url = f"https://news.google.com/rss/search?q={query.replace(' ', '%20')}"
            cmd = f'curl -s "{url}" 2>/dev/null | head -50'
            output = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
            
            # 提取标题
            import re
            titles = re.findall(r'<title><!\[CDATA\[(.*?)\]\]></title>', output.stdout)
            
            if titles:
                results.append({
                    "query": query,
                    "count": len(titles),
                    "titles": titles[:5]
                })
        except Exception as e:
            results.append({"query": query, "error": str(e)})
    
    RESULTS["iran_war"] = results
    return results


async def search_xiaohongshu():
    """搜索小红书相关笔记 - 使用 curl 模拟搜索"""
    print("[2/4] 搜索小红书...")
    
    topics = ["一人公司", "OpenClaw", "AI短剧", "短剧"]
    
    xiaohongshu_results = {}
    
    for topic in topics:
        print(f"   搜索: {topic}")
        try:
            # 小红书搜索 URL
            search_url = f"https://edith.xiaohongshu.com/api/sns/web/v1/search/notes?keyword={topic}&page=1&page_size=10"
            
            cmd = f'''curl -s "{search_url}" \
              -H "User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36" \
              -H "Accept: application/json" \
              2>/dev/null'''
            
            output = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=15)
            
            if output.stdout:
                data = json.loads(output.stdout)
                items = data.get("data", {}).get("items", [])
                
                notes = []
                for item in items[:5]:
                    note = item.get("note_card", {}).get("note", {})
                    notes.append({
                        "title": note.get("title", ""),
                        "author": note.get("user", {}).get("nickname", ""),
                        "likes": note.get("liked_count", 0)
                    })
                
                xiaohongshu_results[topic] = {
                    "status": "success",
                    "count": len(notes),
                    "notes": notes
                }
            else:
                xiaohongshu_results[topic] = {"status": "empty", "error": "no response"}
                
        except Exception as e:
            xiaohongshu_results[topic] = {"status": "error", "error": str(e)}
    
    RESULTS["xiaohongshu"] = xiaohongshu_results
    return xiaohongshu_results


async def search_github():
    """搜索 GitHub 热门项目"""
    print("[3/4] 搜索 GitHub...")
    
    # 1. 热门项目
    try:
        cmd = 'curl -s "https://api.github.com/repos?sort=updated&per_page=10" | python3 -c "import json,sys; d=json.load(sys.stdin); print(\'\\n\'.join([f\\\"{r[\'full_name\']}: {r.get(\'description\',\'\')[:50]}\\\" for r in d[:10]]))"'
        output = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=15)
        RESULTS["github"]["trending"] = output.stdout if output.stdout else "获取失败"
    except Exception as e:
        RESULTS["github"]["trending"] = f"Error: {e}"
    
    # 2. Skills 相关项目
    try:
        cmd = 'curl -s "https://api.github.com/search/repositories?q=openai+skill+agent&per_page=10" | python3 -c "import json,sys; d=json.load(sys.stdin); items=d.get(\'items\',[]); print(\'\\n\'.join([f\\\"{r[\'full_name\']}: {r.get(\'stargazers_count\',0)} stars\\\" for r in items[:5]]))"'
        output = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=15)
        RESULTS["github"]["skills"] = output.stdout if output.stdout else "获取失败"
    except Exception as e:
        RESULTS["github"]["skills"] = f"Error: {e}"
    
    return RESULTS["github"]


async def send_to_feishu():
    """发送到飞书"""
    print("[4/4] 发送到飞书...")
    
    # 构建消息内容
    timestamp = RESULTS["timestamp"]
    
    message = f"""# 📊 Heartbeat 调研报告
**更新时间**: {timestamp}

---

## 🌏 美伊战争最新消息

{RESULTS.get('iran_war', '暂无数据')}

---

## 📕 小红书调研

| 话题 | 状态 |
|------|------|
"""
    
    for topic, data in RESULTS.get("xiaohongshu", {}).items():
        message += f"| {topic} | {data.get('status', 'pending')} |\n"
    
    message += """
---

## 💻 GitHub 热门项目

```
"""
    message += RESULTS.get("github", {}).get("trending", "获取失败")
    message += """
```

## 🔧 GitHub Skill 项目

```
"""
    message += RESULTS.get("github", {}).get("skills", "获取失败")
    message += """
```

---

*由 OpenClaw Heartbeat 自动生成*
"""
    
    # 保存到文件
    output_file = OUTPUT_DIR / f"heartbeat_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(RESULTS, f, ensure_ascii=False, indent=2)
    
    print(f"结果已保存到: {output_file}")
    
    # TODO: 发送到飞书
    # 需要配置飞书机器人 webhook
    print("飞书推送功能待配置...")
    
    return message


async def main():
    """主函数"""
    print(f"=== Heartbeat 任务开始 {datetime.now()} ===")
    
    # 1. 美伊战争
    await search_iran_war()
    
    # 2. 小红书
    await search_xiaohongshu()
    
    # 3. GitHub
    await search_github()
    
    # 4. 飞书
    message = await send_to_feishu()
    
    print(f"=== Heartbeat 任务完成 ===")
    print(message)


if __name__ == "__main__":
    asyncio.run(main())
