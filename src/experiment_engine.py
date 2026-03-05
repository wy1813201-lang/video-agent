#!/usr/bin/env python3
"""
Experiment Engine - 实验版本生成引擎

职责：
1. 根据实验参数生成多个版本
2. 管理实验版本的生成流程
3. 支持参数化变体生成
"""

import asyncio
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass
from enum import Enum


class ExperimentStage(str, Enum):
    """实验阶段"""
    SCRIPT = "script"
    STORYBOARD = "storyboard"
    VIDEO = "video"


@dataclass
class ExperimentConfig:
    """实验配置"""
    stage: ExperimentStage
    base_content: Any  # 基础内容
    params_list: List[Dict[str, Any]]  # 实验参数列表
    generator_fn: Callable  # 生成函数


class ExperimentEngine:
    """
    实验引擎

    用法：
        engine = ExperimentEngine()
        versions = await engine.run_experiment(config)
    """

    def __init__(self):
        self.current_experiments: List[Any] = []

    async def run_experiment(self, config: ExperimentConfig) -> List[Dict[str, Any]]:
        """
        运行实验，生成多个版本

        Returns:
            List of {version_id, params, content}
        """
        print(f"\n🧪 [ExperimentEngine] 开始实验: {config.stage.value}")
        print(f"   基础内容: {type(config.base_content).__name__}")
        print(f"   实验版本数: {len(config.params_list)}")

        versions = []

        for idx, params in enumerate(config.params_list, 1):
            version_id = f"{config.stage.value}_v{idx}"
            print(f"\n   [版本 {idx}] {version_id}")
            print(f"   参数: {params}")

            try:
                # 调用生成函数，传入参数
                content = await self._generate_variant(
                    config.generator_fn,
                    config.base_content,
                    params
                )

                versions.append({
                    "version_id": version_id,
                    "params": params,
                    "content": content
                })

                print(f"   ✓ 生成成功")

            except Exception as e:
                print(f"   ✗ 生成失败: {e}")
                continue

        print(f"\n✓ 实验完成: 成功生成 {len(versions)}/{len(config.params_list)} 个版本")
        return versions

    async def _generate_variant(
        self,
        generator_fn: Callable,
        base_content: Any,
        params: Dict[str, Any]
    ) -> Any:
        """
        生成变体版本

        根据参数调整生成逻辑
        """
        # 如果生成函数是异步的
        if asyncio.iscoroutinefunction(generator_fn):
            return await generator_fn(base_content, params)
        else:
            # 同步函数，在executor中运行
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, generator_fn, base_content, params)


# ================================================================
# 实验参数生成器
# ================================================================

class ExperimentParamsGenerator:
    """实验参数生成器"""

    @staticmethod
    def generate_script_params() -> List[Dict[str, Any]]:
        """生成剧本实验参数"""
        return [
            {
                "name": "快节奏版",
                "conflict_timing": "immediate",  # 立即冲突
                "reversal_count": 3,             # 3个反转
                "emotion_intensity": "extreme",  # 极端情绪
                "scene_count": 4,                # 4个场景
                "hook_style": "shock"            # 震惊式开头
            },
            {
                "name": "标准版",
                "conflict_timing": "early",      # 早期冲突
                "reversal_count": 2,             # 2个反转
                "emotion_intensity": "high",     # 高强度情绪
                "scene_count": 5,                # 5个场景
                "hook_style": "mystery"          # 悬念式开头
            },
        ]

    @staticmethod
    def generate_storyboard_params() -> List[Dict[str, Any]]:
        """生成分镜实验参数"""
        return [
            {
                "name": "动态版",
                "shot_count_multiplier": 1.2,    # 镜头数量 +20%
                "closeup_ratio": 0.5,            # 特写比例 50%
                "camera_motion": "dynamic",      # 动态运镜
                "cut_speed": "fast"              # 快速剪辑
            },
            {
                "name": "稳定版",
                "shot_count_multiplier": 0.9,    # 镜头数量 -10%
                "closeup_ratio": 0.3,            # 特写比例 30%
                "camera_motion": "stable",       # 稳定运镜
                "cut_speed": "medium"            # 中速剪辑
            },
        ]

    @staticmethod
    def generate_video_params() -> List[Dict[str, Any]]:
        """生成视频实验参数"""
        return [
            {
                "name": "暖色调版",
                "color_grade": "warm",           # 暖色调
                "transition_style": "dissolve",  # 溶解转场
                "music_intensity": "high",       # 高强度音乐
                "subtitle_style": "bold"         # 粗体字幕
            },
            {
                "name": "电影感版",
                "color_grade": "cinematic",      # 电影感调色
                "transition_style": "fade",      # 淡入淡出
                "music_intensity": "medium",     # 中等音乐
                "subtitle_style": "elegant"      # 优雅字幕
            },
        ]


