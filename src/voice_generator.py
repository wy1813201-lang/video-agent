#!/usr/bin/env python3
"""
AI 配音生成模块
支持 Edge TTS、硅基流动 (CosyVoice)、OpenAI TTS

用法：
    voice_gen = VoiceGenerator(api_config)
    audio_path = await voice_gen.generate(text, voice, output_path)
"""

import asyncio
import os
import json
from dataclasses import dataclass
from typing import Optional, List

# Edge TTS
import edge_tts


# 中文声音列表
ZH_CN_VOICES = {
    # 女声
    "xiaoxiao": "zh-CN-XiaoxiaoNeural",       # 晓晓 - 温柔女声
    "xiaoyi": "zh-CN-XiaoyiNeural",           # 晓伊 - 年轻女声
    "jenny": "zh-CN-JennyNeural",             # Jenny - 成熟女声
    "yunxi": "zh-CN-YunxiNeural",             # 云希 - 男声
    "yunyang": "zh-CN-YunyangNeural",         # 云扬 - 男声
    "yunjian": "zh-CN-YunjianNeural",          # 云健 - 男声
    
    # 情感声音
    "xiaoxiao_emotional": {
        "happy": "zh-CN-XiaoxiaoNeural",
        "sad": "zh-CN-XiaoxiaoNeural",
        "angry": "zh-CN-XiaoxiaoNeural",
        "fearful": "zh-CN-XiaoxiaoNeural",
        "disgusted": "zh-CN-XiaoxiaoNeural",
        "surprised": "zh-CN-XiaoxiaoNeural",
    }
}

# 英文声音列表
EN_US_VOICES = {
    "jenny": "en-US-JennyNeural",
    "guy": "en-US-GuyNeural",
    "aria": "en-US-AriaNeural",
    "ana": "en-US-anaNeural",
}


@dataclass
class VoiceConfig:
    """配音配置"""
    provider: str = "edge"           # edge / siliconflow / openai
    voice: str = "xiaoxiao"          # 声音名称
    rate: str = "+0%"                # 语速
    pitch: str = "+0Hz"              # 音调
    volume: str = "+0%"              # 音量
    output_format: str = "audio-24khz-48kbitrate-mono-mp3"


