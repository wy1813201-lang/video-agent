#!/usr/bin/env python3
"""
测试即梦 i2v (图生视频) API - 使用修复后的 JimengVideoClient
"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import urllib3
urllib3.disable_warnings()

from jimeng_client import JimengVideoClient


async def main():
    client = JimengVideoClient()
    print(f"AK: {client.access_key}")
    print(f"SK: {client.secret_key[:20]}...")

    # 用一张稳定可访问的公开图片
    test_image_url = "https://upload.wikimedia.org/wikipedia/commons/thumb/4/47/PNG_transparency_demonstration_1.png/280px-PNG_transparency_demonstration_1.png"

    print("\n=== 测试 image_to_video ===")
    result = await client.image_to_video(
        image_url=test_image_url,
        prompt="画面缓缓移动，光影变化",
        aspect_ratio="16:9",
        seed=42,
    )
    print(f"\n✅ 成功! 视频保存至: {result['video_path']}")
    return result


if __name__ == "__main__":
    asyncio.run(main())
