"""
Google Veo 视频生成器
使用 Google AI Studio / Vertex AI API
"""

import requests
import base64
import json
import time
import os
from typing import Optional

class GoogleVeoGenerator:
    """Google Veo 视频生成器"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://generativelanguage.googleapis.com/v1beta"
    
    def generate_video(
        self, 
        prompt: str, 
        output_path: str,
        duration: int = 5,
        sample_count: int = 1
    ) -> Optional[str]:
        """
        生成视频
        
        Args:
            prompt: 视频描述提示词
            output_path: 输出路径
            duration: 视频时长(秒)
            sample_count: 生成数量
        
        Returns:
            视频路径或 None
        """
        # Veo 3 API endpoint
        url = f"{self.base_url}/models/veo-3:generateVideo?key={self.api_key}"
        
        payload = {
            "prompt": prompt,
            "duration": duration,
            "sampleCount": sample_count
        }
        
        try:
            print(f"🎬 正在调用 Veo API...")
            print(f"   Prompt: {prompt[:50]}...")
            
            response = requests.post(
                url, 
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=60
            )
            
            result = response.json()
            
            if response.status_code == 200:
                # 处理响应 - Veo 返回 base64 编码的视频
                if "generatedVideos" in result:
                    video_data = result["generatedVideos"][0].get("bytes")
                    if video_data:
                        # 解码并保存
                        video_bytes = base64.b64decode(video_data)
                        with open(output_path, 'wb') as f:
                            f.write(video_bytes)
                        print(f"✅ 视频已保存: {output_path}")
                        return output_path
                
                # 检查是否有 operation id (异步模式)
                if "name" in result:
                    operation_id = result["name"]
                    return self._poll_operation(operation_id, output_path)
                
            else:
                print(f"❌ API 错误: {result}")
                return None
                
        except Exception as e:
            print(f"❌ 生成失败: {e}")
            return None
    
    def _poll_operation(self, operation_id: str, output_path: str) -> Optional[str]:
        """轮询异步操作直到完成"""
        poll_url = f"{self.base_url}/operations/{operation_id}?key={self.api_key}"
        
        max_attempts = 60  # 最多等待5分钟
        for i in range(max_attempts):
            try:
                response = requests.get(poll_url, timeout=30)
                result = response.json()
                
                if result.get("done"):
                    if "response" in result:
                        video_data = result["response"].get("bytes")
                        if video_data:
                            video_bytes = base64.b64decode(video_data)
                            with open(output_path, 'wb') as f:
                                f.write(video_bytes)
                            return output_path
                    return None
                
                print(f"⏳ 等待生成... {i+1}/{max_attempts}")
                time.sleep(5)
                
            except Exception as e:
                print(f"❌ 轮询错误: {e}")
                return None
        
        return None
    
    def generate_from_image(
        self,
        image_path: str,
        prompt: str,
        output_path: str,
        duration: int = 5
    ) -> Optional[str]:
        """
        从图像生成视频 (Image-to-Video)
        
        Args:
            image_path: 输入图像路径
            prompt: 动作描述
            output_path: 输出路径
            duration: 时长
        
        Returns:
            视频路径
        """
        # 读取图像并编码
        with open(image_path, 'rb') as f:
            image_bytes = f.read()
        
        image_base64 = base64.b64encode(image_bytes).decode('utf-8')
        
        url = f"{self.base_url}/models/veo-3:generateVideo?key={self.api_key}"
        
        payload = {
            "prompt": prompt,
            "image": {
                "bytesBase64Encoded": image_base64
            },
            "duration": duration
        }
        
        try:
            response = requests.post(url, json=payload, timeout=120)
            result = response.json()
            
            if response.status_code == 200 and "generatedVideos" in result:
                video_data = result["generatedVideos"][0].get("bytes")
                if video_data:
                    video_bytes = base64.b64decode(video_data)
                    with open(output_path, 'wb') as f:
                        f.write(video_bytes)
                    return output_path
            
            print(f"❌ API 响应: {result}")
            return None
            
        except Exception as e:
            print(f"❌ 生成失败: {e}")
            return None


# 测试
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 3:
        print("用法: python google_veo.py <api_key> <prompt>")
        sys.exit(1)
    
    api_key = sys.argv[1]
    prompt = sys.argv[2]
    
    generator = GoogleVeoGenerator(api_key)
    output = "test_video.mp4"
    
    result = generator.generate_video(prompt, output)
    if result:
        print(f"✅ 成功: {result}")
    else:
        print("❌ 失败")
