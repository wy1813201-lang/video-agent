"""
即梦 AI (Jimeng) 视频生成客户端
火山引擎视觉智能 API - 使用官方 SDK
"""

import asyncio
import json
import aiohttp
import requests
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, Optional
from volcengine.auth.SignerV4 import SignerV4
from volcengine.Credentials import Credentials
from volcengine.base.Request import Request
try:
    from ip_adapter_generator import IPAdapterGenerator
except Exception:
    IPAdapterGenerator = None

CONFIG_PATH = Path(__file__).parent.parent / "config" / "api_keys.json"


class JimengVideoClient:
    """即梦视频生成客户端"""

    def __init__(self):
        with open(CONFIG_PATH) as f:
            config = json.load(f)

        cfg = config.get("video", {}).get("jimeng", {})
        self.access_key = cfg.get("access_key", "")
        self.secret_key = cfg.get("secret_key", "")  # 直接使用 base64 字符串
        
        self.host = 'visual.volcengineapi.com'
        self.region = 'cn-north-1'
        self.service = 'cv'
        
        self.models = cfg.get("models", {})
        self.default_resolution = cfg.get("default_resolution", "720p")

        output_dir = cfg.get("output_dir", "~/Desktop/ShortDrama")
        self.output_dir = Path(output_dir).expanduser()
        self.videos_dir = self.output_dir / "videos"
        self.videos_dir.mkdir(parents=True, exist_ok=True)
        self.images_dir = self.output_dir / "images"
        self.images_dir.mkdir(parents=True, exist_ok=True)

    def _sign_request(self, request):
        """使用火山引擎 SDK 签名"""
        credentials = Credentials(
            self.access_key, 
            self.secret_key, 
            self.service,  # service
            self.region    # region
        )
        SignerV4.sign(request, credentials)

    def _build_request(self, action: str, body: dict) -> Request:
        """构建并签名请求，避免重复代码"""
        request = Request()
        request.host = self.host
        request.method = 'POST'
        request.path = '/'
        request.query = {'Action': action, 'Version': '2022-08-31'}
        request.body = json.dumps(body).encode('utf-8')
        request.headers = {
            'Content-Type': 'application/json',
            'Host': self.host
        }
        self._sign_request(request)
        return request

    def _apply_ip_adapter_prompt(
        self,
        prompt: str,
        use_ip_adapter: bool = False,
        ip_adapter: Optional[Dict[str, Any]] = None,
    ) -> str:
        """可选地增强提示词，注入角色一致性/IP-Adapter 指令。"""
        if not use_ip_adapter:
            return prompt

        ip_adapter = ip_adapter or {}
        character_name = ip_adapter.get("character_name")
        try:
            from prompt_builder import CharacterConsistencyPrompt
            return CharacterConsistencyPrompt.build_consistent_prompt(
                base_prompt=prompt,
                character_name=character_name,
                use_ip_adapter=True,
                use_lora=False,
                lora_name=None,
                enhance_face=True,
            )
        except Exception:
            suffix = "IP-Adapter, consistent character identity across scenes, stable face features"
            return f"{prompt}, {suffix}"

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
            print("[Jimeng] IP-Adapter unavailable: import failed")
            return None

        try:
            generator = IPAdapterGenerator(
                model_path=ip_adapter.get("model_path", "stabilityai/stable-diffusion-xl-base-1.0"),
                ip_adapter_path=ip_adapter.get("ip_adapter_path", "h94/IP-Adapter"),
                device=ip_adapter.get("device"),
                attention_backend=ip_adapter.get("attention_backend", "auto"),
            )
            image = generator.generate_with_reference(
                prompt=prompt,
                reference_images=references,
                negative_prompt=negative_prompt,
                num_inference_steps=ip_adapter.get("num_inference_steps", 30),
                guidance_scale=ip_adapter.get("guidance_scale", 7.5),
                seed=ip_adapter.get("seed"),
                ip_adapter_scale=ip_adapter.get("scale", 0.7),
            )
        except Exception as e:
            print(f"[Jimeng] IP-Adapter generation failed: {e}")
            return None
        finally:
            try:
                generator.unload()
            except Exception:
                pass

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        image_path = self.images_dir / f"image_ip_adapter_{timestamp}.jpg"
        image.save(image_path)
        print(f"[Jimeng] IP-Adapter image saved: {image_path}")
        return {
            "saved_path": str(image_path),
            "ip_adapter_used": True,
        }

    def generate_image(
        self,
        prompt: str,
        negative_prompt: str = "",
        use_ip_adapter: bool = False,
        ip_adapter: Optional[Dict[str, Any]] = None,
    ) -> dict:
        """图像生成入口（即梦客户端当前仅支持本地 IP-Adapter 方案）。"""
        if use_ip_adapter:
            result = self._generate_with_ip_adapter(
                prompt=prompt,
                negative_prompt=negative_prompt,
                ip_adapter=ip_adapter,
            )
            if result:
                return result

        raise NotImplementedError("JimengClient 当前未集成官方图像生成 API；请启用 use_ip_adapter 或使用 CozexClient。")

    def image_generation(
        self,
        prompt: str,
        negative_prompt: str = "",
        use_ip_adapter: bool = False,
        ip_adapter: Optional[Dict[str, Any]] = None,
    ) -> dict:
        """兼容接口：转发到 generate_image。"""
        return self.generate_image(
            prompt=prompt,
            negative_prompt=negative_prompt,
            use_ip_adapter=use_ip_adapter,
            ip_adapter=ip_adapter,
        )

    async def video_generation(
        self,
        prompt: str,
        resolution: str = "720p",
        aspect_ratio: str = "9:16",
        frames: int = 121,
        seed: int = -1,
        max_wait: int = 300,
        use_ip_adapter: bool = False,
        ip_adapter: Optional[Dict[str, Any]] = None,
    ) -> dict:
        """生成视频（异步）"""
        resolution = resolution.lower().replace("p", "p")
        model_config = self.models.get(resolution, {})
        req_key = model_config.get("req_key", "jimeng_t2v_v30")
        prompt = self._apply_ip_adapter_prompt(prompt, use_ip_adapter, ip_adapter)

        print(f"[Jimeng] 生成: {prompt[:30]}... | {resolution}")

        # 禁用 SSL 证书验证（火山引擎 SSL 问题）
        connector = aiohttp.TCPConnector(ssl=False)
        async with aiohttp.ClientSession(connector=connector) as session:
            # 提交任务
            req = self._build_request('CVSync2AsyncSubmitTask', {
                "req_key": req_key,
                "prompt": prompt,
                "seed": seed,
                "frames": frames,
                "aspect_ratio": aspect_ratio
            })
            url = f"https://{self.host}/?Action=CVSync2AsyncSubmitTask&Version=2022-08-31"
            async with session.post(url, headers=req.headers, data=req.body) as resp:
                result = await resp.json()

            if result.get("code") != 10000:
                raise Exception(f"提交失败: {result.get('message')}")

            task_id = result.get("data", {}).get("task_id")
            print(f"[Jimeng] 任务ID: {task_id}")

            # 轮询等待结果
            poll_body = {"req_key": req_key, "task_id": task_id}
            poll_url = f"https://{self.host}/?Action=CVSync2AsyncGetResult&Version=2022-08-31"
            video_url = None

            for _ in range(max_wait // 3):
                await asyncio.sleep(3)

                req = self._build_request('CVSync2AsyncGetResult', poll_body)
                async with session.post(poll_url, headers=req.headers, data=req.body) as resp:
                    result = await resp.json()

                status = result.get("data", {}).get("status")
                print(f"[Jimeng] 状态: {status}")

                if status == 'done':
                    video_url = result.get("data", {}).get("video_url")
                    break
                elif status in ['not_found', 'expired']:
                    raise Exception("任务失败或过期")
            else:
                raise Exception("等待超时")

            # 下载视频
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            video_path = self.videos_dir / f"video_{timestamp}.mp4"

            async with session.get(video_url) as resp:
                resp.raise_for_status()
                content = await resp.read()

        with open(video_path, "wb") as f:
            f.write(content)

        print(f"[Jimeng] 保存: {video_path}")

        return {
            "video_path": str(video_path),
            "video_url": video_url,
            "resolution": resolution
        }


JimengClient = JimengVideoClient
