#!/usr/bin/env python3
"""
市场调研脚本 - 使用 OpenClaw browser 工具调用 Gemini 网页版
"""

import json
import os
import sys
import re
import time
import argparse
import subprocess
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

GEMINI_URL = "https://gemini.google.com/u/1/app/24a8b6c52b74c713?pageId=none"

RESEARCH_PROMPT = """请深入调研番茄小说、起点中文网、晋江文学城近一个月的畅销榜、飙升榜前十名的作品。

竞品分析：分析这些热门作品的核心爆点（如：逆袭、马甲、虐恋重生等）、受众画像及叙事节奏。

请以JSON格式输出，结构如下：
{
  "research_date": "调研日期",
  "platforms": ["番茄小说", "起点中文网", "晋江文学城"],
  "top_works": [
    {
      "title": "作品名",
      "platform": "平台",
      "genre": "题材类型",
      "core_hooks": ["爆点1", "爆点2"],
      "audience": "受众画像描述",
      "narrative_pace": "叙事节奏描述",
      "rank": 1
    }
  ],
  "trend_analysis": {
    "dominant_genres": ["最热题材1", "最热题材2"],
    "top_hooks": ["最高频爆点1", "最高频爆点2", "最高频爆点3"],
    "audience_profile": "综合受众画像",
    "narrative_trends": "叙事节奏趋势总结"
  },
  "script_recommendations": {
    "recommended_genre": "推荐题材",
    "recommended_hooks": ["推荐爆点1", "推荐爆点2"],
    "opening_strategy": "前三分钟情绪反转策略",
    "commercial_tips": "商业转化率提升建议"
  }
}

只输出JSON，不要其他文字。"""


# ---------------------------------------------------------------------------
# OpenClaw browser tool wrapper (calls openclaw CLI as subprocess)
# ---------------------------------------------------------------------------

def _openclaw(payload: dict) -> dict:
    """Call openclaw tool via CLI and return parsed JSON result."""
    cmd = ["openclaw", "tool", "browser", json.dumps(payload)]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        raise RuntimeError(f"openclaw tool error: {result.stderr.strip()}")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"raw": result.stdout}


def browser_action(action: str, **kwargs) -> dict:
    payload = {"action": action, "profile": "chrome", **kwargs}
    return _openclaw(payload)


# ---------------------------------------------------------------------------
# Gemini web automation
# ---------------------------------------------------------------------------

def run_gemini_research() -> str:
    """Open Gemini URL, submit prompt, wait for response, return text."""
    print(f"[Gemini] 打开 URL: {GEMINI_URL}")

    # Open the tab
    open_result = browser_action("open", targetUrl=GEMINI_URL)
    target_id = open_result.get("targetId") or open_result.get("tabId")
    if not target_id:
        # Try to get from tabs list
        tabs = browser_action("tabs")
        for tab in (tabs.get("tabs") or []):
            if "gemini.google.com" in tab.get("url", ""):
                target_id = tab.get("targetId") or tab.get("id")
                break
    if not target_id:
        raise RuntimeError("无法获取 Gemini 标签页 ID")

    print(f"[Gemini] 标签页 ID: {target_id}")
    time.sleep(4)  # wait for page load

    # Take snapshot to find the input box
    print("[Gemini] 获取页面快照...")
    snap = browser_action("snapshot", targetId=target_id)

    # Click the input area and type the prompt
    print("[Gemini] 输入调研 prompt...")
    browser_action(
        "act",
        targetId=target_id,
        request={
            "kind": "click",
            "ref": "textarea",
        }
    )
    time.sleep(0.5)

    # Type prompt (split to avoid timeout on large text)
    browser_action(
        "act",
        targetId=target_id,
        request={
            "kind": "fill",
            "ref": "textarea",
            "text": RESEARCH_PROMPT,
        }
    )
    time.sleep(0.5)

    # Submit with Enter
    browser_action(
        "act",
        targetId=target_id,
        request={"kind": "press", "key": "Enter"}
    )

    # Wait for Gemini to respond (poll snapshot until response appears)
    print("[Gemini] 等待 Gemini 响应（最多 120 秒）...")
    response_text = ""
    for attempt in range(24):  # 24 * 5s = 120s
        time.sleep(5)
        snap = browser_action("snapshot", targetId=target_id)
        content = snap.get("content") or snap.get("text") or json.dumps(snap)
        # Look for JSON block in the page content
        if "{" in content and "research_date" in content:
            response_text = content
            print(f"[Gemini] 检测到 JSON 响应（第 {attempt+1} 次轮询）")
            break
        if attempt % 4 == 3:
            print(f"[Gemini] 仍在等待... ({(attempt+1)*5}s)")
    else:
        # Take screenshot for debugging
        browser_action("screenshot", targetId=target_id)
        # Return whatever we have
        snap = browser_action("snapshot", targetId=target_id)
        response_text = snap.get("content") or snap.get("text") or json.dumps(snap)
        print("[Gemini] 警告：超时，使用当前页面内容")

    return response_text


