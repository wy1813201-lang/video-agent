"""
Cozex API client for image and video generation.
"""

import json
import time
import requests
from datetime import datetime
from pathlib import Path


CONFIG_PATH = Path(__file__).parent.parent / "config" / "api_keys.json"


class CozexClient:
    def __init__(self):
        with open(CONFIG_PATH) as f:
            config = json.load(f)

        # Use image config as primary (same key/url as video)
        img_cfg = config["image"]["cozex"]
        self.api_key = img_cfg["api_key"]
        self.base_url = img_cfg["base_url"].rstrip("/")
        self.default_image_model = img_cfg["model"]

        vid_cfg = config["video"]["cozex"]
        self.default_video_model = vid_cfg["video_model"]

        # Output directory from video.cozex config, fallback to ~/Desktop/ShortDrama
        output_dir = vid_cfg.get("output_dir", "~/Desktop/ShortDrama")
        self.output_dir = Path(output_dir).expanduser()

        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        })

    def _save_file(self, url: str, subdir: str, prefix: str, ext: str) -> Path:
        """Download a URL and save to output_dir/subdir/ with a timestamp filename."""
        dest_dir = self.output_dir / subdir
        dest_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{prefix}_{timestamp}.{ext}"
        dest = dest_dir / filename
        resp = requests.get(url, timeout=120)
        resp.raise_for_status()
        dest.write_bytes(resp.content)
        return dest

    def image_generation(self, prompt: str, model: str = None) -> dict:
        """
        Generate an image via /v1/images/generations.
        Downloads and saves the result to output_dir/images/.
        Returns the API response dict with an added 'saved_path' key.
        """
        model = model or self.default_image_model
        payload = {
            "model": model,
            "prompt": prompt,
            "n": 1,
        }
        resp = self.session.post(f"{self.base_url}/v1/images/generations", json=payload, timeout=120)
        resp.raise_for_status()
        result = resp.json()

        # Extract image URL and save
        try:
            image_url = result["data"][0]["url"]
            saved = self._save_file(image_url, "images", "image", "jpg")
            result["saved_path"] = str(saved)
            print(f"[CozexClient] Image saved: {saved}")
        except (KeyError, IndexError, Exception) as e:
            print(f"[CozexClient] Warning: could not save image — {e}")

        return result

    def video_generation(self, prompt: str, model: str = None, poll: bool = True, poll_interval: int = 5, max_wait: int = 300) -> dict:
        """
        Submit a video generation job via /v1/video/generations.
        If poll=True, waits for completion, downloads and saves the video to output_dir/videos/.
        Returns the API response dict with an added 'saved_path' key.
        """
        model = model or self.default_video_model
        payload = {
            "model": model,
            "prompt": prompt,
        }
        resp = self.session.post(f"{self.base_url}/v1/video/generations", json=payload, timeout=60)
        resp.raise_for_status()
        result = resp.json()

        if not poll:
            return result

        # Poll for completion if we got a task id
        task_id = (result.get("data") or {}).get("task_id") or result.get("id")
        if not task_id:
            return result

        elapsed = 0
        while elapsed < max_wait:
            time.sleep(poll_interval)
            elapsed += poll_interval
            status_resp = self.session.get(
                f"{self.base_url}/v1/video/generations/{task_id}",
                timeout=30,
            )
            status_resp.raise_for_status()
            status_data = status_resp.json()
            status = (status_data.get("data") or {}).get("status") or status_data.get("status")
            if status in ("succeeded", "completed", "done"):
                # Extract video URL and save
                try:
                    video_url = (status_data.get("data") or {}).get("video_url") or status_data.get("video_url")
                    if video_url:
                        saved = self._save_file(video_url, "videos", "video", "mp4")
                        status_data["saved_path"] = str(saved)
                        print(f"[CozexClient] Video saved: {saved}")
                    else:
                        print("[CozexClient] Warning: no video_url in response")
                except Exception as e:
                    print(f"[CozexClient] Warning: could not save video — {e}")
                return status_data
            if status in ("failed", "error"):
                raise RuntimeError(f"Video generation failed: {status_data}")

        raise TimeoutError(f"Video generation timed out after {max_wait}s")
