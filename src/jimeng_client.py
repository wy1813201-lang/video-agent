"""
即梦 AI (Jimeng) 图像/视频生成客户端
字节跳动即梦 AI - https://jimeng.jianying.com
API 文档: https://www.volcengine.com/docs/85128
"""

import json
import time
import requests
from pathlib import Path
from datetime import datetime

CONFIG_PATH = Path(__file__).parent.parent / "config" / "api_keys.json"


class JimengClient:
    """即梦 AI 客户端（火山引擎 Visual API）"""

    BASE_URL = "https://visual.volcengineapi.com"

    def __init__(self):
        with open(CONFIG_PATH) as f:
            config = json.load(f)

        cfg = config.get("jimeng", config.get("video", {}).get("jimeng", {}))
        self.access_key = cfg.get("access_key", "")
        self.secret_key = cfg.get("secret_key", "")
        self.api_key = cfg.get("api_key", "")  # 也支持直接 API key
        self.base_url = cfg.get("base_url", self.BASE_URL).rstrip("/")

        output_dir = cfg.get("output_dir", "~/Desktop/ShortDrama")
        self.output_dir = Path(output_dir).expanduser()

        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
        })
        if self.api_key:
            self.session.headers["Authorization"] = f"Bearer {self.api_key}"

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
                         width: int = 1080, height: int = 1920,
                         model_version: str = "high_aes_general_v21_L") -> dict:
        """
        文生图
        Action=CVProcess, req_key=high_aes_general_v21_L
        """
        payload = {
            "req_key": model_version,
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "width": width,
            "height": height,
            "return_url": True,
            "logo_info": {"add_logo": False},
        }
        params = {"Action": "CVProcess", "Version": "2022-08-31"}
        resp = self.session.post(self.base_url, params=params, json=payload, timeout=120)
        resp.raise_for_status()
        result = resp.json()

        try:
            image_url = result["data"]["image_urls"][0]
            saved = self._save_file(image_url, "images", "jimeng_image", "jpg")
            result["saved_path"] = str(saved)
            print(f"[JimengClient] Image saved: {saved}")
        except Exception as e:
            print(f"[JimengClient] Warning: could not save image — {e}")

        return result

    def text_to_video(self, prompt: str, negative_prompt: str = "",
                      width: int = 1080, height: int = 1920,
                      duration: int = 5,
                      poll: bool = True, max_wait: int = 300) -> dict:
        """
        文生视频（即梦视频生成）
        """
        payload = {
            "req_key": "jimeng_video_generation",
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "width": width,
            "height": height,
            "duration": duration,
            "return_url": True,
        }
        params = {"Action": "CVProcess", "Version": "2022-08-31"}
        resp = self.session.post(self.base_url, params=params, json=payload, timeout=60)
        resp.raise_for_status()
        result = resp.json()

        if not poll:
            return result

        task_id = result.get("data", {}).get("task_id")
        if not task_id:
            # 同步返回
            try:
                video_url = result["data"]["video_url"]
                saved = self._save_file(video_url, "videos", "jimeng_video", "mp4")
                result["saved_path"] = str(saved)
                print(f"[JimengClient] Video saved: {saved}")
            except Exception as e:
                print(f"[JimengClient] Warning: could not save video — {e}")
            return result

        return self._poll_task(task_id, max_wait)

    def _poll_task(self, task_id: str, max_wait: int = 300, interval: int = 5) -> dict:
        elapsed = 0
        params = {"Action": "CVGetResult", "Version": "2022-08-31"}
        while elapsed < max_wait:
            time.sleep(interval)
            elapsed += interval
            r = self.session.post(self.base_url, params=params,
                                  json={"task_id": task_id}, timeout=30)
            r.raise_for_status()
            data = r.json()
            status = data.get("data", {}).get("status", "")
            if status in ("done", "succeed", "completed"):
                try:
                    video_url = data["data"]["video_url"]
                    saved = self._save_file(video_url, "videos", "jimeng_video", "mp4")
                    data["saved_path"] = str(saved)
                    print(f"[JimengClient] Video saved: {saved}")
                except Exception as e:
                    print(f"[JimengClient] Warning: could not save video — {e}")
                return data
            if status in ("failed", "error"):
                raise RuntimeError(f"Jimeng task failed: {data}")
            print(f"[JimengClient] Waiting... {elapsed}s (status: {status})")

        raise TimeoutError(f"Jimeng task timed out after {max_wait}s")
