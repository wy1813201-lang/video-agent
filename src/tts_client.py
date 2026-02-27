"""
AI 配音模块
支持多种 TTS 引擎：Edge TTS, ChatTTS, CosyVoice
"""

import os
import asyncio
import subprocess
from pathlib import Path
from typing import Optional, List
from dataclasses import dataclass


# 可用音色
EDGE_TTS_VOICES = {
    # 中文女声
    "xiaoxiao": "zh-CN-XiaoxiaoNeural",      # 新闻、小说
    "xiaoyi": "zh-CN-XiaoyiNeural",          # 卡通、活泼
    "xiaobei": "zh-CN-liaoning-XiaobeiNeural",  # 东北话
    "xiaoni": "zh-CN-shaanxi-XiaoniNeural",  # 陕西话
    # 中文男声
    "yunjian": "zh-CN-YunjianNeural",        # 体育、激情
    "yunxi": "zh-CN-YunxiNeural",            # 小说、阳光
    "yunxia": "zh-CN-YunxiaNeural",          # 卡通、可爱
    "yunyang": "zh-CN-YunyangNeural",         # 新闻、专业
}


@dataclass
class VoiceConfig:
    """音色配置"""
    voice_id: str
    rate: str = "+0%"    # 语速
    volume: str = "+0%"  # 音量
    pitch: str = "+0Hz"  # 音调


class TTSEngine:
    """TTS 引擎基类"""
    
    def __init__(self, output_dir: str = "~/Desktop/ShortDrama/audio"):
        self.output_dir = Path(output_dir).expanduser()
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def generate(self, text: str, output_path: str = None, **kwargs) -> str:
        """生成语音 - 子类实现"""
        raise NotImplementedError


class EdgeTTS(TTSEngine):
    """微软 Edge TTS - 免费、快速"""
    
    def __init__(self, output_dir: str = "~/Desktop/ShortDrama/audio"):
        super().__init__(output_dir)
        self.voices = EDGE_TTS_VOICES
    
    def generate(
        self,
        text: str,
        output_path: str = None,
        voice: str = "xiaoxiao",
        rate: str = "+0%",
        volume: str = "+0%",
        pitch: str = "+0Hz"
    ) -> str:
        """生成语音
        
        Args:
            text: 要转换的文本
            output_path: 输出路径
            voice: 音色 (xiaoxiao/xiaoyi/yunjian/yunxi...)
            rate: 语速 (+/-%)
            volume: 音量 (+/-%)
            pitch: 音调 (+/-Hz)
            
        Returns:
            生成的音频文件路径
        """
        if not output_path:
            import datetime
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = self.output_dir / f"edge_{ts}.mp3"
        
        voice_id = self.voices.get(voice, voice)
        
        # 使用 edge-tts 命令行
        cmd = [
            "edge-tts",
            "-t", text,
            "--write-media", str(output_path),
            "--voice", voice_id
        ]
        
        if rate != "+0%":
            cmd.extend(["--rate", rate])
        if volume != "+0%":
            cmd.extend(["--volume", volume])
        if pitch != "+0Hz":
            cmd.extend(["--pitch", pitch])
        
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            print(f"✅ Edge TTS 生成: {output_path}")
            return str(output_path)
        except subprocess.CalledProcessError as e:
            print(f"❌ Edge TTS 错误: {e.stderr}")
            return ""
    
    def list_voices(self) -> dict:
        """列出可用音色"""
        return self.voices


class ChatTTS(TTSEngine):
    """ChatTTS - 中文效果最好的开源 TTS"""
    
    def __init__(self, output_dir: str = "~/Desktop/ShortDrama/audio"):
        super().__init__(output_dir)
        self._client = None
    
    def _get_client(self):
        """懒加载 ChatTTS"""
        if self._client is None:
            try:
                import ChatTTS
                self._client = ChatTTS.ChatTTS()
                self._client.load(compile=False)
            except ImportError:
                print("⚠️ ChatTTS 未安装，运行: pip install chat-tts")
                return None
        return self._client
    
    def generate(
        self,
        text: str,
        output_path: str = None,
        voice: str = "female",
        temperature: float = 0.3,
        **kwargs
    ) -> str:
        """生成语音
        
        Args:
            text: 要转换的文本
            output_path: 输出路径
            voice: 音色 (female/male)
            temperature: 温度参数
            
        Returns:
            生成的音频文件路径
        """
        client = self._get_client()
        if not client:
            return ""
        
        if not output_path:
            import datetime
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = self.output_dir / f"chat_{ts}.wav"
        
        # 文本预处理
        text = text.replace("\n", " ")
        
        # 音色选择
        if voice == "female":
            rand_steve = client.sample_random_speaker()
            rand_steve['temperature'] = temperature
        else:
            rand_steve = client.sample_random_speaker()
            rand_steve['temperature'] = temperature
        
        # 生成
        wavs = client.generate(text, skip_refine_text=True, **rand_steve)
        
        # 保存
        client.save(wavs, str(output_path))
        
        print(f"✅ ChatTTS 生成: {output_path}")
        return str(output_path)


