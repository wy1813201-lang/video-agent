"""
市场调研模块
调用 Gemini 网页版搜索调研主流网文平台畅销榜，
分析热门作品爆点、受众画像、叙事节奏，
输出结构化竞品分析报告。
"""

import json
import os
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional


RESEARCH_PROMPT = """请调用搜索功能，深入调研番茄、起点或晋江等主流网文平台近一个月的畅销榜、飙升榜前十名的作品。

竞品分析：分析这些热门作品的核心爆点（如：逆袭、马甲、虐恋重生等）、受众画像及叙事节奏。

剧本创作参考：基于上述调研结果，提炼出最具市场潜力的题材，给出短剧创作建议。

请以 JSON 格式输出，结构如下：
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

只输出 JSON，不要其他文字。"""


class MarketResearcher:
    """
    市场调研器
    通过 Gemini 网页版搜索调研网文平台热门作品，
    生成结构化竞品分析报告。
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Args:
            config: market_research 配置块，来自 api_keys.json
        """
        self.config = config or {}
        self.enabled = self.config.get("enabled", True)
        self.output_dir = self.config.get("output_dir", "output/market_research")
        self.cache_hours = self.config.get("cache_hours", 24)
        self._ensure_output_dir()

    def _ensure_output_dir(self):
        os.makedirs(self.output_dir, exist_ok=True)

    def _get_timestamp(self) -> str:
        tz = timezone(timedelta(hours=8))
        return datetime.now(tz).strftime("%Y%m%d_%H%M%S")

    def _get_cache_path(self) -> str:
        tz = timezone(timedelta(hours=8))
        date_str = datetime.now(tz).strftime("%Y%m%d")
        return os.path.join(self.output_dir, f"research_{date_str}.json")

    def _load_cache(self) -> Optional[Dict[str, Any]]:
        """加载当日缓存，避免重复调研"""
        cache_path = self._get_cache_path()
        if not os.path.exists(cache_path):
            return None
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            print(f"[MarketResearcher] 使用缓存调研结果: {cache_path}")
            return data
        except Exception:
            return None

    def _save_result(self, result: Dict[str, Any]) -> str:
        """保存调研结果，同时写入带时间戳的文件和当日缓存"""
        ts = self._get_timestamp()
        # 带时间戳的完整记录
        full_path = os.path.join(self.output_dir, f"research_{ts}.json")
        with open(full_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        # 当日缓存（供同日复用）
        cache_path = self._get_cache_path()
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"[MarketResearcher] 调研结果已保存: {full_path}")
        return full_path

    def _parse_json_from_text(self, text: str) -> Dict[str, Any]:
        """从模型回答中提取 JSON"""
        # 尝试直接解析
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        # 尝试提取 ```json ... ``` 块
        import re
        match = re.search(r"```(?:json)?\s*([\s\S]+?)```", text)
        if match:
            try:
                return json.loads(match.group(1).strip())
            except json.JSONDecodeError:
                pass
        # 尝试找第一个 { ... } 块
        match = re.search(r"(\{[\s\S]+\})", text)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
        # 解析失败，返回原始文本包装
        return {"raw_text": text, "parse_error": True}

    async def research(self, use_cache: bool = True) -> Dict[str, Any]:
        """
        执行市场调研

        Args:
            use_cache: 是否使用当日缓存（默认 True，避免重复调用）

        Returns:
            结构化调研报告 dict
        """
        if not self.enabled:
            print("[MarketResearcher] 市场调研已禁用，跳过")
            return self._fallback_report()

        if use_cache:
            cached = self._load_cache()
            if cached:
                return cached

        print("[MarketResearcher] 开始市场调研（通过 Gemini 网页版）...")

        try:
            result = await self._call_gemini_web()
        except Exception as e:
            print(f"[MarketResearcher] Gemini 调研失败: {e}，使用内置默认报告")
            result = self._fallback_report()

        result["_meta"] = {
            "source": result.get("_meta", {}).get("source", "gemini_web"),
            "generated_at": self._get_timestamp(),
        }
        self._save_result(result)
        return result

    async def _call_gemini_web(self) -> Dict[str, Any]:
        """
        调用 Gemini 网页版调研
        注意：由于 Playwright 自动化在部分环境有兼容性问题，
        如果调用失败会自动 fallback 到缓存或默认报告
        """
        # 先检查是否有可用的缓存
        cached = self._load_cache()
        if cached and not cached.get("parse_error"):
            print("[MarketResearcher] 使用现有缓存")
            return cached
        
        # 尝试使用自动化脚本
        script_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "scripts", "gemini_automation.py"
        )

        if not os.path.exists(script_path):
            print("[MarketResearcher] 自动化脚本未找到，使用默认报告")
            return self._fallback_report()

        # 检查 playwright 是否安装
        try:
            import playwright
        except ImportError:
            print("[MarketResearcher] playwright 未安装，使用默认报告")
            return self._fallback_report()

        print("[MarketResearcher] 启动自动化调研...")
        print("[MarketResearcher] 注意：如果自动化失败，会自动使用默认报告")

        try:
            import subprocess
            proc = await asyncio.create_subprocess_exec(
                "python3", script_path,
                "--output", "/tmp/gemini_research_result.json",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            
            # 等待脚本完成（最多 120 秒）
            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
            except asyncio.TimeoutError:
                proc.kill()
                print("[MarketResearcher] 调研超时，使用默认报告")
                return self._fallback_report()

            # 读取结果
            result_path = "/tmp/gemini_research_result.json"
            if os.path.exists(result_path):
                with open(result_path, "r", encoding="utf-8") as f:
                    result = json.load(f)
                
                # 清理临时文件
                try:
                    os.remove(result_path)
                except:
                    pass

                if result.get("error"):
                    print(f"[MarketResearcher] 自动化失败: {result.get('error')}，使用默认报告")
                    return self._fallback_report()
                
                result.setdefault("_meta", {})["source"] = "gemini_web_automated"
                return result
            
        except Exception as e:
            print(f"[MarketResearcher] 调用异常: {e}，使用默认报告")
        
        return self._fallback_report()

    def _fallback_report(self) -> Dict[str, Any]:
        """内置默认调研报告（当调研不可用时使用）"""
        return {
            "research_date": datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d"),
            "platforms": ["番茄小说", "起点中文网", "晋江文学城"],
            "top_works": [
                {
                    "title": "重生归来复仇记",
                    "platform": "番茄小说",
                    "genre": "重生复仇",
                    "core_hooks": ["重生", "复仇", "逆袭"],
                    "audience": "18-35岁女性，偏好爽文情节",
                    "narrative_pace": "快节奏，每章必有反转",
                    "rank": 1,
                },
                {
                    "title": "豪门马甲大小姐",
                    "platform": "晋江文学城",
                    "genre": "马甲文",
                    "core_hooks": ["马甲", "豪门", "打脸"],
                    "audience": "20-30岁女性，喜欢反差萌",
                    "narrative_pace": "前期隐忍，中期爆发，高潮密集",
                    "rank": 2,
                },
                {
                    "title": "虐恋成瘾",
                    "platform": "起点中文网",
                    "genre": "虐恋",
                    "core_hooks": ["虐恋", "误会", "破镜重圆"],
                    "audience": "25-40岁女性，情感需求强烈",
                    "narrative_pace": "情绪波动大，虐点密集",
                    "rank": 3,
                },
            ],
            "trend_analysis": {
                "dominant_genres": ["重生复仇", "马甲文", "虐恋", "逆袭爽文"],
                "top_hooks": ["重生/穿越", "马甲/隐藏身份", "逆袭打脸", "虐恋反转", "豪门秘辛"],
                "audience_profile": "主力受众18-35岁女性，追求情绪爽感和代入感，偏好强反差、高密度情节",
                "narrative_trends": "前三分钟必须建立冲突或悬念，每集结尾留钩子，情绪曲线呈W型",
            },
            "script_recommendations": {
                "recommended_genre": "重生复仇+马甲隐藏身份",
                "recommended_hooks": ["重生逆袭", "马甲揭露", "情感反转"],
                "opening_strategy": "第1分钟展示主角受辱/绝境，第2分钟触发重生/觉醒，第3分钟完成第一次反击，制造情绪高峰",
                "commercial_tips": "前3秒必须有视觉冲击或台词钩子，每90秒设置一个小高潮，结尾留悬念引导追剧",
            },
            "_meta": {
                "source": "fallback",
                "generated_at": datetime.now(timezone(timedelta(hours=8))).strftime("%Y%m%d_%H%M%S"),
            },
        }

    def format_for_prompt(self, report: Dict[str, Any]) -> str:
        """
        将调研报告格式化为可注入 prompt 的文本摘要

        Args:
            report: research() 返回的报告 dict

        Returns:
            适合嵌入 prompt 的简洁文本
        """
        if report.get("parse_error"):
            return f"市场调研原始数据：\n{report.get('raw_text', '')[:500]}"

        trend = report.get("trend_analysis", {})
        rec = report.get("script_recommendations", {})

        lines = [
            "=== 市场调研结果（近一个月网文平台热榜） ===",
            f"热门题材：{', '.join(trend.get('dominant_genres', []))}",
            f"核心爆点：{', '.join(trend.get('top_hooks', []))}",
            f"受众画像：{trend.get('audience_profile', '')}",
            f"叙事趋势：{trend.get('narrative_trends', '')}",
            "",
            "=== 剧本创作建议 ===",
            f"推荐题材：{rec.get('recommended_genre', '')}",
            f"推荐爆点：{', '.join(rec.get('recommended_hooks', []))}",
            f"前三分钟策略：{rec.get('opening_strategy', '')}",
            f"商业转化建议：{rec.get('commercial_tips', '')}",
            "=" * 40,
        ]
        return "\n".join(lines)
