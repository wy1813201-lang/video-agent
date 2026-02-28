"""
Cozex API client — 支持多模型图像/视频生成
"""

import json
import time
import requests
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional
try:
    from ip_adapter_generator import IPAdapterGenerator
except Exception:
    IPAdapterGenerator = None


CONFIG_PATH = Path(__file__).parent.parent / "config" / "api_keys.json"

# 可用模型列表
IMAGE_MODELS = {
    "seedream-5":   "doubao-seedream-5-0-260128",
    "seedream-3":   "doubao-seedream-3-0-t2i-250415",
    "flux-dev":     "flux-dev",
    "flux-schnell": "flux-schnell",
    "sdxl":         "stable-diffusion-xl-base-1.0",
    "sd3":          "stable-diffusion-3-medium",
}

VIDEO_MODELS = {
    "seedance-pro": "doubao-seedance-1-5-pro-251215",
    "seedance-lite": "doubao-seedance-1-5-lite-251215",
    "wan-pro":      "wan2.1-pro",
    "wan-lite":     "wan2.1-lite",
    "hailuo":       "hailuo-video",
}


class CozexClient:
    def __init__(self):
        with open(CONFIG_PATH) as f:
            config = json.load(f)

        img_cfg = config["image"]["cozex"]
        self.api_key = img_cfg["api_key"]
        self.base_url = img_cfg["base_url"].rstrip("/")
        self.default_image_model = img_cfg.get("model", IMAGE_MODELS["seedream-5"])

        vid_cfg = config["video"]["cozex"]
        self.default_video_model = vid_cfg.get("video_model", VIDEO_MODELS["seedance-pro"])

        output_dir = vid_cfg.get("output_dir", "~/Desktop/ShortDrama")
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

    def list_image_models(self) -> dict:
        return IMAGE_MODELS.copy()

    def list_video_models(self) -> dict:
        return VIDEO_MODELS.copy()

    def _generate_with_ip_adapter(
        self,
        prompt: str,
        negative_prompt: str = "",
        ip_adapter: Optional[Dict[str, Any]] = None,
    ) -> Optional[dict]:
        """使用本地 IP-Adapter 进行角色一致性图像生成。"""
        ip_adapter = ip_adapter or {}
        references = ip_adapter.get("reference_images") or ip_adapter.get("references") or []
        if isinstance(references, str):
            references = [references]
        references = [r for r in references if r]
        if not references:
            return None

        if IPAdapterGenerator is None:
            print("[CozexClient] IP-Adapter unavailable, fallback to API: import failed")
            return None
        try:
            model_path = ip_adapter.get("model_path", "stabilityai/stable-diffusion-xl-base-1.0")
            adapter_path = ip_adapter.get("ip_adapter_path", "h94/IP-Adapter")
            generator = IPAdapterGenerator(
                model_path=model_path,
                ip_adapter_path=adapter_path,
                device=ip_adapter.get("device"),
                attention_backend=ip_adapter.get("attention_backend", "auto"),
            )
        except Exception as e:
            print(f"[CozexClient] IP-Adapter unavailable, fallback to API: {e}")
            return None

        try:
            image = generator.generate_with_reference(
                prompt=prompt,
                reference_images=references,
                negative_prompt=negative_prompt,
                num_inference_steps=ip_adapter.get("num_inference_steps", 30),
                guidance_scale=ip_adapter.get("guidance_scale", 7.5),
                seed=ip_adapter.get("seed"),
                ip_adapter_scale=ip_adapter.get("scale", 0.7),
            )
            dest_dir = self.output_dir / "images"
            dest_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            saved = dest_dir / f"image_ip_adapter_{timestamp}.jpg"
            image.save(saved)
            print(f"[CozexClient] IP-Adapter image saved: {saved}")
            return {
                "data": [{"url": ""}],
                "saved_path": str(saved),
                "ip_adapter_used": True,
            }
        except Exception as e:
            print(f"[CozexClient] IP-Adapter generation failed, fallback to API: {e}")
            return None
        finally:
            try:
                generator.unload()
            except Exception:
                pass

    def generate_image(
        self,
        prompt: str,
        model: str = None,
        negative_prompt: str = "",
        size: str = None,
        use_ip_adapter: bool = False,
        ip_adapter: Optional[Dict[str, Any]] = None,
    ) -> dict:
        """统一图像生成入口。"""
        return self.image_generation(
            prompt=prompt,
            model=model,
            negative_prompt=negative_prompt,
            size=size,
            use_ip_adapter=use_ip_adapter,
            ip_adapter=ip_adapter,
        )

    def image_generation(self, prompt: str, model: str = None,
                         negative_prompt: str = "", size: str = None,
                         use_ip_adapter: bool = False,
                         ip_adapter: Optional[Dict[str, Any]] = None) -> dict:
        """
        生成图像 POST /v1/images/generations
        model: 可用 IMAGE_MODELS 中的别名或完整模型名
        """
        if use_ip_adapter:
            result = self._generate_with_ip_adapter(
                prompt=prompt,
                negative_prompt=negative_prompt,
                ip_adapter=ip_adapter,
            )
            if result:
                return result

        model = IMAGE_MODELS.get(model, model) or self.default_image_model
        payload = {"model": model, "prompt": prompt, "n": 1}
        if negative_prompt:
            payload["negative_prompt"] = negative_prompt
        if size:
            payload["size"] = size  # e.g. "1080x1920"

        resp = self.session.post(f"{self.base_url}/v1/images/generations",
                                 json=payload, timeout=120)
        resp.raise_for_status()
        result = resp.json()

        try:
            image_url = result["data"][0]["url"]
            saved = self._save_file(image_url, "images", "image", "jpg")
            result["saved_path"] = str(saved)
            print(f"[CozexClient] Image saved: {saved}")
        except Exception as e:
            print(f"[CozexClient] Warning: could not save image — {e}")

        return result

    def video_generation(self, prompt: str, model: str = None,
                         image_url: str = None,
                         poll: bool = True, poll_interval: int = 5,
                         max_wait: int = 300) -> dict:
        """
        生成视频 POST /v1/video/generations
        model: 可用 VIDEO_MODELS 中的别名或完整模型名
        image_url: 图生视频时传入参考图 URL
        """
        model = VIDEO_MODELS.get(model, model) or self.default_video_model
        payload = {"model": model, "prompt": prompt}
        if image_url:
            payload["image_url"] = image_url

        resp = self.session.post(f"{self.base_url}/v1/video/generations",
                                 json=payload, timeout=60)
        resp.raise_for_status()
        result = resp.json()

        if not poll:
            return result

        task_id = (result.get("data") or {}).get("task_id") or result.get("id")
        if not task_id:
            return result

        elapsed = 0
        while elapsed < max_wait:
            time.sleep(poll_interval)
            elapsed += poll_interval
            sr = self.session.get(f"{self.base_url}/v1/video/generations/{task_id}",
                                  timeout=30)
            sr.raise_for_status()
            sd = sr.json()
            status = (sd.get("data") or {}).get("status") or sd.get("status", "")
            if status in ("succeeded", "completed", "done"):
                try:
                    video_url = (sd.get("data") or {}).get("video_url") or sd.get("video_url")
                    if video_url:
                        saved = self._save_file(video_url, "videos", "video", "mp4")
                        sd["saved_path"] = str(saved)
                        print(f"[CozexClient] Video saved: {saved}")
                except Exception as e:
                    print(f"[CozexClient] Warning: could not save video — {e}")
                return sd
            if status in ("failed", "error"):
                raise RuntimeError(f"Video generation failed: {sd}")
            print(f"[CozexClient] Waiting... {elapsed}s (status: {status})")

        raise TimeoutError(f"Video generation timed out after {max_wait}s")