# ---------------------------------------------------------------------------
# JSON parsing
# ---------------------------------------------------------------------------

def parse_json(text: str) -> dict:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"\s*```\s*$", "", text, flags=re.MULTILINE)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r"(\{[\s\S]+\})", text)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    return {"raw_text": text[:2000], "parse_error": True}


# ---------------------------------------------------------------------------
# Fallback: API direct call (kept from original)
# ---------------------------------------------------------------------------

def load_api_config() -> dict:
    config_path = Path(__file__).parent.parent / "config" / "api_keys.json"
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        script_cfg = data.get("script", {})
        for key in ["custom_opus", "openai"]:
            cfg = script_cfg.get(key, {})
            if cfg.get("enabled") and cfg.get("api_key"):
                return cfg
    return {}


def call_api_fallback(prompt: str) -> str:
    cfg = load_api_config()
    if not cfg:
        raise RuntimeError("未找到可用的 API 配置")
    try:
        from openai import OpenAI
    except ImportError:
        raise RuntimeError("openai 包未安装，请运行: pip3 install openai")

    base_url = cfg.get("base_url", "https://api.openai.com/v1")
    if not base_url.endswith("/v1"):
        base_url = base_url.rstrip("/") + "/v1"
    client = OpenAI(api_key=cfg["api_key"], base_url=base_url)
    model = cfg.get("model", "gpt-4o")
    print(f"[Fallback] 调用 API: {cfg.get('base_url')} model={model}")
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "你是一个专业的网文市场分析师，熟悉中国网络文学平台的热门趋势。"},
            {"role": "user", "content": prompt},
        ],
        temperature=0.7,
        max_tokens=4096,
    )
    return response.choices[0].message.content


# ---------------------------------------------------------------------------
# Main research runner
# ---------------------------------------------------------------------------

def run_research(use_browser: bool = True) -> dict:
    tz = timezone(timedelta(hours=8))
    print(f"[Research] 开始市场调研 {'(Gemini 网页版)' if use_browser else '(API 直接调用)'}...")

    if use_browser:
        try:
            raw_text = run_gemini_research()
        except Exception as e:
            print(f"[Research] Gemini 浏览器调用失败: {e}")
            print("[Research] 回退到 API 直接调用...")
            raw_text = call_api_fallback(RESEARCH_PROMPT)
            source = "api_fallback"
        else:
            source = "gemini_web"
    else:
        raw_text = call_api_fallback(RESEARCH_PROMPT)
        source = "api_direct"

    print("[Research] 解析 JSON...")
    result = parse_json(raw_text)
    result.setdefault("_meta", {})
    result["_meta"]["source"] = source
    result["_meta"]["timestamp"] = datetime.now(tz).strftime("%Y%m%d_%H%M%S")
    result["_meta"]["gemini_url"] = GEMINI_URL

    if not result.get("parse_error"):
        print("[Research] JSON 解析成功!")
    else:
        print("[Research] 警告：JSON 解析失败，返回原始文本")

    return result


def main():
    parser = argparse.ArgumentParser(description="市场调研（Gemini 网页版 / API 回退）")
    parser.add_argument("--output", "-o", help="输出文件路径")
    parser.add_argument("--no-browser", action="store_true", help="跳过浏览器，直接用 API")
    args = parser.parse_args()

    result = run_research(use_browser=not args.no_browser)
    output = json.dumps(result, ensure_ascii=False, indent=2)

    if args.output:
        out_path = Path(args.output)
    else:
        tz = timezone(timedelta(hours=8))
        date_str = datetime.now(tz).strftime("%Y%m%d")
        out_path = Path(__file__).parent.parent / "output" / "market_research" / f"research_{date_str}.json"

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(output, encoding="utf-8")
    print(f"[Research] 结果已保存到: {out_path}")


if __name__ == "__main__":
    main()
