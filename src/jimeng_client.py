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

    DEFAULT_LINXIA_PROFILE: Dict[str, str] = {
        "gender": "女性",
        "age": "25-30岁",
        "hairstyle": "长发披肩",
        "outfit": "莫兰迪色真丝衬衫",
        "accessory": "精致腕表",
        "makeup": "精致职场妆",
        "temperament": "冷静自信",
    }

    def __init__(self):
        with open(CONFIG_PATH) as f:
            config = json.load(f)

        cfg = config.get("video", {}).get("jimeng", {})
        self.access_key = cfg.get("access_key", "")
        # SK直接使用原始字符串，不做任何base64解码
        self.secret_key = cfg.get("secret_key", "")
        
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

    def _build_character_profile_prompt(
        self,
        character_name: str = "林夏",
        profile: Optional[Dict[str, str]] = None,
    ) -> str:
        """构建统一角色描述模板，保证跨场景外观稳定。"""
        merged = dict(self.DEFAULT_LINXIA_PROFILE)
        if profile:
            merged.update({k: v for k, v in profile.items() if v})

        return (
            f"{character_name}（固定角色设定）: "
            f"{merged['gender']}，{merged['age']}，{merged['hairstyle']}，"
            f"穿着{merged['outfit']}，佩戴{merged['accessory']}，"
            f"{merged['makeup']}，整体气质{merged['temperament']}。"
            "保持同一张脸与体型，不改变发色、发型、服装款式与配饰。"
        )

    def _build_scene_consistent_prompt(
        self,
        scene_prompt: str,
        scene_index: Optional[int] = None,
        character_name: str = "林夏",
        profile: Optional[Dict[str, str]] = None,
    ) -> str:
        """将场景描述与统一角色模板合并为视频生成 Prompt。"""
        scene_label = f"场景{scene_index}: " if scene_index is not None else ""
        role_prompt = self._build_character_profile_prompt(
            character_name=character_name,
            profile=profile,
        )
        return (
            f"{scene_label}{scene_prompt}。"
            f"主角设定锁定：{role_prompt}"
            "镜头中主角始终是同一人，保持人物一致性。"
        )

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
        scene_prompt: Optional[str] = None,
        scene_index: Optional[int] = None,
        main_character: str = "林夏",
        character_profile: Optional[Dict[str, str]] = None,
        enforce_character_consistency: bool = True,
    ) -> dict:
        """生成视频（异步）"""
        resolution = resolution.lower().replace("p", "p")
        model_config = self.models.get(resolution, {})
        req_key = model_config.get("req_key", "jimeng_t2v_v30")

        merged_prompt = scene_prompt or prompt
        if enforce_character_consistency:
            merged_prompt = self._build_scene_consistent_prompt(
                scene_prompt=merged_prompt,
                scene_index=scene_index,
                character_name=main_character,
                profile=character_profile,
            )

        prompt = merged_prompt
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

            task_data = result.get("data") or {}
            task_id = task_data.get("task_id")
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

                poll_data = result.get("data") or {}
                status = poll_data.get("status")
                print(f"[Jimeng] 状态: {status}")

                if status == 'done':
                    video_url = poll_data.get("video_url")
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


    async def image_to_video(
        self,
        image_url: str,
        prompt: str = "",
        aspect_ratio: str = "9:16",
        seed: int = -1,
        max_wait: int = 300,
    ) -> dict:
        """图生视频 - 首帧 (jimeng_i2v_first_v30)"""
        req_key = "jimeng_i2v_first_v30"
        print(f"[Jimeng i2v] 提交任务 | prompt={prompt[:30]}...")

        connector = aiohttp.TCPConnector(ssl=False)
        async with aiohttp.ClientSession(connector=connector) as session:
            # 提交任务
            req = self._build_request('CVSync2AsyncSubmitTask', {
                "req_key": req_key,
                "prompt": prompt,
                "seed": seed,
                "image_urls": [image_url],
                "aspect_ratio": aspect_ratio,
            })
            url = f"https://{self.host}/?Action=CVSync2AsyncSubmitTask&Version=2022-08-31"
            async with session.post(url, headers=req.headers, data=req.body) as resp:
                result = await resp.json()

            if result.get("code") != 10000:
                raise Exception(f"i2v提交失败: {result.get('message')} | {result}")

            task_data = result.get("data") or {}
            task_id = task_data.get("task_id")
            print(f"[Jimeng i2v] task_id: {task_id}")

            # 轮询
            poll_body = {"req_key": req_key, "task_id": task_id}
            poll_url = f"https://{self.host}/?Action=CVSync2AsyncGetResult&Version=2022-08-31"
            video_url = None

            for _ in range(max_wait // 3):
                await asyncio.sleep(3)
                req = self._build_request('CVSync2AsyncGetResult', poll_body)
                async with session.post(poll_url, headers=req.headers, data=req.body) as resp:
                    result = await resp.json()

                poll_data = result.get("data") or {}
                status = poll_data.get("status")
                print(f"[Jimeng i2v] 状态: {status}")

                if status == 'done':
                    video_url = poll_data.get("video_url")
                    break
                elif status in ['not_found', 'expired', 'failed']:
                    raise Exception(f"任务失败: {status}")
            else:
                raise Exception("等待超时")

            # 下载视频
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            video_path = self.videos_dir / f"i2v_{timestamp}.mp4"

            async with session.get(video_url) as resp:
                resp.raise_for_status()
                content = await resp.read()

        with open(video_path, "wb") as f:
            f.write(content)

        print(f"[Jimeng i2v] 保存: {video_path}")
        return {
            "video_path": str(video_path),
            "video_url": video_url,
            "task_id": task_id,
        }


JimengClient = JimengVideoClient