class CosyVoice(TTSEngine):
    """阿里 CosyVoice - 支持 Voice Cloning"""
    
    def __init__(self, output_dir: str = "~/Desktop/ShortDrama/audio"):
        super().__init__(output_dir)
        self._client = None
    
    def _get_client(self):
        """懒加载 CosyVoice"""
        if self._client is None:
            try:
                from cosyvoice import CosyVoice
                self._client = CosyVoice('cosyvoice2-0.5')
            except ImportError:
                print("⚠️ CosyVoice 未安装")
                return None
        return self._client
    
    def generate(
        self,
        text: str,
        output_path: str = None,
        voice_preset: str = "中文女声",
        **kwargs
    ) -> str:
        """生成语音
        
        Args:
            text: 要转换的文本
            output_path: 输出路径
            voice_preset: 音色预设
            
        Returns:
            生成的音频文件路径
        """
        client = self._get_client()
        if not client:
            return ""
        
        if not output_path:
            import datetime
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = self.output_dir / f"cosy_{ts}.wav"
        
        # 生成
        result = client.generate(text, stream=False)
        
        # 保存
        import soundfile as sf
        sf.write(output_path, result['audio'], result['sample_rate'])
        
        print(f"✅ CosyVoice 生成: {output_path}")
        return str(output_path)


class VoiceSelector:
    """统一配音入口"""
    
    ENGINES = {
        "edge": EdgeTTS,
        "chat": ChatTTS,
        "cosy": CosyVoice,
    }
    
    def __init__(self, default_engine: str = "edge"):
        self.default_engine = default_engine
        self._engines = {}
    
    def get_engine(self, name: str = None) -> TTSEngine:
        """获取 TTS 引擎"""
        name = name or self.default_engine
        
        if name not in self._engines:
            engine_class = self.ENGINES.get(name)
            if engine_class:
                self._engines[name] = engine_class()
            else:
                raise ValueError(f"未知引擎: {name}")
        
        return self._engines[name]
    
    def generate(
        self,
        text: str,
        output_path: str = None,
        engine: str = None,
        **kwargs
    ) -> str:
        """生成语音
        
        Args:
            text: 要转换的文本
            output_path: 输出路径
            engine: 引擎选择 (edge/chat/cosy)
            
        Returns:
            生成的音频文件路径
        """
        engine_obj = self.get_engine(engine)
        return engine_obj.generate(text, output_path, **kwargs)
    
    def list_engines(self) -> List[str]:
        """列出可用引擎"""
        return list(self.ENGINES.keys())


# 便捷函数
def generate_voice(
    text: str,
    output_path: str = None,
    engine: str = "edge",
    voice: str = "xiaoxiao"
) -> str:
    """生成语音的便捷函数
    
    Args:
        text: 要转换的文本
        output_path: 输出路径
        engine: 引擎 (edge/chat/cosy)
        voice: 音色
        
    Returns:
        生成的音频文件路径
    """
    selector = VoiceSelector(default_engine=engine)
    return selector.generate(text, output_path, voice=voice)


# 测试
if __name__ == "__main__":
    print("=== TTS 配音测试 ===\n")
    
    test_text = "仙人之姿，徒手摘星辰，天地为之变色。"
    
    # Edge TTS 测试
    print("1. Edge TTS 测试:")
    edge = EdgeTTS()
    result = edge.generate(test_text, voice="xiaoxiao")
    print(f"   结果: {result}\n")
    
    # 列出可用音色
    print("2. Edge TTS 可用音色:")
    for name, voice_id in edge.voices.items():
        print(f"   {name}: {voice_id}")
