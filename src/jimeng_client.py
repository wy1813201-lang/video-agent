"""
即梦 AI (Jimeng) 视频生成客户端
火山引擎视觉智能 API
"""

import json
import requests
import hashlib
import hmac
from pathlib import Path
from datetime import datetime

CONFIG_PATH = Path(__file__).parent.parent / "config" / "api_keys.json"


def sign(key, msg):
    return hmac.new(key, msg.encode('utf-8'), hashlib.sha256).digest()

def getSignatureKey(key, dateStamp, regionName, serviceName):
    kDate = sign(key.encode('utf-8'), dateStamp)
    kRegion = sign(kDate, regionName)
    kService = sign(kRegion, serviceName)
    return sign(kService, 'request')


def make_volc_request(ak, sk, action, body_params):
    """火山引擎 V4 签名请求"""
    host = 'visual.volcengineapi.com'
    region = 'cn-north-1'
    service = 'cv'
    
    t = datetime.utcnow()
    current_date = t.strftime('%Y%m%dT%H%M%SZ')
    datestamp = t.strftime('%Y%m%d')
    
    query_params = {'Action': action, 'Version': '2022-08-31'}
    req_query = '&'.join([f"{k}={v}" for k, v in sorted(query_params.items())])
    req_body = json.dumps(body_params)
    
    signed_headers = 'content-type;host;x-content-sha256;x-date'
    payload_hash = hashlib.sha256(req_body.encode('utf-8')).hexdigest()
    canonical_headers = f'content-type:application/json\nhost:{host}\nx-content-sha256:{payload_hash}\nx-date:{current_date}\n'
    canonical_request = f"POST\n/\n{req_query}\n{canonical_headers}\n{signed_headers}\n{payload_hash}"
    
    algorithm = 'HMAC-SHA256'
    credential_scope = f'{datestamp}/{region}/{service}/request'
    string_to_sign = f'{algorithm}\n{current_date}\n{credential_scope}\n{hashlib.sha256(canonical_request.encode("utf-8")).hexdigest()}'
    
    signing_key = getSignatureKey(sk, datestamp, region, service)
    signature = hmac.new(signing_key, string_to_sign.encode('utf-8'), hashlib.sha256).hexdigest()
    
    authorization_header = f'{algorithm} Credential={ak}/{credential_scope}, SignedHeaders={signed_headers}, Signature={signature}'
    
    headers = {
        'X-Date': current_date,
        'Authorization': authorization_header,
        'X-Content-Sha256': payload_hash,
        'Content-Type': 'application/json'
    }
    
    return requests.post(f'https://{host}/?{req_query}', headers=headers, data=req_body)


class JimengVideoClient:
    """即梦视频生成客户端"""

    def __init__(self):
        with open(CONFIG_PATH) as f:
            config = json.load(f)

        cfg = config.get("video", {}).get("jimeng", {})
        self.access_key = cfg.get("access_key", "")
        self.secret_key = cfg.get("secret_key", "")  # base64 编码的 SK
        self.models = cfg.get("models", {})
        self.default_resolution = cfg.get("default_resolution", "720p")

        output_dir = cfg.get("output_dir", "~/Desktop/ShortDrama")
        self.output_dir = Path(output_dir).expanduser()
        self.videos_dir = self.output_dir / "videos"
        self.videos_dir.mkdir(parents=True, exist_ok=True)

    def video_generation(
        self,
        prompt: str,
        resolution: str = "720p",
        aspect_ratio: str = "16:9",
        frames: int = 121,
        seed: int = -1,
        max_wait: int = 300
    ) -> dict:
        """生成视频"""
        resolution = resolution.lower().replace("p", "p")
        model_config = self.models.get(resolution, {})
        req_key = model_config.get("req_key", "jimeng_t2v_v30")
        
        print(f"[Jimeng] 生成: {prompt[:30]}... | {resolution}")
        
        # 提交任务
        resp = make_volc_request(
            self.access_key, 
            self.secret_key,  # 使用 base64 编码的 SK
            'CVSync2AsyncSubmitTask',
            {
                "req_key": req_key,
                "prompt": prompt,
                "seed": seed,
                "frames": frames,
                "aspect_ratio": aspect_ratio
            }
        )
        
        result = resp.json()
        
        if result.get("code") != 10000:
            raise Exception(f"提交失败: {result.get('message')}")
        
        task_id = result.get("data", {}).get("task_id")
        print(f"[Jimeng] 任务ID: {task_id}")
        
        # 轮询等待结果
        import time
        for i in range(max_wait // 3):
            time.sleep(3)
            
            resp = make_volc_request(
                self.access_key,
                self.secret_key,
                'CVSync2AsyncGetResult',
                {
                    "req_key": req_key,
                    "task_id": task_id
                }
            )
            
            result = resp.json()
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
        
        resp = requests.get(video_url)
        resp.raise_for_status()
        
        with open(video_path, "wb") as f:
            f.write(resp.content)
        
        print(f"[Jimeng] 保存: {video_path}")
        
        return {
            "video_path": str(video_path),
            "video_url": video_url,
            "resolution": resolution
        }


JimengClient = JimengVideoClient
