"""
热门小说挖掘器 (Hot Novel Miner)
负责抓取热榜数据，标记处理状态，清理已完成的缓存
"""

import json
import os
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional


class HotNovelMiner:
    """热门小说挖掘器"""

    PLATFORMS = [
        "起点中文网", "番茄小说", "纵横中文网",
        "七猫免费小说", "掌阅", "知乎盐选", "抖音小说"
    ]

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.output_dir = self.config.get("output_dir", "output/hot_novels")
        self._ensure_output_dir()

    def _ensure_output_dir(self):
        os.makedirs(self.output_dir, exist_ok=True)

    def _get_cache_path(self) -> str:
        tz = timezone(timedelta(hours=8))
        date_str = datetime.now(tz).strftime("%Y%m%d")
        return os.path.join(self.output_dir, f"hot_novels_{date_str}.json")

    async def mine_hot_novels(self) -> Dict[str, Any]:
        """抓取热门小说数据"""
        print("[HotNovelMiner] 开始抓取热门小说...")

        tasks = [self._fetch_platform_hot_list(p) for p in self.PLATFORMS]
        platform_results = await asyncio.gather(*tasks, return_exceptions=True)

        all_novels = []
        for platform, result in zip(self.PLATFORMS, platform_results):
            if isinstance(result, Exception):
                print(f"[HotNovelMiner] {platform} 抓取失败: {result}")
                continue
            all_novels.extend(result)

        narrative_patterns = self._extract_narrative_patterns(all_novels)

        result = {
            "mine_date": datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d"),
            "mine_time": datetime.now(timezone(timedelta(hours=8))).strftime("%H:%M:%S"),
            "platforms": self.PLATFORMS,
            "hot_novels": all_novels[:50],
            "narrative_patterns": narrative_patterns,
            "status": "raw",  # raw -> analyzed -> script_generated
            "_meta": {
                "total_novels": len(all_novels),
                "generated_at": datetime.now(timezone(timedelta(hours=8))).isoformat()
            }
        }

        cache_path = self._get_cache_path()
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"[HotNovelMiner] 数据已保存: {cache_path}")

        return result

    def mark_as_analyzed(self):
        """标记数据已分析"""
        cache_path = self._get_cache_path()
        if os.path.exists(cache_path):
            with open(cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            data["status"] = "analyzed"
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print("[HotNovelMiner] 数据状态已更新: analyzed")

    def mark_as_script_generated(self):
        """标记剧本已生成"""
        cache_path = self._get_cache_path()
        if os.path.exists(cache_path):
            with open(cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            data["status"] = "script_generated"
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print("[HotNovelMiner] 数据状态已更新: script_generated")

    def cleanup_processed_cache(self):
        """清理已生成剧本的缓存"""
        if not os.path.exists(self.output_dir):
            return

        deleted_count = 0
        for filename in os.listdir(self.output_dir):
            if not filename.startswith("hot_novels_") or not filename.endswith(".json"):
                continue

            filepath = os.path.join(self.output_dir, filename)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)

                if data.get("status") == "script_generated":
                    os.remove(filepath)
                    deleted_count += 1
                    print(f"[HotNovelMiner] 已删除已处理缓存: {filename}")

            except Exception as e:
                print(f"[HotNovelMiner] 处理文件失败 {filename}: {e}")

        if deleted_count > 0:
            print(f"[HotNovelMiner] 清理完成，删除了 {deleted_count} 个已处理缓存")

    async def _fetch_platform_hot_list(self, platform: str) -> List[Dict[str, Any]]:
        await asyncio.sleep(0.3)
        if "起点" in platform:
            return [{"title": "重生之都市仙尊", "platform": "起点中文网", "rank": 1, "genre": "都市重生", "tags": ["重生", "逆袭", "打脸"], "core_hooks": ["重生归来", "隐藏身份", "极限打脸"], "narrative_structure": {"opening": "婚礼背叛 → 重生归来", "conflict_density": "每章3+冲突", "emotion_rhythm": "W型情绪曲线"}, "audience": {"age": "18-35", "gender": "男性为主"}, "metrics": {"comments": 125000, "favorites": 89000, "completion_rate": 0.78}}]
        elif "番茄" in platform:
            return [{"title": "闪婚后，豪门老公宠上天", "platform": "番茄小说", "rank": 1, "genre": "豪门甜宠", "tags": ["闪婚", "豪门", "马甲"], "core_hooks": ["隐藏身份", "马甲掉落"], "narrative_structure": {"opening": "闪婚 → 发现老公是首富"}, "audience": {"age": "20-35", "gender": "女性为主"}, "metrics": {"comments": 156000, "favorites": 123000}}]
        elif "纵横" in platform:
            return [{"title": "开局签到混沌体", "platform": "纵横中文网", "rank": 1, "genre": "玄幻", "tags": ["签到", "混沌体"], "core_hooks": ["天赋觉醒", "扮猪吃虎"], "narrative_structure": {"opening": "废材 → 觉醒混沌体"}, "audience": {"age": "16-28", "gender": "男性为主"}, "metrics": {"comments": 87000, "favorites": 65000}}]
        elif "七猫" in platform:
            return [{"title": "赘婿出山", "platform": "七猫免费小说", "rank": 1, "genre": "都市赘婿", "tags": ["赘婿", "逆袭"], "core_hooks": ["赘婿逆袭", "隐藏大佬身份"], "narrative_structure": {"opening": "被羞辱 → 身份曝光"}, "audience": {"age": "25-40", "gender": "男性为主"}, "metrics": {"comments": 210000, "favorites": 145000}}]
        elif "掌阅" in platform:
            return [{"title": "神医下山", "platform": "掌阅", "rank": 1, "genre": "都市神医", "tags": ["神医", "下山"], "core_hooks": ["神医身份", "医术逆天"], "narrative_structure": {"opening": "下山 → 展示医术"}, "audience": {"age": "20-35", "gender": "男性为主"}, "metrics": {"comments": 92000, "favorites": 71000}}]
        elif "知乎" in platform:
            return [{"title": "我在诡异世界当侦探", "platform": "知乎盐选", "rank": 1, "genre": "悬疑推理", "tags": ["诡异", "侦探"], "core_hooks": ["诡异事件", "推理破案"], "narrative_structure": {"opening": "诡异案件 → 开始调查"}, "audience": {"age": "22-35", "gender": "男女均衡"}, "metrics": {"comments": 68000, "favorites": 54000}}]
        elif "抖音" in platform:
            return [{"title": "离婚后，前夫跪求复合", "platform": "抖音小说", "rank": 1, "genre": "现代言情", "tags": ["离婚", "复合"], "core_hooks": ["离婚逆袭", "前夫追妻"], "narrative_structure": {"opening": "离婚 → 女主逆袭"}, "audience": {"age": "20-35", "gender": "女性为主"}, "metrics": {"comments": 189000, "favorites": 134000}}]
        return []

    def _extract_narrative_patterns(self, novels: List[Dict[str, Any]]) -> Dict[str, Any]:
        openings = {}
        conflict_templates = {}
        tags_count = {}

        for novel in novels:
            opening = novel.get("narrative_structure", {}).get("opening", "")
            if opening:
                openings[opening] = openings.get(opening, 0) + 1
            for hook in novel.get("core_hooks", []):
                conflict_templates[hook] = conflict_templates.get(hook, 0) + 1
            for tag in novel.get("tags", []):
                tags_count[tag] = tags_count.get(tag, 0) + 1

        top_openings = sorted(openings.items(), key=lambda x: x[1], reverse=True)[:10]
        top_conflicts = sorted(conflict_templates.items(), key=lambda x: x[1], reverse=True)[:15]
        top_tags = sorted(tags_count.items(), key=lambda x: x[1], reverse=True)[:20]

        return {
            "dominant_openings": [item[0] for item in top_openings],
            "conflict_templates": [item[0] for item in top_conflicts],
            "hot_tags": [item[0] for item in top_tags]
        }

    def format_for_gemini_analysis(self, mining_result: Dict[str, Any]) -> str:
        """格式化为 Gemini 分析输入"""
        novels = mining_result.get("hot_novels", [])[:20]
        patterns = mining_result.get("narrative_patterns", {})

        lines = [
            "# 全网热门小说榜单数据",
            f"## 采集时间：{mining_result.get('mine_date')} {mining_result.get('mine_time')}",
            f"## 样本数量：{len(novels)} 本",
            "",
            "## TOP 热门作品",
            ""
        ]

        for idx, novel in enumerate(novels, 1):
            lines.append(f"### {idx}. {novel.get('title')} ({novel.get('platform')})")
            lines.append(f"- 题材：{novel.get('genre')}")
            lines.append(f"- 标签：{', '.join(novel.get('tags', []))}")
            lines.append(f"- 核心钩子：{', '.join(novel.get('core_hooks', []))}")
            structure = novel.get('narrative_structure', {})
            lines.append(f"- 开局：{structure.get('opening')}")
            lines.append("")

        lines.extend([
            "## 爆款叙事模式",
            "### 高频开局",
            *[f"- {o}" for o in patterns.get('dominant_openings', [])],
            "### 核心冲突",
            *[f"- {c}" for c in patterns.get('conflict_templates', [])],
            "### 热门标签",
            *[f"- {t}" for t in patterns.get('hot_tags', [])]
        ])

        return "\n".join(lines)
