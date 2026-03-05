#!/usr/bin/env python3
"""
字幕生成模块
使用 Whisper 语音识别生成字幕

用法：
    subtitle_gen = SubtitleGenerator(api_config)
    subtitle_path = await subtitle_gen.generate_from_audio(audio_path)
"""

import asyncio
import os
from dataclasses import dataclass
from typing import List, Optional

# Whisper
try:
    from faster_whisper import WhisperModel
    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False


@dataclass
class SubtitleSegment:
    """字幕片段"""
    id: int
    start: float      # 开始时间（秒）
    end: float       # 结束时间（秒）
    text: str        # 字幕文本


@dataclass
class SubtitleConfig:
    """字幕配置"""
    model_size: str = "large-v3"     # 模型大小: tiny / base / small / medium / large-v3
    device: str = "cpu"               # 设备: cpu / cuda
    compute_type: str = "int8"       # 计算类型: int8 / int16 / float16
    language: str = "zh"             # 语言: zh / en / auto
    initial_prompt: str = ""         # 初始提示
    word_timestamps: bool = True      # 词级时间戳


class SubtitleGenerator:
    """字幕生成器"""
    
    def __init__(self, api_config: dict = None, config: SubtitleConfig = None):
        self.api_config = api_config or {}
        self.config = config or SubtitleConfig()
        self._model = None
        
        # 从配置加载
        whisper_cfg = self.api_config.get("whisper", {})
        if whisper_cfg:
            self.config.model_size = whisper_cfg.get("model_size", self.config.model_size)
            self.config.device = whisper_cfg.get("device", self.config.device)
            self.config.compute_type = whisper_cfg.get("compute_type", self.config.compute_type)
    
    def _load_model(self):
        """加载 Whisper 模型"""
        if not WHISPER_AVAILABLE:
            raise RuntimeError("faster-whisper 未安装，请运行: pip install faster-whisper")
        
        if self._model is None:
            print(f"Loading Whisper model: {self.config.model_size}")
            self._model = WhisperModel(
                model_size_or_path=self.config.model_size,
                device=self.config.device,
                compute_type=self.config.compute_type
            )
    
    async def generate_from_audio(
        self, 
        audio_path: str, 
        output_path: str = None,
        format: str = "srt"
    ) -> str:
        """
        从音频生成字幕
        
        Args:
            audio_path: 音频文件路径
            output_path: 输出字幕文件路径
            format: 格式 (srt / vtt / txt)
            
        Returns:
            生成的字幕文件路径
        """
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Audio file not found: {audio_path}")
        
        if not output_path:
            base = os.path.splitext(audio_path)[0]
            output_path = f"{base}.{format}"
        
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        
        # 加载模型
        self._load_model()
        
        # 识别
        print(f"Transcribing: {audio_path}")
        
        def _sync_transcribe():
            segments, info = self._model.transcribe(
                audio_path,
                language=self.config.language,
                initial_prompt=self.config.initial_prompt,
                word_timestamps=self.config.word_timestamps,
                vad_filter=True,
                vad_parameters=dict(min_silence_duration_ms=500),
            )
            return list(segments), info
        
        loop = asyncio.get_event_loop()
        segments, info = await loop.run_in_executor(None, _sync_transcribe)
        
        print(f"Detected language: {info.language} (probability: {info.language_probability:.2f})")
        
        # 生成字幕文件
        if format == "srt":
            return await self._save_srt(segments, output_path)
        elif format == "vtt":
            return await self._save_vtt(segments, output_path)
        elif format == "txt":
            return await self._save_txt(segments, output_path)
        else:
            raise ValueError(f"Unknown format: {format}")
    
    async def _save_srt(self, segments, output_path: str) -> str:
        """保存为 SRT 格式"""
        def _generate():
            lines = []
            for i, segment in enumerate(segments, 1):
                start = self._format_srt_time(segment.start)
                end = self._format_srt_time(segment.end)
                text = segment.text.strip()
                lines.append(f"{i}\n{start} --> {end}\n{text}\n")
            
            with open(output_path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
        
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _generate)
        print(f"Saved SRT: {output_path}")
        return output_path
    
    async def _save_vtt(self, segments, output_path: str) -> str:
        """保存为 VTT 格式"""
        def _generate():
            lines = ["WEBVTT", ""]
            for segment in segments:
                start = self._format_vtt_time(segment.start)
                end = self._format_vtt_time(segment.end)
                text = segment.text.strip()
                lines.append(f"{start} --> {end}\n{text}\n")
            
            with open(output_path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
        
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _generate)
        print(f"Saved VTT: {output_path}")
        return output_path
    
    async def _save_txt(self, segments, output_path: str) -> str:
        """保存为纯文本格式"""
        def _generate():
            texts = [segment.text.strip() for segment in segments]
            with open(output_path, "w", encoding="utf-8") as f:
                f.write("\n".join(texts))
        
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _generate)
        print(f"Saved TXT: {output_path}")
        return output_path
    
    def _format_srt_time(self, seconds: float) -> str:
        """格式化 SRT 时间 (00:00:00,000)"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"
    
    def _format_vtt_time(self, seconds: float) -> str:
        """格式化 VTT 时间 (00:00:00.000)"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"
    
    def generate_from_script(
        self,
        script: str,
        duration: float,
        output_path: str = None,
        format: str = "srt"
    ) -> str:
        """
        从剧本文本生成字幕（按时间均分）
        
        适用于没有配音的情况
        
        Args:
            script: 剧本文本
            duration: 总时长（秒）
            output_path: 输出路径
            format: 格式
            
        Returns:
            字幕文件路径
        """
        # 按句分割
        lines = [l.strip() for l in script.split("\n") if l.strip()]
        
        if not lines:
            raise ValueError("Script is empty")
        
        # 计算每句时长
        total_chars = sum(len(l) for l in lines)
        if total_chars == 0:
            raise ValueError("No characters in script")
        
        segments = []
        current_time = 0.0
        
        for i, line in enumerate(lines):
            # 按字符数比例分配时间
            line_duration = (len(line) / total_chars) * duration
            end_time = current_time + line_duration
            
            segments.append(SubtitleSegment(
                id=i+1,
                start=current_time,
                end=end_time,
                text=line
            ))
            current_time = end_time
        
        # 写入文件
        if not output_path:
            output_path = f"output/subtitles/script.{format}"
        
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        
        def _save():
            if format == "srt":
                lines = []
                for seg in segments:
                    start = self._format_srt_time(seg.start)
                    end = self._format_srt_time(seg.end)
                    lines.append(f"{seg.id}\n{start} --> {end}\n{seg.text}\n")
                with open(output_path, "w", encoding="utf-8") as f:
                    f.write("\n".join(lines))
        
        import concurrent.futures
        executor = concurrent.futures.ThreadPoolExecutor()
        executor.submit(_save).result()
        executor.shutdown(wait=False)
        
        print(f"Generated script subtitle: {output_path}")
        return output_path
    
    def close(self):
        """释放模型"""
        if self._model:
            del self._model
            self._model = None


# 便捷函数
async def quick_subtitle(audio_path: str, output_path: str = None) -> str:
    """快速生成字幕"""
    config = SubtitleGenerator()
    return await config.generate_from_audio(audio_path, output_path)


if __name__ == "__main__":
    # 测试
    import sys
    
    if len(sys.argv) > 1:
        audio_file = sys.argv[1]
        output_file = sys.argv[2] if len(sys.argv) > 2 else None
        
        async def test():
            gen = SubtitleGenerator()
            path = await gen.generate_from_audio(audio_file, output_file)
            print(f"Generated: {path}")
        
        asyncio.run(test())
    else:
        print("Usage: python subtitle_generator.py <audio_file> [output_file]")
