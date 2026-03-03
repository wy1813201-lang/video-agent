"""Story Bible 管理器

功能：
- 读取/初始化 story_bible.json
- 构建给 LLM 的连载上下文
- 每集生成后自动写入摘要
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Dict, Any, List, Tuple


class StoryBibleManager:
    def __init__(self, path: str = "data/story_bible.json"):
        self.path = path
        self._ensure_parent()
        self.data = self._load_or_init()

    def _ensure_parent(self) -> None:
        parent = os.path.dirname(self.path)
        if parent:
            os.makedirs(parent, exist_ok=True)

    def _default_data(self) -> Dict[str, Any]:
        now = datetime.now().isoformat()
        return {
            "global_setting": {
                "title": "",
                "genre": "",
                "target_audience": "",
                "total_episodes": 0,
                "characters": [],
            },
            "plot_outline": [
                {"phase": 1, "name": "开头", "episodes": "1-5", "summary": ""},
                {"phase": 2, "name": "发展", "episodes": "6-15", "summary": ""},
                {"phase": 3, "name": "高潮", "episodes": "16-20", "summary": ""},
                {"phase": 4, "name": "结局", "episodes": "21-25", "summary": ""},
            ],
            "episode_summaries": [],
            "character_profiles": {},
            "world_rules": {},
            "created_at": now,
            "updated_at": now,
        }

    def _load_or_init(self) -> Dict[str, Any]:
        if os.path.exists(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    data.setdefault("episode_summaries", [])
                    data.setdefault("character_profiles", {})
                    data.setdefault("world_rules", {})
                    data.setdefault("plot_outline", [])
                    data.setdefault("global_setting", {})
                    data.setdefault("created_at", datetime.now().isoformat())
                    data.setdefault("updated_at", datetime.now().isoformat())
                    return data
            except Exception:
                pass

        data = self._default_data()
        self._save(data)
        return data

    def _save(self, data: Dict[str, Any]) -> None:
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.path)

    def save(self) -> None:
        self.data["updated_at"] = datetime.now().isoformat()
        self._save(self.data)

    def set_series_meta(self, title: str, total_episodes: int, genre: str = "") -> None:
        global_setting = self.data.setdefault("global_setting", {})
        if title and not global_setting.get("title"):
            global_setting["title"] = title
        if total_episodes:
            global_setting["total_episodes"] = total_episodes
        if genre and not global_setting.get("genre"):
            global_setting["genre"] = genre

    def build_context_for_episode(self, episode_num: int, max_history: int = 5) -> str:
        global_setting = self.data.get("global_setting", {})
        episodes: List[Dict[str, Any]] = self.data.get("episode_summaries", [])
        history = [e for e in episodes if int(e.get("episode", 0) or 0) < episode_num]
        history = history[-max_history:]

        lines = [
            "世界观与主设定：",
            json.dumps(global_setting, ensure_ascii=False),
        ]

        if self.data.get("world_rules"):
            lines.append("世界规则：")
            lines.append(json.dumps(self.data.get("world_rules", {}), ensure_ascii=False))

        if self.data.get("character_profiles"):
            lines.append("角色档案：")
            lines.append(json.dumps(self.data.get("character_profiles", {}), ensure_ascii=False))

        if history:
            lines.append("最近已播剧情摘要：")
            for item in history:
                ep = item.get("episode")
                summary = item.get("summary", "")
                ending = item.get("ending_hook", "")
                lines.append(f"- 第{ep}集：{summary}")
                if ending:
                    lines.append(f"  结尾钩子：{ending}")

        return "\n".join(lines)

    def update_after_episode(self, episode_num: int, script_text: str) -> None:
        summary, ending_hook = self._summarize_script(script_text)
        entry = {
            "episode": episode_num,
            "summary": summary,
            "ending_hook": ending_hook,
            "updated_at": datetime.now().isoformat(),
        }

        episodes: List[Dict[str, Any]] = self.data.setdefault("episode_summaries", [])
        found = False
        for idx, item in enumerate(episodes):
            if int(item.get("episode", 0) or 0) == episode_num:
                episodes[idx] = entry
                found = True
                break
        if not found:
            episodes.append(entry)
            episodes.sort(key=lambda x: int(x.get("episode", 0) or 0))

        self._update_character_hints(script_text, episode_num)
        self.save()

    def _summarize_script(self, script_text: str) -> Tuple[str, str]:
        lines = [ln.strip() for ln in (script_text or "").splitlines() if ln.strip()]
        content_lines = [
            ln for ln in lines if not ln.startswith("第") and not ln.startswith("场景")
        ]
        summary = "；".join(content_lines[:4])
        if len(summary) > 220:
            summary = summary[:220] + "..."

        ending = ""
        if content_lines:
            ending = content_lines[-1]
            if len(ending) > 80:
                ending = ending[:80] + "..."

        return (summary or "本集暂无摘要"), ending

    def _update_character_hints(self, script_text: str, episode_num: int) -> None:
        profiles = self.data.setdefault("character_profiles", {})
        chars = self.data.setdefault("global_setting", {}).setdefault("characters", [])

        for raw in (script_text or "").splitlines():
            s = raw.strip()
            if not s:
                continue
            if "：" not in s and ":" not in s:
                continue
            name = s.replace("：", ":", 1).split(":", 1)[0].strip()
            if not name:
                continue
            if len(name) > 8 or any(k in name for k in ["场景", "旁白", "字幕"]):
                continue

            if name not in chars:
                chars.append(name)
            if name not in profiles:
                profiles[name] = {
                    "latest_trait_hint": "",
                    "latest_episode_seen": 0,
                }
            profiles[name]["latest_episode_seen"] = max(
                int(profiles[name].get("latest_episode_seen", 0) or 0),
                int(episode_num),
            )
