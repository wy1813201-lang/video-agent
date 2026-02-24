"""
视频合成器
使用 FFmpeg 合成视频
"""

import os
import subprocess
from typing import List, Optional
from dataclasses import dataclass


@dataclass
class VideoScene:
    """视频场景"""
    image_path: str
    duration: float  # 秒
    transition: str = "fade"  # fade, slide, none


class VideoAssembler:
    """视频合成器"""
    
    def __init__(self, config):
        self.config = config
        self.resolution = config.resolution
        
        # 检查 ffmpeg
        self.ffmpeg_available = self._check_ffmpeg()
    
    def _check_ffmpeg(self) -> bool:
        """检查 ffmpeg 是否可用"""
        try:
            subprocess.run(
                ["ffmpeg", "-version"],
                capture_output=True,
                check=True
            )
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False
    
    def create_video_from_images(
        self,
        image_paths: List[str],
        output_path: str,
        duration_per_image: float = 3.0,
        transition: str = "fade",
        audio_path: Optional[str] = None
    ) -> bool:
        """
        从图片列表创建视频
        
        Args:
            image_paths: 图片路径列表
            output_path: 输出视频路径
            duration_per_image: 每张图片持续时间(秒)
            transition: 转场效果
            audio_path: 背景音乐路径
        
        Returns:
            是否成功
        """
        if not self.ffmpeg_available:
            print("❌ FFmpeg 不可用")
            return False
        
        if not image_paths:
            print("❌ 没有图片")
            return False
        
        print(f"🎬 合成视频: {len(image_paths)} 张图片")
        
        # 创建临时文件列表
        list_file = output_path + ".txt"
        with open(list_file, 'w') as f:
            for img in image_paths:
                if os.path.exists(img):
                    f.write(f"file '{img}'\n")
                    f.write(f"duration {duration_per_image}\n")
        
        try:
            # 基础命令
            cmd = [
                "ffmpeg",
                "-y",  # 覆盖输出
                "-f", "concat",
                "-safe", "0",
                "-i", list_file,
                "-vf", f"scale={self._parse_resolution()}",
                "-c:v", "libx264",
                "-pix_fmt", "yuv420p",
                "-preset", "fast",
                "-crf", "23"
            ]
            
            # 添加音频
            if audio_path and os.path.exists(audio_path):
                cmd.extend(["-i", audio_path, "-c:a", "aac", "-b:a", "128k"])
            
            cmd.append(output_path)
            
            # 执行
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                print(f"✅ 视频保存到: {output_path}")
                return True
            else:
                print(f"❌ FFmpeg 错误: {result.stderr}")
                return False
                
        except Exception as e:
            print(f"❌ 错误: {e}")
            return False
        finally:
            # 清理临时文件
            if os.path.exists(list_file):
                os.remove(list_file)
    
    def add_text_overlay(
        self,
        input_video: str,
        output_video: str,
        text: str,
        position: str = "bottom",
        font_size: int = 24,
        font_color: str = "white"
    ) -> bool:
        """添加文字水印"""
        if not self.ffmpeg_available:
            return False
        
        # 位置映射
        pos_map = {
            "top": "10:main_h-th-10",
            "bottom": "10:10",
            "center": "(w-text_w)/2:(h-text_h)/2"
        }
        
        position_expr = pos_map.get(position, "10:10")
        
        cmd = [
            "ffmpeg", "-y",
            "-i", input_video,
            "-vf", f"drawtext=text='{text}':fontcolor={font_color}:fontsize={font_size}:x={position_expr}",
            "-codec:a", "copy",
            output_video
        ]
        
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            return True
        except subprocess.CalledProcessError:
            return False
    
    def add_subtitles(
        self,
        input_video: str,
        output_video: str,
        subtitles: List[dict]
    ) -> bool:
        """添加字幕"""
        # subtitles 格式: [{"start": 0, "end": 3, "text": "对话内容"}]
        if not subtitles:
            return False
        
        # 生成 srt 字幕文件
        srt_path = output_video + ".srt"
        
        with open(srt_path, 'w', encoding='utf-8') as f:
            for i, sub in enumerate(subtitles, 1):
                start = self._format_srt_time(sub.get("start", 0))
                end = self._format_srt_time(sub.get("end", 3))
                text = sub.get("text", "")
                f.write(f"{i}\n{start} --> {end}\n{text}\n\n")
        
        cmd = [
            "ffmpeg", "-y",
            "-i", input_video,
            "-vf", f"subtitles={srt_path}",
            "-codec:a", "copy",
            output_video
        ]
        
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            os.remove(srt_path)
            return True
        except subprocess.CalledProcessError:
            return False
    
    def extract_audio(self, input_video: str, output_audio: str) -> bool:
        """提取音频"""
        if not self.ffmpeg_available:
            return False
        
        cmd = [
            "ffmpeg", "-y",
            "-i", input_video,
            "-vn",
            "-acodec", "libmp3lame",
            "-q:a", "2",
            output_audio
        ]
        
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            return True
        except subprocess.CalledProcessError:
            return False
    
    def _parse_resolution(self) -> str:
        """解析分辨率"""
        # 默认 1080x1920 (竖屏)
        w, h = self.resolution.split('x')
        return f"{w}:{h}"
    
    def _format_srt_time(self, seconds: float) -> str:
        """格式化 SRT 时间"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


class BrowserVideoGenerator:
    """基于浏览器自动化的视频生成器"""
    # 这个类可以扩展，使用 Playwright/Selenium 
    # 自动操作在线 AI 视频生成平台
    
    def __init__(self, config):
        self.config = config
    
    async def generate_with_runway(self, prompt: str, output_path: str) -> bool:
        """使用 Runway ML 生成视频"""
        # 需要 Playwright 和登录
        # 这是一个框架示例
        pass
    
    async def generate_with_pika(self, prompt: str, output_path: str) -> bool:
        """使用 Pika Labs 生成视频"""
        pass
    
    async def generate_with_kling(self, prompt: str, output_path: str) -> bool:
        """使用可灵 AI 生成视频"""
        pass