# ================================================================
# 实验版本生成器（具体实现）
# ================================================================

class ScriptVariantGenerator:
    """剧本变体生成器"""

    def __init__(self, script_generator):
        self.script_generator = script_generator

    async def generate(self, base_script: str, params: Dict[str, Any]) -> str:
        """
        根据参数生成剧本变体

        简化版：在原剧本基础上添加提示词引导
        """
        # 构建变体提示词
        variant_prompt = self._build_variant_prompt(params)

        # 重新生成剧本（带变体参数）
        # 这里简化处理，实际应该调用 script_generator 并传入参数
        print(f"      变体提示: {variant_prompt}")

        # TODO: 实际调用 LLM 重新生成
        # 现在返回标记版本
        return f"{base_script}\n\n[实验版本: {params.get('name', 'unknown')}]"

    def _build_variant_prompt(self, params: Dict[str, Any]) -> str:
        """构建变体提示词"""
        prompts = []

        if params.get("conflict_timing") == "immediate":
            prompts.append("开头第一句话就要有强烈冲突")
        elif params.get("conflict_timing") == "early":
            prompts.append("前10秒内必须出现冲突")

        if params.get("reversal_count"):
            prompts.append(f"必须有{params['reversal_count']}个明显的剧情反转")

        if params.get("emotion_intensity") == "extreme":
            prompts.append("情绪表达要极端化，使用强烈的情绪词汇")

        if params.get("hook_style") == "shock":
            prompts.append("开头使用震惊式Hook（如：死亡、背叛、身份曝光）")
        elif params.get("hook_style") == "mystery":
            prompts.append("开头使用悬念式Hook（如：秘密、真相、隐藏）")

        return "；".join(prompts)


class StoryboardVariantGenerator:
    """分镜变体生成器"""

    def __init__(self, storyboard_manager):
        self.storyboard_manager = storyboard_manager

    async def generate(self, base_storyboard: Dict[str, Any], params: Dict[str, Any]) -> Dict[str, Any]:
        """
        根据参数生成分镜变体

        简化版：调整现有分镜的参数
        """
        import copy
        variant = copy.deepcopy(base_storyboard)

        shots = variant.get("film_storyboard", [])

        # 应用参数变化
        if params.get("shot_count_multiplier"):
            # TODO: 实际应该增加/减少镜头数量
            pass

        if params.get("closeup_ratio"):
            # 调整特写镜头比例
            self._adjust_closeup_ratio(shots, params["closeup_ratio"])

        if params.get("camera_motion"):
            # 调整运镜风格
            self._adjust_camera_motion(shots, params["camera_motion"])

        variant["experiment_params"] = params
        return variant

    def _adjust_closeup_ratio(self, shots: List[Dict], target_ratio: float):
        """调整特写比例"""
        closeup_types = ["close-up", "detail"]
        current_closeups = sum(1 for s in shots if s.get("shot_type") in closeup_types)
        target_count = int(len(shots) * target_ratio)

        # 简化处理：标记需要调整
        print(f"      调整特写比例: {current_closeups}/{len(shots)} -> {target_count}/{len(shots)}")

    def _adjust_camera_motion(self, shots: List[Dict], motion_style: str):
        """调整运镜风格"""
        motion_map = {
            "dynamic": ["tracking shot", "orbit shot", "whip pan"],
            "stable": ["slow push", "dolly in", "gimbal stabilized"]
        }

        motions = motion_map.get(motion_style, [])
        print(f"      调整运镜风格: {motion_style} ({len(motions)} 种运镜)")


class VideoVariantGenerator:
    """视频变体生成器"""

    def __init__(self, video_composer):
        self.video_composer = video_composer

    async def generate(self, base_video_path: str, params: Dict[str, Any]) -> str:
        """
        根据参数生成视频变体

        应用不同的后期处理参数
        """
        import os

        output_path = base_video_path.replace(".mp4", f"_{params.get('name', 'variant')}.mp4")

        # TODO: 实际应该调用 video_composer 应用参数
        # 现在简化处理
        print(f"      应用参数: {params}")
        print(f"      输出路径: {output_path}")

        # 复制原视频作为占位
        if os.path.exists(base_video_path):
            import shutil
            shutil.copy(base_video_path, output_path)

        return output_path
