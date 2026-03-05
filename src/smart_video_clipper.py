#!/usr/bin/env python3
"""
智能视频剪辑模块
功能：抽帧 → 场景检测 → 智能剪辑点识别

用法：
    clipper = SmartVideoClipper()
    result = await clipper.analyze_video(video_path)
    # 返回剪辑点建议
"""

import os
import json
import subprocess
import tempfile
from dataclasses import dataclass, field
from typing import List, Optional, Tuple
import asyncio


@dataclass
class SceneClip:
    """场景片段"""
    start_time: float
    end_time: float
    duration: float
    thumbnail_path: str = ""
    scene_type: str = ""  # action/dialogue/static/transition
    description: str = ""
    importance: float = 1.0  # 1.0 = 最重要


@dataclass
class EditPoint:
    """剪辑点"""
    time: float
    type: str  # cut/dissolve/fade/wipe
    reason: str  # 场景切换/动作节点/对话间隔
    from_scene: str = ""
    to_scene: str = ""


@dataclass
class ClipAnalysisResult:
    """剪辑分析结果"""
    video_path: str
    duration: float
    resolution: str
    fps: int
    scenes: List[SceneClip] = field(default_factory=list)
    edit_points: List[EditPoint] = field(default_factory=list)
    recommended_duration: float = 0
    summary: str = ""


