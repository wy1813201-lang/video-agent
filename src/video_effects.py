"""
专业视频特效模块
基于 FFmpeg 的高级视频剪辑效果
"""

import subprocess
import os
import json
from typing import List, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass


@dataclass
class TransitionEffect:
    """转场效果"""
    name: str  # fade, dissolve, wipe, zoom, blur
    duration: float = 1.0  # 秒
    
    # fade 参数
    fade_color: str = "black"
    
    # wipe 参数
    wipe_direction: str = "left"  # left, right, up, down
    
    # zoom 参数
    zoom_from: float = 1.0
    zoom_to: float = 1.5


@dataclass
class ColorGrade:
    """调色参数"""
    brightness: float = 0.0      # -1.0 ~ 1.0
    contrast: float = 1.0        # 0.0 ~ 2.0
    saturation: float = 1.0      # 0.0 ~ 3.0
    temperature: float = 0.0     # -100 ~ 100 (色温)
    tint: float = 0.0            # -100 ~ 100 (色调)
    vignette: float = 0.0        # 0.0 ~ 1.0 (暗角强度)
    sharpen: float = 0.0         # 0.0 ~ 5.0


class VideoEffects:
    """专业视频特效处理器"""
    
    def __init__(self, output_dir: str = "~/Desktop/ShortDrama/videos"):
        self.output_dir = Path(output_dir).expanduser()
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def _run_ffmpeg(self, cmd: List[str]) -> Tuple[bool, str]:
        """执行 FFmpeg 命令"""
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )
            return True, result.stderr
        except subprocess.CalledProcessError as e:
            return False, e.stderr
    
    # ==================== 转场效果 ====================
    
    def add_fade_transition(
        self,
        input_video: str,
        output_video: str,
        fade_in: float = 0.5,
        fade_out: float = 0.5,
        color: str = "black"
    ) -> bool:
        """添加淡入淡出转场"""
        duration = self._get_duration(input_video)
        
        cmd = [
            "ffmpeg", "-y",
            "-i", input_video,
            "-vf", f"fade=t=in:st=0:d={fade_in}:color={color},fade=t=out:st={duration-fade_out}:d={fade_out}:color={color}",
            "-c:a", "copy",
            output_video
        ]
        
        ok, msg = self._run_ffmpeg(cmd)
        if ok:
            print(f"✅ 添加淡入淡出: {output_video}")
        return ok
    
    def add_dissolve_transition(
        self,
        input_videos: List[str],
        output_video: str,
        transition_duration: float = 1.0
    ) -> bool:
        """添加溶解转场（视频拼接）"""
        if len(input_videos) < 2:
            return False
        
        # 创建 concat 列表文件
        list_file = self.output_dir / "concat_list.txt"
        with open(list_file, 'w') as f:
            for v in input_videos:
                f.write(f"file '{v}'\n")
        
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(list_file),
            "-c", "copy",
            output_video
        ]
        
        ok, msg = self._run_ffmpeg(cmd)
        list_file.unlink(missing_ok=True)
        
        if ok:
            print(f"✅ 溶解拼接: {output_video}")
        return ok
    
    def add_wipe_transition(
        self,
        input_video: str,
        output_video: str,
        transition_video: str,
        direction: str = "left",
        duration: float = 1.0
    ) -> bool:
        """添加擦除转场（需要 xfade filter）"""
        # xfade direction: left, right, up, down
        offset = self._get_duration(input_video) - duration
        
        cmd = [
            "ffmpeg", "-y",
            "-i", input_video,
            "-i", transition_video,
            "-filter_complex", 
            f"[0:v][1:v]xfade=transition=wipeleft:duration={duration}:offset={offset}[out]",
            "-map", "[out]",
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            output_video
        ]
        
        ok, msg = self._run_ffmpeg(cmd)
        if ok:
            print(f"✅ 添加擦除转场: {output_video}")
        return ok
    
    # ==================== 动态缩放 ====================
    
    def add_zoom_effect(
        self,
        input_video: str,
        output_video: str,
        zoom_type: str = "in",  # in, out, pan
        speed: float = 1.0,
        duration: Optional[float] = None
    ) -> bool:
        """添加缩放效果
        
        Args:
            zoom_type: in(推进), out(拉远), pan(推拉)
            speed: 速度倍数
        """
        dur = duration or self._get_duration(input_video)
        
        if zoom_type == "in":
            # 推进效果：zoom 1->1.5
            filter_str = f"zoompan=z='min(zoom+0.001,1.5)':d={int(dur*25)}:s=704x1250"
        elif zoom_type == "out":
            # 拉远效果：zoom 1.5->1
            filter_str = f"zoompan=z='max(1.5-0.001*(on/25),1)':d={int(dur*25)}:s=704x1250"
        else:
            # 推拉交替
            filter_str = f"zoompan=z='1+0.5*sin(0.1*on)':d={int(dur*25)}:s=704x1250"
        
        cmd = [
            "ffmpeg", "-y",
            "-i", input_video,
            "-vf", filter_str,
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            output_video
        ]
        
        ok, msg = self._run_ffmpeg(cmd)
        if ok:
            print(f"✅ 添加缩放效果({zoom_type}): {output_video}")
        return ok
    
    def add_ken_burns(
        self,
        input_video: str,
        output_video: str,
        start_x: float = 0,
        start_y: float = 0,
        end_x: float = 10,
        end_y: float = 10,
        duration: Optional[float] = None
    ) -> bool:
        """添加肯汀堡效果（电影感推拉）"""
        dur = duration or self._get_duration(input_video)
        
        cmd = [
            "ffmpeg", "-y",
            "-i", input_video,
            "-vf", f"zoompan=z='1+0.5*((on/{int(dur*25)})-0.5)':x='{start_x}+{end_x}*((on/{int(dur*25)})-0.5)':y='{start_y}+{end_y}*((on/{int(dur*25)})-0.5)':d={int(dur*25)}:s=704x1250",
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            output_video
        ]
        
        ok, msg = self._run_ffmpeg(cmd)
        if ok:
            print(f"✅ 添加肯汀堡效果: {output_video}")
        return ok
    
    # ==================== 调色 ====================
    
    def add_color_grade(
        self,
        input_video: str,
        output_video: str,
        grade: Optional[ColorGrade] = None,
        preset: str = "cinematic"  # cinematic, warm, cool, vintage, noir
    ) -> bool:
        """添加调色"""
        if grade is None:
            grade = self._get_preset_grade(preset)
        
        # 构建 eq 滤镜
        filters = []
        
        if grade.brightness != 0:
            filters.append(f"eq=brightness={grade.brightness}")
        if grade.contrast != 1.0:
            filters.append(f"eq=contrast={grade.contrast}")
        if grade.saturation != 1.0:
            filters.append(f"eq=saturation={grade.saturation}")
        
        if grade.temperature != 0:
            filters.append(f"colortemperature=temperature={6500 + grade.temperature*50}")
        
        if grade.tint != 0:
            filters.append(f"colortemperature=tint={grade.tint}")
        
        if grade.vignette > 0:
            filters.append(f"vignette=angle={grade.vignette}")
        
        if grade.sharpen > 0:
            filters.append(f"unsharp=5:5:{grade.sharpen}:5:5:0")
        
        if not filters:
            filters = ["null"]
        
        filter_str = ",".join(filters)
        
        cmd = [
            "ffmpeg", "-y",
            "-i", input_video,
            "-vf", filter_str,
            "-c:a", "copy",
            output_video
        ]
        
        ok, msg = self._run_ffmpeg(cmd)
        if ok:
            print(f"✅ 添加调色({preset}): {output_video}")
        return ok
    
    def _get_preset_grade(self, preset: str) -> ColorGrade:
        """获取预设调色"""
        presets = {
            "cinematic": ColorGrade(
                contrast=1.2,
                saturation=0.9,
                temperature=-10,
                vignette=0.3,
                sharpen=1.0
            ),
            "warm": ColorGrade(
                temperature=20,
                saturation=1.1
            ),
            "cool": ColorGrade(
                temperature=-20,
                saturation=0.95
            ),
            "vintage": ColorGrade(
                contrast=1.1,
                saturation=0.7,
                temperature=15,
                vignette=0.4
            ),
            "noir": ColorGrade(
                contrast=1.5,
                saturation=0.0,
                brightness=-0.1,
                vignette=0.5
            ),
        }
        return presets.get(preset, ColorGrade())
    
    # ==================== 画中画 ====================
    
    def add_pip(
        self,
        input_video: str,
        pip_video: str,
        output_video: str,
        position: str = "top-right",
        scale: float = 0.3,
        border: bool = True
    ) -> bool:
        """添加画中画
        
        Args:
            position: top-left, top-right, bottom-left, bottom-right, center
            scale: 缩放比例
            border: 是否添加边框
        """
        pos_map = {
            "top-left": "10:10",
            "top-right": "W-w-10:10",
            "bottom-left": "10:H-h-10",
            "bottom-right": "W-w-10:H-h-10",
            "center": "(W-w)/2:(H-h)/2"
        }
        
        pos = pos_map.get(position, "W-w-10:10")
        
        # 缩放 pip 视频
        scale_filter = f"scale=iw*{scale}:ih*{scale}"
        
        # 边框
        if border:
            scale_filter += ",pad=iw+4:ih+4:(ow-iw)/2:(oh-ih)/2:black"
        
        cmd = [
            "ffmpeg", "-y",
            "-i", input_video,
            "-i", pip_video,
            "-filter_complex", 
            f"[1:v]{scale_filter}[pip];[0:v][pip]overlay={pos}",
            "-c:a", "copy",
            output_video
        ]
        
        ok, msg = self._run_ffmpeg(cmd)
        if ok:
            print(f"✅ 添加画中画({position}): {output_video}")
        return ok
    
    def add_text_overlay(
        self,
        input_video: str,
        output_video: str,
        text: str,
        position: str = "bottom-center",
        font_size: int = 32,
        font_color: str = "white",
        font_file = ""  # 使用默认字体
        shadow: bool = True,
        bg_color: Optional[str] = None
    ) -> bool:
        """添加文字字幕"""
        pos_map = {
            "top-center": "(w-text_w)/2:20",
            "bottom-center": "(w-text_w)/2:h-text_h-20",
            "center": "(w-text_w)/2:(h-text_h)/2"
        }
        
        pos = pos_map.get(position, "(w-text_w)/2:h-text_h-20")
        
        # 构建 drawtext
        if shadow:
            drawtext = f"drawtext=fontfile='{font_file}':text='{text}':fontcolor={font_color}:fontsize={font_size}:x={pos}:shadowcolor=black:shadowx=2:shadowy=2"
        else:
            drawtext = f"drawtext=fontfile='{font_file}':text='{text}':fontcolor={font_color}:fontsize={font_size}:x={pos}"
        
        cmd = [
            "ffmpeg", "-y",
            "-i", input_video,
            "-vf", drawtext,
            "-c:a", "copy",
            output_video
        ]
        
        ok, msg = self._run_ffmpeg(cmd)
        if ok:
            print(f"✅ 添加字幕: {output_video}")
        return ok
    
    # ==================== 变速 ====================
    
    def speed_ramp(
        self,
        input_video: str,
        output_video: str,
        speed: float = 1.0,
        keep_audio_pitch: bool = True
    ) -> bool:
        """变速（快慢动作）"""
        # speed > 1 加速, speed < 1 慢动作
        
        if speed == 1.0:
            return False
        
        if keep_audio_pitch:
            # 保持音调变速 (视频变速，音频变调)
            cmd = [
                "ffmpeg", "-y",
                "-i", input_video,
                "-filter_complex", f"[0:v]setpts={1/speed}*PTS[v];[0:a]atempo={speed}[a]",
                "-map", "[v]",
                "-map", "[a]",
                "-c:v", "libx264",
                "-pix_fmt", "yuv420p",
                output_video
            ]
        else:
            # 简单变速
            cmd = [
                "ffmpeg", "-y",
                "-i", input_video,
                "-filter_complex", f"[0:v]setpts={1/speed}*PTS[v]",
                "-map", "[v]",
                "-c:v", "libx264",
                "-pix_fmt", "yuv420p",
                output_video
            ]
        
        ok, msg = self._run_ffmpeg(cmd)
        if ok:
            print(f"✅ 变速效果({speed}x): {output_video}")
        return ok
    
    def add_slow_motion(
        self,
        input_video: str,
        output_video: str,
        slow_factor: float = 0.5
    ) -> bool:
        """添加慢动作"""
        return self.speed_ramp(input_video, output_video, slow_factor, keep_audio_pitch=True)
    
    # ==================== 特效组合 ====================
    
    def apply_cinematic_look(
        self,
        input_video: str,
        output_video: str,
        preset: str = "cinematic"
    ) -> bool:
        """应用电影感效果（调色+暗角+锐化）"""
        return self.add_color_grade(input_video, output_video, preset=preset)
    
    def create_hero_shot(
        self,
        input_video: str,
        output_video: str,
        text: str,
        title: str = ""
    ) -> bool:
        """创建英雄镜头（开场画面）"""
        # 1. 添加暗角和调色
        temp1 = self.output_dir / "temp_grade.mp4"
        self.add_color_grade(input_video, str(temp1), preset="cinematic")
        
        # 2. 添加标题文字
        if title:
            temp2 = self.output_dir / "temp_title.mp4"
            self.add_text_overlay(str(temp1), str(temp2), title, position="bottom-center", font_size=48)
        else:
            temp2 = temp1
        
        # 3. 重命名
        import shutil
        shutil.move(str(temp2), output_video)
        
        for f in [temp1, temp2]:
            if f.exists() and f != output_video:
                f.unlink(missing_ok=True)
        
        return True
    
    # ==================== 工具 ====================
    
    def _get_duration(self, video_path: str) -> float:
        """获取视频时长"""
        cmd = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            video_path
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return float(result.stdout.strip())
        except:
            return 5.0
    
    def get_video_info(self, video_path: str) -> dict:
        """获取视频信息"""
        cmd = [
            "ffprobe",
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            video_path
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return json.loads(result.stdout)
        except:
            return {}


# 便捷函数
def create_zoom_in_effect(input_video: str, output_video: str) -> bool:
    """创建推进效果"""
    effects = VideoEffects()
    return effects.add_zoom_effect(input_video, output_video, zoom_type="in")


def create_hero_intro(input_video: str, output_video: str, title: str) -> bool:
    """创建开场标题"""
    effects = VideoEffects()
    return effects.create_hero_shot(input_video, output_video, title)


def apply_cinematic_grade(input_video: str, output_video: str) -> bool:
    """应用电影感调色"""
    effects = VideoEffects()
    return effects.add_color_grade(input_video, output_video, preset="cinematic")
