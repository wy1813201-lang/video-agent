"""
Gemini 网页版客户端
通过浏览器自动化调用 Gemini 网页版优化 prompt / 生成剧本。

说明：
- 仅浏览器对话，不依赖 Gemini API
- 内置会话复用、失败重试、本地缓存、JSON 解析兜底
"""

import asyncio
import hashlib
import json
import os
import re
import time
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

# Gemini 已登录会话 URL
GEMINI_SESSION_URL = "https://gemini.google.com/u/1/app"
GEMINI_TAB_ID = None  # 缓存 tab id，避免重复开启


class GeminiWebClient:
    """Gemini 网页版客户端（浏览器自动化）"""

    def __init__(
        self,
        profile: str = "openclaw",
        timeout: int = 90,
        headless: Optional[bool] = None,
        timeout_ms: Optional[int] = None,
        gemini_url: Optional[str] = None,
        cache_dir: str = "data/storage/gemini_web_cache",
        max_cache_entries: int = 500,
    ):
        # 兼容旧调用参数（headless 由外层浏览器工具决定，这里保留但不使用）
        _ = headless
        self.profile = profile
        self.timeout = max(10, int((timeout_ms or (timeout * 1000)) / 1000))
        self.gemini_url = gemini_url or GEMINI_SESSION_URL
        self._tab_id: Optional[str] = None

        self.cache_dir = cache_dir
        self.max_cache_entries = max(10, int(max_cache_entries))
        os.makedirs(self.cache_dir, exist_ok=True)
        self.cache_path = os.path.join(self.cache_dir, "script_cache.json")

    def _ts(self) -> str:
        tz = timezone(timedelta(hours=8))
        return datetime.now(tz).isoformat()

    # ------------------------------------------------------------------
    # Browser low-level helpers
    # ------------------------------------------------------------------

    def _call_browser(self, payload: Dict[str, Any]) -> Any:
        from openclaw.runtime import call_tool

        return call_tool("browser", payload)

    def _snapshot_text(self, snapshot: Any) -> str:
        if not snapshot:
            return ""
        if isinstance(snapshot, dict):
            text = snapshot.get("text") or snapshot.get("content") or snapshot.get("html") or ""
            if not text:
                text = json.dumps(snapshot, ensure_ascii=False)
            return str(text)
        return str(snapshot)

    def _is_tab_alive(self, tab_id: str) -> bool:
        try:
            snapshot = self._call_browser({
                "action": "snapshot",
                "profile": self.profile,
                "targetId": tab_id,
            })
            text = self._snapshot_text(snapshot)
            return bool(text)
        except Exception:
            return False

    def _ensure_tab(self, force_reopen: bool = False) -> Optional[str]:
        """确保 Gemini 标签页已打开，返回 tab_id"""
        global GEMINI_TAB_ID

        if force_reopen:
            self._tab_id = None

        # 先用实例缓存
        if self._tab_id and self._is_tab_alive(self._tab_id):
            return self._tab_id

        # 再用全局缓存
        if GEMINI_TAB_ID and self._is_tab_alive(GEMINI_TAB_ID):
            self._tab_id = GEMINI_TAB_ID
            return self._tab_id

        try:
            tabs_result = self._call_browser({"action": "tabs", "profile": self.profile})
            tabs = tabs_result.get("tabs", []) if isinstance(tabs_result, dict) else []
            for tab in tabs:
                url = tab.get("url", "")
                if "gemini.google.com" in url:
                    self._tab_id = tab.get("id") or tab.get("targetId")
                    GEMINI_TAB_ID = self._tab_id
                    return self._tab_id

            open_result = self._call_browser({
                "action": "open",
                "profile": self.profile,
                "targetUrl": self.gemini_url,
            })
            self._tab_id = (
                open_result.get("targetId")
                or open_result.get("id")
                if isinstance(open_result, dict)
                else None
            )
            time.sleep(2)
            GEMINI_TAB_ID = self._tab_id
            return self._tab_id
        except Exception:
            return None

    def _send_message(self, tab_id: str, text: str) -> bool:
        """向 Gemini 输入框发送消息"""
        try:
            self._call_browser({
                "action": "act",
                "profile": self.profile,
                "targetId": tab_id,
                "request": {"kind": "click", "ref": "textarea"},
            })
            time.sleep(0.2)

            self._call_browser({
                "action": "act",
                "profile": self.profile,
                "targetId": tab_id,
                "request": {"kind": "fill", "ref": "textarea", "text": text},
            })
            time.sleep(0.2)

            self._call_browser({
                "action": "act",
                "profile": self.profile,
                "targetId": tab_id,
                "request": {"kind": "press", "key": "Enter"},
            })
            return True
        except Exception:
            return False

    def _extract_latest_response(self, snapshot: Any) -> str:
        """从页面快照中提取最新回复文本"""
        text = self._snapshot_text(snapshot)
        if not text:
            return ""

        # 优先提取最后一个 model-response 块
        low = text.lower()
        if "model-response" in low:
            idx = low.rfind("model-response")
            if idx >= 0:
                return text[idx:]

        # 后备：截取尾部，减少 UI 噪声
        return text[-8000:] if len(text) > 8000 else text

    def _wait_for_response(self, tab_id: str, max_wait: int = 60) -> Optional[str]:
        """等待 Gemini 响应完成，返回响应文本"""
        start = time.time()
        last_text = ""
        stable_count = 0
        best_text = ""

        while time.time() - start < max_wait:
            time.sleep(2)
            try:
                snapshot = self._call_browser({
                    "action": "snapshot",
                    "profile": self.profile,
                    "targetId": tab_id,
                })
            except Exception:
                continue

            text = self._extract_latest_response(snapshot).strip()
            if not text:
                continue

            best_text = text
            if text == last_text:
                stable_count += 1
                # 连续 3 次稳定，降低截断概率
                if stable_count >= 3:
                    return text
            else:
                stable_count = 0
                last_text = text

        return best_text or None

    def _request_text(self, prompt: str, max_wait: Optional[int] = None, retries: int = 2) -> Optional[str]:
        wait_seconds = int(max_wait or self.timeout)
        for i in range(retries + 1):
            tab_id = self._ensure_tab(force_reopen=(i > 0))
            if not tab_id:
                continue
            if not self._send_message(tab_id, prompt):
                continue
            response = self._wait_for_response(tab_id, max_wait=wait_seconds)
            if response:
                return response
        return None

    # ------------------------------------------------------------------
    # Local cache helpers (browser-only替代缓存)
    # ------------------------------------------------------------------

    def _load_cache(self) -> Dict[str, Any]:
        if not os.path.exists(self.cache_path):
            return {"version": 1, "entries": {}}
        try:
            with open(self.cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return {"version": 1, "entries": {}}
            if "entries" not in data or not isinstance(data["entries"], dict):
                data["entries"] = {}
            return data
        except Exception:
            return {"version": 1, "entries": {}}

    def _save_cache(self, data: Dict[str, Any]) -> None:
        entries = data.get("entries", {})
        if len(entries) > self.max_cache_entries:
            sorted_items = sorted(
                entries.items(),
                key=lambda kv: kv[1].get("updated_at", ""),
                reverse=True,
            )
            entries = dict(sorted_items[: self.max_cache_entries])
            data["entries"] = entries

        tmp = self.cache_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.cache_path)

    def _cache_key(self, full_prompt: str, require_json: bool) -> str:
        base = f"json={int(require_json)}\n{full_prompt.strip()}"
        return hashlib.sha256(base.encode("utf-8")).hexdigest()

    def _cache_get(self, full_prompt: str, require_json: bool) -> Optional[Dict[str, Any]]:
        data = self._load_cache()
        entry = data.get("entries", {}).get(self._cache_key(full_prompt, require_json))
        if not isinstance(entry, dict):
            return None
        return entry.get("result") if isinstance(entry.get("result"), dict) else None

    def _cache_set(self, full_prompt: str, require_json: bool, result: Dict[str, Any]) -> None:
        data = self._load_cache()
        key = self._cache_key(full_prompt, require_json)
        data.setdefault("entries", {})[key] = {
            "updated_at": self._ts(),
            "result": result,
            "preview": full_prompt[:120],
        }
        self._save_cache(data)

    # ------------------------------------------------------------------
    # 核心功能：优化 Shot Prompt
    # ------------------------------------------------------------------

    def optimize_shot_prompt(self, shot_info: Dict[str, Any]) -> str:
        """调用 Gemini 网页版优化单个 Shot 的 prompt"""
        prompt_text = self._build_optimization_prompt(shot_info)
        response = self._request_text(prompt_text, max_wait=self.timeout, retries=2)
        if not response:
            return self._fallback_prompt(shot_info)

        extracted = self._extract_prompt_from_response(response)
        return extracted if extracted else self._fallback_prompt(shot_info)

    def optimize_prompts_batch(self, shots_info: List[Dict[str, Any]]) -> List[str]:
        """批量优化多个 Shot 的 prompt（复用同一个 Gemini 会话）"""
        results = []
        for shot in shots_info:
            prompt_text = self._build_optimization_prompt(shot)
            response = self._request_text(prompt_text, max_wait=45, retries=1)
            extracted = self._extract_prompt_from_response(response) if response else None
            results.append(extracted if extracted else self._fallback_prompt(shot))
        return results

    def _build_optimization_prompt(self, shot_info: Dict[str, Any]) -> str:
        return f"""You are a professional cinematographer and AI video prompt engineer.

Optimize this shot into a high-quality English prompt for AI video generation.

SCRIPT SCENE INFO:
- Location: {shot_info.get('scene_location', '')}
- Description: {shot_info.get('description', '')}
- Character: {shot_info.get('character', '')}
- Action: {shot_info.get('action', '')}

SHOT TECHNICAL INFO:
- Shot type: {shot_info.get('shot_type', 'medium')}
- Camera motion: {shot_info.get('camera_motion', '')}
- Camera angle: {shot_info.get('camera_angle', '')}
- Lighting: {shot_info.get('lighting', '')}
- Mood: {shot_info.get('mood', '')}

Requirements:
1. Output ONLY the prompt text in English
2. Must include: character, action, environment, camera movement
3. Keep script details (clothing, expression, props)
4. Max 50 words
5. Format: comma-separated descriptive phrases

Prompt:"""

    def _extract_prompt_from_response(self, response: str) -> Optional[str]:
        if not response:
            return None

        lines = [l.strip() for l in response.strip().split("\n") if l.strip()]
        skip_patterns = [
            "model-response", "response-content", "gemini", "google",
            "copy", "share", "thumbs", "button", "input", "textarea",
            "prompt:", "here is", "here's", "certainly", "sure,",
        ]

        content_lines = []
        for line in lines:
            lower = line.lower()
            if any(p in lower for p in skip_patterns):
                continue
            if len(line) > 20:
                content_lines.append(line)

        if not content_lines:
            return None

        best = max(content_lines, key=len)
        if "," in best and len(best) > 40:
            return best
        return ", ".join(content_lines[:3]) if content_lines else None

    def _fallback_prompt(self, shot_info: Dict[str, Any]) -> str:
        parts = [
            shot_info.get("description", "cinematic shot"),
            f"in {shot_info.get('scene_location', 'scene')}" if shot_info.get("scene_location") else "",
            shot_info.get("camera_motion", ""),
            shot_info.get("camera_angle", ""),
            shot_info.get("lens_type", ""),
            shot_info.get("lighting", ""),
            shot_info.get("mood", ""),
            "cinematic quality, 4k, film grain, high detail",
        ]
        return ", ".join(p for p in parts if p)

    # ------------------------------------------------------------------
    # 剧本生成
    # ------------------------------------------------------------------

    def generate_script(
        self,
        prompt: str,
        require_json: bool = True,
        use_cache: bool = True,
        max_retries: int = 2,
        return_meta: bool = False,
    ) -> Dict[str, Any]:
        """生成剧本。

        默认返回标准化剧本结构：
        {"title": str, "summary": str, "scenes": [{"location":..., "description":..., "dialogues":[...]}]}
        """
        full_prompt = self._build_script_prompt(prompt, require_json)

        if use_cache:
            cached = self._cache_get(full_prompt, require_json)
            if cached:
                if return_meta:
                    return {
                        "source": "gemini_web",
                        "status": "success_cache",
                        "timestamp": self._ts(),
                        "data": cached,
                    }
                return cached

        response = self._request_text(full_prompt, max_wait=self.timeout, retries=max_retries)
        if not response:
            fallback = {
                "title": "生成失败（浏览器不可用）",
                "summary": "",
                "scenes": [],
            }
            if return_meta:
                return {
                    "source": "gemini_web",
                    "status": "timeout",
                    "timestamp": self._ts(),
                    "data": fallback,
                }
            return fallback

        parsed = self._parse_script_response(response)
        if use_cache:
            self._cache_set(full_prompt, require_json, parsed)

        if return_meta:
            return {
                "source": "gemini_web",
                "status": "success",
                "timestamp": self._ts(),
                "raw": response,
                "data": parsed,
            }
        return parsed

    async def generate_script_async(
        self,
        prompt: str,
        require_json: bool = True,
        use_cache: bool = True,
        max_retries: int = 2,
        return_meta: bool = False,
    ) -> Dict[str, Any]:
        return await asyncio.to_thread(
            self.generate_script,
            prompt,
            require_json,
            use_cache,
            max_retries,
            return_meta,
        )

    async def close(self):
        """兼容异步资源释放接口（当前浏览器会话由运行时托管）。"""
        return None

    def _build_script_prompt(self, user_prompt: str, require_json: bool) -> str:
        if require_json:
            return f"""{user_prompt}

要求：
1. 只输出 JSON，不要输出 markdown 代码块
2. 包含角色对白和情节冲突
3. 输出结构：
{{
  "title": "标题",
  "summary": "本集梗概",
  "scenes": [
    {{
      "scene": 1,
      "location": "场景地点",
      "description": "场景描述",
      "dialogues": [{{"speaker": "角色", "line": "台词"}}]
    }}
  ]
}}"""
        return user_prompt

    def _parse_script_response(self, text: str) -> Dict[str, Any]:
        parsed = self._try_parse_json(text)
        if parsed:
            return self._normalize_script_payload(parsed)

        # 兜底：无法解析时用文本降级
        return {
            "title": "未命名剧本",
            "summary": "",
            "scenes": [
                {
                    "scene": 1,
                    "location": "未知地点",
                    "description": text[:500],
                    "dialogues": [],
                }
            ],
        }

    def _normalize_script_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        # 兼容旧格式：{"source":..., "data": {...}}
        if isinstance(payload.get("data"), dict):
            payload = payload["data"]

        title = str(payload.get("title") or "未命名剧本")
        summary = str(payload.get("summary") or "")
        raw_scenes = payload.get("scenes")
        scenes_out: List[Dict[str, Any]] = []

        if not isinstance(raw_scenes, list):
            raw_scenes = []

        for idx, scene in enumerate(raw_scenes, start=1):
            if not isinstance(scene, dict):
                continue
            scene_no = scene.get("scene") or idx
            location = str(scene.get("location") or scene.get("scene_location") or "未知地点")
            description = str(scene.get("description") or scene.get("content") or "")

            dialogues_out: List[Dict[str, str]] = []
            raw_dialogues = scene.get("dialogues")
            if isinstance(raw_dialogues, list):
                for d in raw_dialogues:
                    if isinstance(d, dict):
                        spk = str(d.get("speaker") or "角色")
                        line = str(d.get("line") or d.get("text") or "")
                        if line:
                            dialogues_out.append({"speaker": spk, "line": line})
                    elif isinstance(d, str) and d.strip():
                        dialogues_out.append({"speaker": "角色", "line": d.strip()})

            # 兼容旧字段：dialogue（单行）
            if not dialogues_out:
                single = scene.get("dialogue")
                if isinstance(single, str) and single.strip():
                    dialogues_out.append({"speaker": "角色", "line": single.strip()})

            scenes_out.append(
                {
                    "scene": scene_no,
                    "location": location,
                    "description": description,
                    "dialogues": dialogues_out,
                }
            )

        return {
            "title": title,
            "summary": summary,
            "scenes": scenes_out,
        }

    def _try_parse_json(self, text: str) -> Optional[Dict[str, Any]]:
        if not text:
            return None

        # 1) ```json ... ```
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except Exception:
                pass

        # 2) 直接 parse 整体
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass

        # 3) 提取首尾花括号
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            chunk = text[start : end + 1]
            try:
                return json.loads(chunk)
            except Exception:
                # 尝试去掉尾逗号
                chunk = re.sub(r",\s*([}\]])", r"\1", chunk)
                try:
                    return json.loads(chunk)
                except Exception:
                    return None
        return None

    def generate_from_template(self, template: str = "romance", **kwargs) -> Dict[str, Any]:
        prompts = {
            "romance": "写一个1分钟的现代都市爱情短剧剧本",
            "suspense": "写一个1分钟的悬疑惊悚短剧剧本，高智商紧张刺激",
            "xianxia": "写一个1分钟的仙侠古风短剧剧本",
            "modern": "写一个1分钟的现代都市短剧剧本",
        }
        base_prompt = prompts.get(template, prompts["modern"])
        if kwargs:
            base_prompt += "，" + ", ".join(f"{k}={v}" for k, v in kwargs.items())
        return self.generate_script(base_prompt)

    def generate_novel_based_script(self, novel_theme: str, style: str = "suspense") -> Dict[str, Any]:
        prompt = f"""基于《{novel_theme}》的风格，写一个1分钟{style}短剧剧本。
要求：
1. 高智商悬疑
2. 紧张刺激
3. 有反转
4. 输出 JSON"""
        return self.generate_script(prompt)


# === 便捷函数 ===

def generate_script(prompt: str, site: str = "gemini") -> Dict[str, Any]:
    if site == "gemini":
        return GeminiWebClient().generate_script(prompt)
    raise ValueError(f"Unsupported site: {site}")


def generate_from_novel(novel_name: str, style: str = "suspense") -> Dict[str, Any]:
    return GeminiWebClient().generate_novel_based_script(novel_name, style)


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        result = generate_script(sys.argv[1])
    else:
        result = generate_from_novel("十日终焉", "悬疑")
    print(json.dumps(result, ensure_ascii=False, indent=2))