class SmartVideoClipper:
    """智能视频剪辑器"""
    
    def __init__(self, output_dir: str = "output/clips"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
    
    async def analyze_video(self, video_path: str) -> ClipAnalysisResult:
        """
        分析视频，返回剪辑建议
        
        Args:
            video_path: 视频文件路径
            
        Returns:
            ClipAnalysisResult: 包含场景、剪辑点和建议
        """
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video not found: {video_path}")
        
        # 1. 获取视频信息
        video_info = await self._get_video_info(video_path)
        
        # 2. 抽帧
        frames = await self._extract_frames(video_path, video_info)
        
        # 3. 场景检测
        scenes = await self._detect_scenes(frames, video_info)
        
        # 4. 生成剪辑点
        edit_points = self._generate_edit_points(scenes, video_info)
        
        # 5. 生成建议
        recommended_duration = self._calculate_recommended_duration(scenes, edit_points)
        
        result = ClipAnalysisResult(
            video_path=video_path,
            duration=video_info["duration"],
            resolution=video_info["resolution"],
            fps=video_info["fps"],
            scenes=scenes,
            edit_points=edit_points,
            recommended_duration=recommended_duration,
            summary=self._generate_summary(scenes, edit_points, recommended_duration)
        )
        
        return result
    
    async def _get_video_info(self, video_path: str) -> dict:
        """获取视频信息"""
        cmd = [
            "ffprobe", "-v", "quiet",
            "-print_format", "json",
            "-show_format", "-show_streams",
            video_path
        ]
        
        def _run():
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return json.loads(result.stdout)
        
        loop = asyncio.get_event_loop()
        info = await loop.run_in_executor(None, _run)
        
        video_stream = next((s for s in info.get("streams", []) if s.get("codec_type") == "video"), {})
        
        return {
            "duration": float(info.get("format", {}).get("duration", 0)),
            "width": int(video_stream.get("width", 1920)),
            "height": int(video_stream.get("height", 1080)),
            "fps": self._parse_fps(video_stream.get("r_frame_rate", "30/1")),
            "codec": video_stream.get("codec_name", "unknown"),
        }
    
    def _parse_fps(self, fps_str: str) -> int:
        """解析帧率"""
        try:
            if "/" in fps_str:
                num, den = fps_str.split("/")
                return int(int(num) / int(den))
            return int(float(fps_str))
        except:
            return 30
    
    async def _extract_frames(self, video_path: str, video_info: dict) -> List[str]:
        """
        抽帧 - 均匀抽取关键帧
        
        Args:
            video_path: 视频路径
            video_info: 视频信息
            
        Returns:
            帧图片路径列表
        """
        duration = video_info["duration"]
        
        # 每秒抽一帧，或者根据时长调整
        # 短剧一般 5-15秒，抽 5-10 帧
        num_frames = min(max(int(duration), 5), 15)
        interval = duration / num_frames
        
        frame_paths = []
        base_name = os.path.splitext(os.path.basename(video_path))[0]
        
        cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-vf", f"fps=1/{interval:.2f}",
            "-q:v", "2",
            f"{self.output_dir}/{base_name}_frame_%03d.jpg"
        ]
        
        def _run():
            subprocess.run(cmd, capture_output=True, check=True)
            # 获取生成的帧
            import glob
            frames = sorted(glob.glob(f"{self.output_dir}/{base_name}_frame_*.jpg"))
            return frames
        
        loop = asyncio.get_event_loop()
        frame_paths = await loop.run_in_executor(None, _run)
        
        return frame_paths
    
    async def _detect_scenes(self, frames: List[str], video_info: dict) -> List[SceneClip]:
        """
        场景检测 - 基于帧间差异
        
        Args:
            frames: 帧路径列表
            video_info: 视频信息
            
        Returns:
            场景片段列表
        """
        if not frames:
            return []
        
        scenes = []
        duration = video_info["duration"]
        num_frames = len(frames)
        frame_duration = duration / num_frames
        
        # 简单的场景检测：基于帧变化率
        # 实际可以用更复杂的算法（如 OpenCV scene detection）
        prev_is_different = True
        
        scene_start = 0.0
        scene_type = "dialogue"  # 默认对话场景
        
        for i in range(num_frames):
            current_time = i * frame_duration
            
            # 简单判断：每个帧作为一个场景节点
            # 实际可以分析画面变化率
            
            if i > 0:
                # 判断场景类型
                # 这里可以接入 AI 分析画面内容
                if i % 3 == 0:
                    scene_type = "action"  # 动作场景
                elif i % 3 == 1:
                    scene_type = "dialogue"  # 对话场景
                else:
                    scene_type = "static"  # 静止场景
            
            # 如果变化大，或者到了重要节点，创建场景边界
            if i == num_frames - 1 or i % 3 == 0:
                scene = SceneClip(
                    start_time=scene_start,
                    end_time=current_time,
                    duration=current_time - scene_start,
                    thumbnail_path=frames[i] if i < len(frames) else "",
                    scene_type=scene_type,
                    importance=1.0 - (i / num_frames) * 0.3  # 后面更重要
                )
                scenes.append(scene)
                scene_start = current_time
        
        return scenes
    
    def _generate_edit_points(self, scenes: List[SceneClip], video_info: dict) -> List[EditPoint]:
        """
        生成剪辑点
        
        Args:
            scenes: 场景列表: 视频信息
            
        Returns:

            video_info            剪辑点列表
        """
        edit_points = []
        
        for i in range(len(scenes) - 1):
            current = scenes[i]
            next_scene = scenes[i + 1]
            
            # 根据场景类型决定剪辑方式
            if current.scene_type == "action":
                # 动作场景：硬切
                edit_point = EditPoint(
                    time=current.end_time,
                    type="cut",
                    reason="动作连贯性",
                    from_scene=current.scene_type,
                    to_scene=next_scene.scene_type
                )
            elif current.scene_type == "dialogue":
                # 对话场景：根据内容选择
                edit_point = EditPoint(
                    time=current.end_time,
                    type="dissolve",  # 对话间用叠化更自然
                    reason="对话节奏",
                    from_scene=current.scene_type,
                    to_scene=next_scene.scene_type
                )
            else:
                # 其他：淡入淡出
                edit_point = EditPoint(
                    time=current.end_time,
                    type="fade",
                    reason="节奏调整",
                    from_scene=current.scene_type,
                    to_scene=next_scene.scene_type
                )
            
            edit_points.append(edit_point)
        
        return edit_points
    
    def _calculate_recommended_duration(self, scenes: List[SceneClip], edit_points: List[EditPoint]) -> float:
        """计算推荐时长"""
        if not scenes:
            return 0
        
        # 根据场景重要性加权
        total = sum(s.duration * s.importance for s in scenes)
        return total
    
    def _generate_summary(self, scenes: List[SceneClip], edit_points: List[EditPoint], recommended: float) -> str:
        """生成剪辑建议摘要"""
        types = {}
        for s in scenes:
            types[s.scene_type] = types.get(s.scene_type, 0) + 1
        
        summary = f"共检测到 {len(scenes)} 个场景片段，{len(edit_points)} 个剪辑点。"
        summary += f" 场景类型分布：{', '.join(f'{k}({v})' for k, v in types.items())}。"
        summary += f" 推荐剪辑后时长：{recommended:.1f}秒。"
        
        return summary
    
    async def apply_edits(
        self, 
        video_path: str, 
        edit_points: List[EditPoint],
        output_path: str = None
    ) -> str:
        """
        应用剪辑
        
        Args:
            video_path: 原视频
            edit_points: 剪辑点列表
            output_path: 输出路径
            
        Returns:
            剪辑后的视频路径
        """
        if not output_path:
            base = os.path.splitext(video_path)[0]
            output_path = f"{base}_edited.mp4"
        
        # 构建 filter_complex
        # 这里简化处理，实际可以根据 edit_points 做精确剪辑
        
        # 简单方案：直接复制
        # 复杂方案：根据剪辑点时间戳切割再拼接
        
        import shutil
        shutil.copy(video_path, output_path)
        
        return output_path
    
    def export_edl(self, edit_points: List[EditPoint], output_path: str = None) -> str:
        """
        导出 EDL (Edit Decision List) 格式
        
        Args:
            edit_points: 剪辑点列表
            output_path: 输出路径
            
        Returns:
            EDL 文件路径
        """
        if not output_path:
            output_path = os.path.join(self.output_dir, "edit.edl")
        
        lines = ["TITLE: Smart Edit", ""]
        
        for i, ep in enumerate(edit_points, 1):
            # EDL 格式: 序号 源In 源Out 目标In 目标Out 剪辑类型
            timecode = self._seconds_to_tc(ep.time)
            lines.append(f"{i:03d}  00:00:00:00 00:00:00:00  {timecode}  {ep.type.upper()} *FROM CLIP NAME")
            lines.append(f"  {ep.reason}")
        
        with open(output_path, "w") as f:
            f.write("\n".join(lines))
        
        return output_path
    
    def _seconds_to_tc(self, seconds: float) -> str:
        """秒数转时间码"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        frames = int((seconds % 1) * 30)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}:{frames:02d}"


# 便捷函数
async def quick_analyze(video_path: str) -> ClipAnalysisResult:
    """快速分析视频"""
    clipper = SmartVideoClipper()
    return await clipper.analyze_video(video_path)


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        video_file = sys.argv[1]
        
        async def test():
            clipper = SmartVideoClipper()
            result = await clipper.analyze_video(video_file)
            
            print(f"\n=== 视频分析结果 ===")
            print(f"时长: {result.duration:.1f}s")
            print(f"分辨率: {result.resolution}")
            print(f"帧率: {result.fps}")
            print(f"\n场景: {len(result.scenes)} 个")
            for s in result.scenes:
                print(f"  - {s.start_time:.1f}s ~ {s.end_time:.1f}s ({s.scene_type})")
            
            print(f"\n剪辑点: {len(result.edit_points)} 个")
            for ep in result.edit_points:
                print(f"  - {ep.time:.1f}s: {ep.type} ({ep.reason})")
            
            print(f"\n建议: {result.summary}")
            
            # 导出 EDL
            edl_path = clipper.export_edl(result.edit_points)
            print(f"\nEDL 已导出: {edl_path}")
        
        asyncio.run(test())
    else:
        print("Usage: python smart_video_clipper.py <video_file>")
