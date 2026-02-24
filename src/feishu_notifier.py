"""
飞书消息通知器
用于实时推送工作流进度
"""

import requests
import json
from typing import Optional

class FeishuNotifier:
    """飞书通知器"""
    
    def __init__(self, webhook_url: str = None, user_id: str = None):
        self.webhook_url = webhook_url
        self.user_id = user_id
        self.app_id = "cli_a90e1e88e6f8dbc2"
        self.app_secret = "MtWRDn3GhqOsR4OEXY1sRG1F0x3x4x5x"
        self.tenant_access_token = None
        self.token_expires = 0
    
    def _get_tenant_token(self) -> str:
        """获取 tenant_access_token"""
        import time
        import hashlib
        
        # 检查 token 是否过期
        if self.tenant_access_token and time.time() < self.token_expires - 300:
            return self.tenant_access_token
        
        url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        data = {
            "app_id": self.app_id,
            "app_secret": self.app_secret
        }
        
        response = requests.post(url, json=data)
        result = response.json()
        
        if result.get("code") == 0:
            self.tenant_access_token = result["tenant_access_token"]
            self.token_expires = result.get("expire", 0)
            return self.tenant_access_token
        
        raise Exception(f"获取 token 失败: {result}")
    
    def send_text(self, text: str, user_id: str = None):
        """发送文本消息"""
        token = self._get_tenant_token()
        target = user_id or self.user_id
        
        url = "https://open.feishu.cn/open-apis/im/v1/messages"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        # 构建消息内容
        content = {
            "text": text
        }
        
        params = {
            "receive_id_type": "user_id"
        }
        
        data = {
            "receive_id": target,
            "msg_type": "text",
            "content": json.dumps(content)
        }
        
        response = requests.post(url, headers=headers, params=params, json=data)
        return response.json()
    
    def send_card(self, card_json: dict, user_id: str = None):
        """发送卡片消息"""
        token = self._get_tenant_token()
        target = user_id or self.user_id
        
        url = "https://open.feishu.cn/open-apis/im/v1/messages"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        params = {
            "receive_id_type": "user_id"
        }
        
        data = {
            "receive_id": target,
            "msg_type": "interactive",
            "content": json.dumps(card_json)
        }
        
        response = requests.post(url, headers=headers, params=params, json=data)
        return response.json()
    
    def send_progress_card(self, state: dict, workflow_id: str = None):
        """发送进度卡片"""
        stage = state.get("stage", "")
        progress = state.get("progress", 0)
        message = state.get("message", "")
        current = state.get("current_item", "")
        completed = state.get("completed", 0)
        total = state.get("total", 0)
        
        # 进度条
        bar_length = 15
        filled = int(bar_length * progress)
        bar = "▓" * filled + "░" * (bar_length - filled)
        
        # 阶段颜色
        colors = {
            "剧本生成": "#FF9500",
            "提示词生成": "#34C759",
            "图像生成": "#007AFF",
            "视频生成": "#AF52DE",
            "视频合成": "#FF2D55",
            "完成": "#30D158"
        }
        
        card = {
            "config": {
                "wide_screen_mode": True
            },
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": f"🎬 {stage}"
                },
                "template": colors.get(stage, "blue")
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**进度:** {bar} {progress*100:.0f}%\n\n{message}"
                    }
                },
                {
                    "tag": "div",
                    "fields": [
                        {
                            "is_short": True,
                            "text": {
                                "tag": "lark_md",
                                "content": f"**当前任务:**\n{current}"
                            }
                        },
                        {
                            "is_short": True,
                            "text": {
                                "tag": "lark_md",
                                "content": f"**已完成:**\n{completed}/{total}"
                            }
                        }
                    ]
                },
                {
                    "tag": "action",
                    "actions": [
                        {
                            "tag": "button",
                            "text": {
                                "tag": "plain_text",
                                "content": "✅ 批准继续"
                            },
                            "type": "primary",
                            "value": {"action": "approve", "workflow_id": workflow_id}
                        },
                        {
                            "tag": "button",
                            "text": {
                                "tag": "plain_text",
                                "content": "❌ 要求修改"
                            },
                            "type": "danger",
                            "value": {"action": "reject", "workflow_id": workflow_id}
                        }
                    ]
                }
            ]
        }
        
        return self.send_card(card)


# 测试
if __name__ == "__main__":
    notifier = FeishuNotifier()
    # notifier.send_text("测试消息")
    
    # 测试进度卡片
    test_state = {
        "stage": "视频生成",
        "progress": 0.65,
        "message": "正在生成第8个视频片段",
        "current_item": "片段8/12",
        "completed": 8,
        "total": 12
    }
    # notifier.send_progress_card(test_state)