class VoiceGenerator:
    """AI 配音生成器"""
    
    def __init__(self, api_config: dict = None):
        self.api_config = api_config or {}
        self._edge_communicator = None
    
    async def generate(
        self, 
        text: str, 
        voice: str = "xiaoxiao",
        output_path: str = None,
        provider: str = "edge",
        **kwargs
    ) -> str:
        """
        生成配音
        
        Args:
            text: 要转换的文本
            voice: 声音名称
            output_path: 输出路径
            provider: 提供商 (edge / siliconflow / openai)
            
        Returns:
            生成的音频文件路径
        """
        if not output_path:
            output_path = f"output/audio/voice_{int(asyncio.get_event_loop().time())}.mp3"
        
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        
        if provider == "edge":
            return await self._generate_edge(text, voice, output_path, **kwargs)
        elif provider == "siliconflow":
            return await self._generate_siliconflow(text, voice, output_path, **kwargs)
        elif provider == "openai":
            return await self._generate_openai(text, voice, output_path, **kwargs)
        else:
            raise ValueError(f"Unknown provider: {provider}")
    
    async def _generate_edge(
        self, 
        text: str, 
        voice: str, 
        output_path: str,
        rate: str = "+0%",
        pitch: str = "+0Hz",
        **kwargs
    ) -> str:
        """使用 Edge TTS 生成配音"""
        # 获取声音名称
        voice_name = ZH_CN_VOICES.get(voice, voice)
        if voice_name not in ZH_CN_VOICES and not voice_name.endswith("Neural"):
            voice_name = ZH_CN_VOICES.get("xiaoxiao")
        
        communicate = edge_tts.Communicate(
            text=text,
            voice=voice_name,
            rate=rate,
            pitch=pitch,
        )
        
        await communicate.save(output_path)
        return output_path
    
    async def _generate_siliconflow(
        self,
        text: str,
        voice: str,
        output_path: str,
        **kwargs
    ) -> str:
        """使用硅基流动 CosyVoice 生成配音"""
        sf_config = self.api_config.get("voice", {}).get("siliconflow", {})
        
        if not sf_config.get("api_key"):
            raise ValueError("SiliconFlow API key 未配置")
        
        import requests
        
        # CosyVoice 声音映射
        voice_map = {
            "alex": "FunAudioLLM/CosyVoice2-0.5B:alex",
            "anna": "FunAudioLLM/CosyVoice2-0.5B:anna",
            "bella": "FunAudioLLM/CosyVoice2-0.5B:bella",
            "benjamin": "FunAudioLLM/CosyVoice2-0.5B:benjamin",
        }
        
        model = voice_map.get(voice, "FunAudioLLM/CosyVoice2-0.5B:alex")
        
        url = "https://api.siliconflow.cn/v1/t2a"
        headers = {
            "Authorization": f"Bearer {sf_config['api_key']}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": model,
            "input": {"text": text},
            "response_format": "mp3"
        }
        
        def _sync_call():
            response = requests.post(url, headers=headers, json=payload, timeout=60)
            response.raise_for_status()
            result = response.json()
            # 返回的是 base64 音频
            audio_data = result.get("data", {}).get("audio", "")
            if audio_data:
                import base64
                audio_bytes = base64.b64decode(audio_data)
                with open(output_path, "wb") as f:
                    f.write(audio_bytes)
                return output_path
            raise ValueError("No audio data in response")
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _sync_call)
    
    async def _generate_openai(
        self,
        text: str,
        voice: str,
        output_path: str,
        **kwargs
    ) -> str:
        """使用 OpenAI TTS 生成配音"""
        openai_config = self.api_config.get("voice", {}).get("openai", {})
        
        if not openai_config.get("api_key"):
            raise ValueError("OpenAI API key 未配置")
        
        import openai
        
        openai.api_key = openai_config["api_key"]
        if openai_config.get("base_url"):
            openai.api_base = openai_config["base_url"]
        
        # 映射声音
        voice_map = {
            "female": "alloy",
            "male": "onyx",
            "nova": "nova",
            "shimmer": "shimmer",
        }
        
        openai_voice = voice_map.get(voice, "alloy")
        
        response = await openai.Audio.atranscribe(
            model="tts-1-hd",
            voice=openai_voice,
            response_format="mp3",
            file=io.StringIO(text)  # OpenAI TTS 不支持直接文本，需要用代理
        )
        
        raise NotImplementedError("OpenAI TTS 需要额外处理，请使用 edge-tts")
    
    def list_voices(self, provider: str = "edge") -> List[str]:
        """列出可用的声音"""
        if provider == "edge":
            return list(ZH_CN_VOICES.keys())
        elif provider == "siliconflow":
            return ["alex", "anna", "bella", "benjamin"]
        elif provider == "openai":
            return ["female", "male", "nova", "shimmer"]
        return []


# 便捷函数：批量生成多角色配音
async def generate_dialogue_voice(
    dialogues: List[dict],
    voice_map: dict = None,
    output_dir: str = "output/audio",
    provider: str = "edge"
) -> List[str]:
    """
    批量生成多角色配音
    
    Args:
        dialogues: 对话列表 [{"speaker": "角色名", "line": "台词"}, ...]
        voice_map: 角色名 -> 声音名 的映射
        output_dir: 输出目录
        provider: 提供商
        
    Returns:
        生成的音频文件路径列表
    """
    voice_gen = VoiceGenerator()
    os.makedirs(output_dir, exist_ok=True)
    
    voice_map = voice_map or {
        "女主": "xiaoxiao",
        "男主": "yunxi",
        "配角": "xiaoyi",
    }
    
    results = []
    for i, dialog in enumerate(dialogues):
        speaker = dialog.get("speaker", "")
        line = dialog.get("line", "")
        
        voice = voice_map.get(speaker, "xiaoxiao")
        
        output_path = os.path.join(output_dir, f"voice_{i:03d}_{speaker}.mp3")
        
        try:
            path = await voice_gen.generate(
                text=line,
                voice=voice,
                output_path=output_path,
                provider=provider
            )
            results.append({
                "speaker": speaker,
                "line": line,
                "audio_path": path
            })
        except Exception as e:
            print(f"⚠️ 配音生成失败: {speaker} - {e}")
    
    return results


if __name__ == "__main__":
    # 测试
    async def test():
        gen = VoiceGenerator()
        
        # 测试 Edge TTS
        text = "你好，欢迎观看今天的短剧。"
        path = await gen.generate(text, voice="xiaoxiao")
        print(f"Generated: {path}")
        
        # 列出可用声音
        print(f"Available voices: {gen.list_voices()}")
    
    asyncio.run(test())
