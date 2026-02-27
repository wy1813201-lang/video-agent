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
from volcengine.auth.SignerV4 import SignerV4
from volcengine.Credentials import Credentials
from volcengine.base.Request import Request

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

    async def video_generation(
        self,
        prompt: str,
        resolution: str = "720p",
        aspect_ratio: str = "9:16",
        frames: int = 121,
        seed: int = -1,
        max_wait: int = 300
    ) -> dict:
        """生成视频（异步）"""
        resolution = resolution.lower().replace("p", "p")
        model_config = self.models.get(resolution, {})
        req_key = model_config.get("req_key", "jimeng_t2v_v30")

        print(f"[Jimeng] 生成: {prompt[:30]}... | {resolution}")

        async with aiohttp.ClientSession() as session:
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
