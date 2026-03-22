"""
本地图片 -> 公网 image_url 的最小桥接层。

默认尝试匿名临时文件托管服务：
1. transfer.sh (PUT /<filename>)
2. 0x0.st (multipart/form-data)

也支持通过配置/环境变量注入自定义上传端点，避免把主流程绑死在某一家服务上。
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional

import requests


class ImageUrlBridge:
    """把本地图片桥接成 Jimeng i2v 可用的公网 URL。"""

    DEFAULT_SERVICES = ["transfer.sh", "0x0.st"]

    def __init__(self, config: Optional[Dict[str, Any]] = None, session: Optional[requests.Session] = None):
        self.config = config or {}
        self.session = session or requests.Session()
        self.timeout = int(self.config.get("timeout", 120))
        self.enabled = bool(self.config.get("enabled", True))
        self.preferred_service = self.config.get("service") or os.getenv("IMAGE_URL_BRIDGE_SERVICE", "")

    def ensure_public_url(self, image_path_or_url: str) -> str:
        if not image_path_or_url:
            return ""
        if image_path_or_url.startswith(("http://", "https://")):
            return image_path_or_url
        if not self.enabled:
            raise RuntimeError("image_url bridge disabled")

        image_path = Path(image_path_or_url).expanduser()
        if not image_path.exists():
            raise FileNotFoundError(f"image not found: {image_path}")

        services = self._resolve_services()
        last_error = None
        for service in services:
            try:
                if service == "transfer.sh":
                    return self._upload_transfer_sh(image_path)
                if service == "0x0.st":
                    return self._upload_0x0(image_path)
                if service == "custom":
                    return self._upload_custom(image_path)
                raise RuntimeError(f"unsupported image bridge service: {service}")
            except Exception as e:
                last_error = e

        raise RuntimeError(f"failed to bridge local image to public url: {last_error}")

    def _resolve_services(self):
        if self.preferred_service:
            return [self.preferred_service]
        services = self.config.get("fallback_services")
        if isinstance(services, list) and services:
            return services
        return list(self.DEFAULT_SERVICES)

    def _upload_transfer_sh(self, image_path: Path) -> str:
        with image_path.open("rb") as f:
            resp = self.session.put(
                f"https://transfer.sh/{image_path.name}",
                data=f,
                headers={"Max-Days": str(self.config.get("max_days", 1))},
                timeout=self.timeout,
            )
        resp.raise_for_status()
        return resp.text.strip()

    def _upload_0x0(self, image_path: Path) -> str:
        with image_path.open("rb") as f:
            resp = self.session.post(
                "https://0x0.st",
                files={"file": (image_path.name, f)},
                timeout=self.timeout,
            )
        resp.raise_for_status()
        return resp.text.strip()

    def _upload_custom(self, image_path: Path) -> str:
        endpoint = self.config.get("endpoint") or os.getenv("IMAGE_URL_BRIDGE_ENDPOINT", "")
        if not endpoint:
            raise RuntimeError("custom image bridge endpoint is not configured")

        method = str(self.config.get("method", "POST")).upper()
        field_name = self.config.get("field_name", "file")
        headers = self.config.get("headers") or {}
        data = self.config.get("data") or {}
        response_path = self.config.get("response_path", "url")

        with image_path.open("rb") as f:
            if method == "PUT":
                resp = self.session.put(endpoint, data=f, headers=headers, timeout=self.timeout)
            else:
                resp = self.session.request(
                    method,
                    endpoint,
                    files={field_name: (image_path.name, f)},
                    data=data,
                    headers=headers,
                    timeout=self.timeout,
                )
        resp.raise_for_status()

        if response_path == "$text":
            return resp.text.strip()

        payload = resp.json()
        value: Any = payload
        for key in str(response_path).split("."):
            if not key:
                continue
            if not isinstance(value, dict):
                raise RuntimeError(f"invalid response_path '{response_path}', got non-dict at '{key}'")
            value = value.get(key)
        if not value:
            raise RuntimeError(f"custom image bridge response missing path: {response_path}")
        return str(value).strip()
