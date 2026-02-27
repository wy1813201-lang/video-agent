"""
可灵 AI (Kling) 视频生成客户端
https://klingai.com / https://api.klingai.com
"""

import asyncio
import json
import time
import requests
from pathlib import Path
from datetime import datetime

CONFIG_PATH = Path(__file__).parent.parent / "config" / "api_keys.json"


class KlingClient:
    """可灵 AI 视频/图像生成客户端"""

    BASE_URL = "https://api.klingai.com"

    def __init__(self):
        with open(CONFIG_PATH) as f:
            config = json.load(f)

        cfg = config.get("kling", config.get("video", {}).get("kling", {}))
        self.api_key = cfg.get("api_key", "")
        self.base_url = cfg.get("base_url", self.BASE_URL).rstrip("/")

        output_dir = cfg.get("output_dir", "~/Desktop/ShortDrama")
        self.output_dir = Path(output_dir).expanduser()

        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        })

    def _save_file(self, url: str, subdir: str, prefix: str, ext: str) -> Path:
        dest_dir = self.output_dir / subdir
        dest_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest = dest_dir / f"{prefix}_{timestamp}.{ext}"
        resp = requests.get(url, timeout=120)
        resp.raise_for_status()
        dest.write_bytes(resp.content)
        return dest

    def image_generation(self, prompt: str, negative_prompt: str = "",
                         aspect_ratio: str = "9:16", model: str = "kling-v1") -> dict:
        """
        文生图
        POST /v1/images/generations
        """
        payload = {
            "model": model,
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "aspect_ratio": aspect_ratio,
            "n": 1,
        }
        resp = self.session.post(f"{self.base_url}/v1/images/generations", json=payload, timeout=120)
        resp.raise_for_status()
        result = resp.json()

        try:
            image_url = result["data"][0]["url"]
            saved = self._save_file(image_url, "images", "kling_image", "jpg")
            result["saved_path"] = str(saved)
            print(f"[KlingClient] Image saved: {saved}")
        except Exception as e:
            print(f"[KlingClient] Warning: could not save image — {e}")

        return result

    async def text_to_video(self, prompt: str, negative_prompt: str = "",
                      duration: int = 5, aspect_ratio: str = "9:16",
                      model: str = "kling-v1-5",
                      poll: bool = True, max_wait: int = 300) -> dict:
        """
        文生视频
        POST /v1/videos/text2video
        """
        payload = {
            "model": model,
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "duration": duration,
            "aspect_ratio": aspect_ratio,
        }
        resp = self.session.post(f"{self.base_url}/v1/videos/text2video", json=payload, timeout=60)
        resp.raise_for_status()
        result = resp.json()

        if not poll:
            return result

        task_id = (result.get("data") or {}).get("task_id") or result.get("task_id")
        if not task_id:
            return result

        return await self._poll_video(task_id, max_wait)

    async def image_to_video(self, image_url: str, prompt: str = "",
                       duration: int = 5, model: str = "kling-v1-5",
                       poll: bool = True, max_wait: int = 300) -> dict:
        """
        图生视频
        POST /v1/videos/image2video
        """
        payload = {
            "model": model,
            "image_url": image_url,
            "prompt": prompt,
            "duration": duration,
        }
        resp = self.session.post(f"{self.base_url}/v1/videos/image2video", json=payload, timeout=60)
        resp.raise_for_status()
        result = resp.json()

        if not poll:
            return result

        task_id = (result.get("data") or {}).get("task_id") or result.get("task_id")
        if not task_id:
            return result

        return await self._poll_video(task_id, max_wait)

    async def _poll_video(self, task_id: str, max_wait: int = 300, interval: int = 5) -> dict:
        elapsed = 0
        while elapsed < max_wait:
            await asyncio.sleep(interval)
            elapsed += interval
            r = self.session.get(f"{self.base_url}/v1/videos/tasks/{task_id}", timeout=30)
            r.raise_for_status()
            data = r.json()
            status = (data.get("data") or {}).get("task_status") or data.get("status", "")
            if status in ("succeed", "completed", "done"):
                try:
                    video_url = (data.get("data") or {}).get("task_result", {}).get("videos", [{}])[0].get("url")
                    if video_url:
                        saved = self._save_file(video_url, "videos", "kling_video", "mp4")
                        data["saved_path"] = str(saved)
                        print(f"[KlingClient] Video saved: {saved}")
                except Exception as e:
                    print(f"[KlingClient] Warning: could not save video — {e}")
                return data
            if status in ("failed", "error"):
                raise RuntimeError(f"Kling video generation failed: {data}")
            print(f"[KlingClient] Waiting... {elapsed}s (status: {status})")

        raise TimeoutError(f"Kling video generation timed out after {max_wait}s")
