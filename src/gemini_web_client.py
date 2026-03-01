"""
Gemini 网页版客户端
通过浏览器自动化调用 Gemini 网页版优化 prompt
"""

import json
import time
import re
from typing import Dict, Optional, Any
from datetime import datetime, timezone, timedelta

# Gemini 已登录会话 URL
GEMINI_SESSION_URL = "https://gemini.google.com/u/1/app"
GEMINI_TAB_ID = None  # 缓存 tab id，避免重复开启


def _get_browser():
    """延迟导入 browser 工具（运行时注入）"""
    try:
        from openclaw.tools import browser
        return browser
    except ImportError:
        return None


class GeminiWebClient:
    """
    Gemini 网页版客户端
    通过浏览器自动化生成/优化 prompt
    """

    def __init__(self, profile: str = "openclaw", timeout: int = 90):
        self.profile = profile
        self.timeout = timeout
        self._tab_id: Optional[str] = None

    def _ts(self) -> str:
        tz = timezone(timedelta(hours=8))
        return datetime.now(tz).isoformat()

    # ------------------------------------------------------------------
    # 浏览器操作
    # ------------------------------------------------------------------

    def _ensure_tab(self) -> Optional[str]:
        """确保 Gemini 标签页已打开，返回 tab_id"""
        global GEMINI_TAB_ID
        if self._tab_id:
            return self._tab_id

        try:
            from openclaw.runtime import call_tool
            # 检查现有 tabs
            tabs_result = call_tool("browser", {"action": "tabs", "profile": self.profile})
            tabs = tabs_result.get("tabs", []) if isinstance(tabs_result, dict) else []

            for tab in tabs:
                url = tab.get("url", "")
                if "gemini.google.com" in url:
                    self._tab_id = tab.get("id") or tab.get("targetId")
                    GEMINI_TAB_ID = self._tab_id
                    return self._tab_id

            # 没有找到，打开新标签
            open_result = call_tool("browser", {
                "action": "open",
                "profile": self.profile,
                "targetUrl": GEMINI_SESSION_URL
            })
            self._tab_id = (
                open_result.get("targetId")
                or open_result.get("id")
                if isinstance(open_result, dict) else None
            )
            time.sleep(3)
            GEMINI_TAB_ID = self._tab_id
            return self._tab_id

        except Exception as e:
            return None

    def _send_message(self, tab_id: str, text: str) -> bool:
        """向 Gemini 输入框发送消息"""
        try:
            from openclaw.runtime import call_tool

            # 点击输入框
            call_tool("browser", {
                "action": "act",
                "profile": self.profile,
                "targetId": tab_id,
                "request": {
                    "kind": "click",
                    "ref": "textarea",
                }
            })
            time.sleep(0.5)

            # 输入文本
            call_tool("browser", {
                "action": "act",
                "profile": self.profile,
                "targetId": tab_id,
                "request": {
                    "kind": "fill",
                    "ref": "textarea",
                    "text": text,
                }
            })
            time.sleep(0.5)

            # 提交
            call_tool("browser", {
                "action": "act",
                "profile": self.profile,
                "targetId": tab_id,
                "request": {
                    "kind": "press",
                    "key": "Enter",
                }
            })
            return True
        except Exception:
            return False

    def _wait_for_response(self, tab_id: str, max_wait: int = 60) -> Optional[str]:
        """等待 Gemini 响应完成，返回响应文本"""
        try:
            from openclaw.runtime import call_tool

            start = time.time()
            last_text = ""
            stable_count = 0

            while time.time() - start < max_wait:
                time.sleep(3)
                snapshot = call_tool("browser", {
                    "action": "snapshot",
                    "profile": self.profile,
                    "targetId": tab_id,
                })

                # 从快照中提取最新回复
                text = self._extract_latest_response(snapshot)

                if text and text == last_text:
                    stable_count += 1
                    if stable_count >= 2:  # 连续两次相同，认为生成完毕
                        return text
                else:
                    stable_count = 0
                    last_text = text

            return last_text or None

        except Exception:
            return None

    def _extract_latest_response(self, snapshot: Any) -> str:
        """从页面快照中提取最新的 Gemini 回复"""
        if not snapshot:
            return ""

        # snapshot 可能是 dict 或 str
        if isinstance(snapshot, dict):
            text = snapshot.get("text") or snapshot.get("content") or str(snapshot)
        else:
            text = str(snapshot)

        # 尝试找到最后一个 model-response 块
        # Gemini 的回复通常在特定的 aria role 里
        lines = text.split("\n")
        response_lines = []
        in_response = False

        for line in lines:
            if "model-response" in line.lower() or "response-content" in line.lower():
                in_response = True
            if in_response:
                response_lines.append(line)

        if response_lines:
            return "\n".join(response_lines)

        # 后备：返回最后 2000 字符
        return text[-2000:] if len(text) > 2000 else text

    # ------------------------------------------------------------------
    # 核心功能：优化 Shot Prompt
    # ------------------------------------------------------------------

    def optimize_shot_prompt(self, shot_info: Dict[str, Any]) -> str:
        """
        调用 Gemini 网页版优化单个 Shot 的 prompt

        Args:
            shot_info: 包含 shot_type, description, camera_motion, lighting 等的字典

        Returns:
            优化后的英文 prompt 字符串
        """
        prompt_text = self._build_optimization_prompt(shot_info)

        tab_id = self._ensure_tab()
        if not tab_id:
            # 无法打开浏览器，返回规则生成的 prompt
            return self._fallback_prompt(shot_info)

        sent = self._send_message(tab_id, prompt_text)
        if not sent:
            return self._fallback_prompt(shot_info)

        response = self._wait_for_response(tab_id, max_wait=self.timeout)
        if not response:
            return self._fallback_prompt(shot_info)

        # 从响应中提取 prompt
        extracted = self._extract_prompt_from_response(response)
        return extracted if extracted else self._fallback_prompt(shot_info)

    def optimize_prompts_batch(self, shots_info: list) -> list:
        """
        批量优化多个 Shot 的 prompt（复用同一个 Gemini 会话）

        Args:
            shots_info: Shot 信息列表

        Returns:
            优化后的 prompt 列表
        """
        results = []
        tab_id = self._ensure_tab()

        for shot in shots_info:
            if tab_id:
                prompt_text = self._build_optimization_prompt(shot)
                sent = self._send_message(tab_id, prompt_text)
                if sent:
                    response = self._wait_for_response(tab_id, max_wait=45)
                    extracted = self._extract_prompt_from_response(response) if response else None
                    results.append(extracted if extracted else self._fallback_prompt(shot))
                else:
                    results.append(self._fallback_prompt(shot))
            else:
                results.append(self._fallback_prompt(shot))

        return results

    def _build_optimization_prompt(self, shot_info: Dict[str, Any]) -> str:
        """构建发给 Gemini 的优化请求 - 包含剧本具体内容"""
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
        """从 Gemini 响应中提取 prompt 文本"""
        if not response:
            return None

        # 清理响应文本
        lines = [l.strip() for l in response.strip().split("\n") if l.strip()]

        # 过滤掉 UI 元素和无关内容
        skip_patterns = [
            "model-response", "response-content", "gemini", "google",
            "copy", "share", "thumbs", "button", "input", "textarea",
            "prompt:", "here is", "here's", "certainly", "sure,"
        ]

        content_lines = []
        for line in lines:
            lower = line.lower()
            if any(p in lower for p in skip_patterns):
                continue
            if len(line) > 20:  # 过滤太短的行
                content_lines.append(line)

        if not content_lines:
            return None

        # 取最长的一行（通常是 prompt）
        best = max(content_lines, key=len)

        # 如果包含逗号分隔的短语，很可能是 prompt
        if "," in best and len(best) > 50:
            return best

        # 否则合并前几行
        return ", ".join(content_lines[:3]) if content_lines else None

    def _fallback_prompt(self, shot_info: Dict[str, Any]) -> str:
        """无法调用 Gemini 时的后备 prompt 生成"""
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
    # 剧本生成（原有功能保留）
    # ------------------------------------------------------------------

    def generate_script(self, prompt: str, require_json: bool = True) -> Dict[str, Any]:
        """生成剧本"""
        full_prompt = self._build_script_prompt(prompt, require_json)

        tab_id = self._ensure_tab()
        if not tab_id:
            return {
                "source": "gemini_web",
                "status": "browser_unavailable",
                "prompt": full_prompt,
                "timestamp": self._ts(),
            }

        sent = self._send_message(tab_id, full_prompt)
        if not sent:
            return {"source": "gemini_web", "status": "send_failed", "timestamp": self._ts()}

        response = self._wait_for_response(tab_id)
        if not response:
            return {"source": "gemini_web", "status": "timeout", "timestamp": self._ts()}

        # 尝试解析 JSON
        result = self._try_parse_json(response)
        return {
            "source": "gemini_web",
            "status": "success",
            "timestamp": self._ts(),
            "raw": response,
            "data": result,
        }

    def _build_script_prompt(self, user_prompt: str, require_json: bool) -> str:
        if require_json:
            return f"""{user_prompt}

要求：
1. 包含角色对白
2. 有情节冲突
3. 输出JSON格式：{{"title": "标题", "scenes": [{{"scene": 1, "content": "场景描述", "dialogue": "对白"}}]}}"""
        return user_prompt

    def _try_parse_json(self, text: str) -> Optional[Dict]:
        """尝试从文本中提取 JSON"""
        # 找 ```json ... ``` 块
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except Exception:
                pass

        # 直接找 { ... }
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except Exception:
                pass

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
4. 输出JSON格式：{{"title": "标题", "scenes": [{{"scene": 1, "content": "场景描述", "dialogue": "对白"}}]}}"""
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
