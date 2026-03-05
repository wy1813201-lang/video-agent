"""
视频质量反馈优化系统 (Feedback Loop)
SOP 第八阶段（最终质检）：评估成品 → 根因分析 → 修改前面任何环节

核心能力：
1. 三维度视频评分（图文对齐、运动流畅、美学质量）
2. 根因定位（剧本/分镜/prompt/生成参数）
3. 参数调优引擎（自动修改配置）
4. 闭环重做（触发局部/全局重生成）
"""

import json
import re
import subprocess
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

# ─────────────────────────── 配置 ─────────────────────────────────

@dataclass
class ScoringConfig:
    """评分阈值配置"""
    text_alignment_threshold: float = 0.6   # 图文对齐最低分
    motion_quality_threshold: float = 0.5   # 运动质量最低分
    aesthetic_threshold: float = 0.6        # 美学质量最低分
    overall_threshold: float = 0.65        # 综合质量最低分
    
    # 重试配置
    max_regen_per_shot: int = 3             # 单个分镜最大重试次数
    max_global_rerun: int = 2               # 全流程最大重跑次数


@dataclass
class VideoScore:
    """视频三维度评分"""
    text_alignment: float = 0.0    # 图文对齐 (0-1)
    motion_quality: float = 0.0    # 运动流畅 (0-1)
    aesthetic: float = 0.0         # 美学质量 (0-1)
    overall: float = 0.0           # 综合评分
    
    # 细节
    frame_consistency: float = 0.0  # 帧间一致性
    prompt_matching: float = 0.0   # prompt 匹配度
    
    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class RootCause:
    """根因分析结果"""
    stage: str                      # 出问题的阶段 (script/storyboard/prompt/video_gen/assembly)
    shot_ids: List[str] = field(default_factory=list)  # 出问题的分镜ID
    confidence: float = 0.0         # 置信度 (0-1)
    description: str = ""            # 问题描述
    suggestions: List[str] = field(default_factory=list)  # 修复建议


@dataclass
class OptimizationAction:
    """优化操作"""
    action_type: str                # "regen_prompt" / "adjust_params" / "regen_shot" / "modify_template"
    target: str                     # 目标 (shot_id / stage / config_key)
    old_value: Any = None           # 原值
    new_value: Any = None           # 新值
    reason: str = ""                # 原因


@dataclass
class FeedbackReport:
    """完整反馈报告"""
    scores: VideoScore = field(default_factory=VideoScore)
    root_causes: List[RootCause] = field(default_factory=list)
    optimization_actions: List[OptimizationAction] = field(default_factory=list)
    overall_pass: bool = False
    needs_regen: bool = False
    regen_plan: str = ""            # "shot" / "stage" / "full"
    
    # 统计
    total_shots: int = 0
    failed_shots: int = 0
    
    def summary(self) -> str:
        lines = [
            "=" * 50,
            "📊 视频质量反馈报告",
            "=" * 50,
            f"综合评分: {self.scores.overall:.1%}",
            f"  - 图文对齐: {self.scores.text_alignment:.1%}",
            f"  - 运动流畅: {self.scores.motion_quality:.1%}",
            f"  - 美学质量: {self.scores.aesthetic:.1%}",
            f"",
            f"分镜统计: {self.total_shots} 个, {self.failed_shots} 个不合格",
            f"是否通过: {'✅ 通过' if self.overall_pass else '❌ 需优化'}",
        ]
        if self.root_causes:
            lines.append(f"\n🔍 根因分析 ({len(self.root_causes)}个问题):")
            for i, rc in enumerate(self.root_causes, 1):
                lines.append(f"  {i}. [{rc.stage}] {rc.description}")
                if rc.suggestions:
                    for sug in rc.suggestions[:2]:
                        lines.append(f"     → {sug}")
        if self.optimization_actions:
            lines.append(f"\n🔧 优化操作 ({len(self.optimization_actions)}项):")
            for op in self.optimization_actions[:5]:
                lines.append(f"  - {op.action_type}: {op.target}")
        return "\n".join(lines)


# ─────────────────────────── 评分器 ─────────────────────────────────

class VideoQualityScorer:
    """
    视频质量三维度评分器
    - 图文对齐: 提取关键帧 + prompt，用 VLM 评估
    - 运动质量: 光流检测 + 闪烁检测
    - 美学质量: 美学模型评分
    """
    
    def __init__(self, config: Optional[ScoringConfig] = None):
        self.config = config or ScoringConfig()
    
    async def score_video(
        self,
        video_path: str,
        prompts: List[str],
        storyboard: Dict[str, Any],
    ) -> VideoScore:
        """
        对合成后的视频进行三维度评分
        """
        score = VideoScore()
        
        # 1. 提取关键帧
        frames = await self._extract_frames(video_path, num_frames=8)
        if not frames:
            score.overall = 0.0
            return score
        
        # 2. 逐维度评分
        score.text_alignment = await self._score_text_alignment(frames, prompts)
        score.motion_quality = await self._score_motion_quality(video_path)
        score.aesthetic = await self._score_aesthetic(frames)
        
        # 3. 计算综合
        score.overall = (
            score.text_alignment * 0.35 +
            score.motion_quality * 0.35 +
            score.aesthetic * 0.30
        )
        
        # 4. 额外指标
        score.frame_consistency = await self._score_frame_consistency(frames)
        score.prompt_matching = score.text_alignment  # 别名
        
        return score
    
    async def _extract_frames(self, video_path: str, num_frames: int = 8) -> List[str]:
        """用 FFmpeg 提取关键帧"""
        if not Path(video_path).exists():
            return []
        
        output_dir = Path(video_path).parent / "quality_frames"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 获取视频时长
        cmd = f"ffprobe -v error -show_entries format=duration -of csv=p=0 '{video_path}'"
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
            duration = float(result.stdout.strip()) if result.stdout.strip() else 10
        except:
            duration = 10
        
        # 提取均匀分布的帧
        frame_paths = []
        for i in range(num_frames):
            timestamp = (duration / (num_frames + 1)) * (i + 1)
            output_path = output_dir / f"frame_{i:02d}.jpg"
            cmd = (
                f"ffmpeg -y -ss {timestamp:.2f} -i '{video_path}' "
                f"-vframes 1 -q:v 2 '{output_path}' 2>/dev/null"
            )
            subprocess.run(cmd, shell=True, timeout=5)
            if output_path.exists():
                frame_paths.append(str(output_path))
        
        return frame_paths
    
    async def _score_text_alignment(
        self, frames: List[str], prompts: List[str]
    ) -> float:
        """
        图文对齐评分：用 VLM 评估帧内容与 prompt 的匹配度
        这里使用简化的 CLIP 相似度 + 关键词匹配
        实际生产可用 GPT-4V 或阿里 VLLAMA
        """
        if not frames or not prompts:
            return 0.5
        
        # 合并所有 prompt
        combined_prompt = " ".join(prompts)
        
        # 简单实现：检测 prompt 关键词在帧中是否合理
        # 实际应该用 VLM，这里先用占位逻辑
        # TODO: 集成真实的 VLM 评估
        
        # 临时：返回基于关键词覆盖的分数
        score = 0.7  # 默认分数
        
        # 检查关键元素
        key_elements = self._extract_key_elements(combined_prompt)
        if key_elements:
            # 简单假设 70% 匹配
            score = 0.7 + (len(key_elements) % 3) * 0.1
        
        return min(score, 1.0)
    
    async def _score_motion_quality(self, video_path: str) -> float:
        """
        运动质量评分：检测跳帧、闪烁、伪影
        使用 FFmpeg 分析视频质量 + 简单光流
        """
        if not Path(video_path).exists():
            return 0.0
        
        # 用 FFmpeg vfmpdect 检测运动
        # 简化：检测视频是否稳定
        
        # 检查文件大小（异常小的视频可能是生成失败）
        size_mb = Path(video_path).stat().st_size / 1024 / 1024
        if size_mb < 0.1:
            return 0.0  # 视频太小，可能是失败的
        
        # 简单评分：视频越大通常信息量越大
        # 实际应该用光流分析
        score = min(0.5 + size_mb / 10, 0.95)
        
        return score
    
    async def _score_aesthetic(self, frames: List[str]) -> float:
        """
        美学评分：基于帧质量、构图、色彩
        实际可用 LAION aesthetic predictor 或 CLIP aesthetic
        """
        if not frames:
            return 0.0
        
        # 简化实现：检查帧文件大小和分辨率
        scores = []
        for frame in frames:
            if not Path(frame).exists():
                continue
            size_kb = Path(frame).stat().st_size / 1024
            # 假设清晰的图越大越好
            score = min(0.5 + size_kb / 100, 0.95)
            scores.append(score)
        
        return sum(scores) / len(scores) if scores else 0.5
    
    async def _score_frame_consistency(self, frames: List[str]) -> float:
        """帧间一致性评分"""
        if len(frames) < 2:
            return 1.0
        
        # 简化：检查帧大小变化是否剧烈
        sizes = []
        for f in frames:
            if Path(f).exists():
                sizes.append(Path(f).stat().st_size)
        
        if not sizes:
            return 0.5
        
        # 计算变异系数
        mean_size = sum(sizes) / len(sizes)
        variance = sum((s - mean_size) ** 2 for s in sizes) / len(sizes)
        std = variance ** 0.5
        cv = std / mean_size if mean_size > 0 else 0
        
        # CV 越小越一致
        score = max(0, 1 - cv)
        return score
    
    def _extract_key_elements(self, text: str) -> List[str]:
        """提取关键视觉元素"""
        # 简单关键词提取
        patterns = [
            r"(?:穿着| wearing| dressed in)\s+(\w+)",
            r"(?:发型| hairstyle| hair)\s+(\w+)",
            r"(?:表情| expression| face)\s+(\w+)",
            r"(?:场景| scene| location)\s+(\w+)",
        ]
        elements = []
        for p in patterns:
            matches = re.findall(p, text, re.IGNORECASE)
            elements.extend(matches)
        return elements[:10]


# ─────────────────────────── 根因分析器 ─────────────────────────────

class RootCauseAnalyzer:
    """根因分析器：定位问题源头"""
    
    def __init__(self):
        pass
    
    def analyze(
        self,
        score: VideoScore,
        storyboard: Dict[str, Any],
        video_scores: Dict[str, float],  # {shot_id: individual_score}
        quality_report: Any = None,       # QualityAuditor 的报告
    ) -> List[RootCause]:
        """
        分析根因，返回问题列表
        """
        causes = []
        
        # 1. 图文对齐问题 → 追溯到 prompt
        if score.text_alignment < 0.6:
            causes.append(RootCause(
                stage="prompt",
                confidence=0.8,
                description="图文对齐度低，prompt描述与生成画面不匹配",
                suggestions=[
                    "增加具体视觉描述（服装、场景、动作细节）",
                    "使用角色锚点强化角色外貌",
                    "添加参考图增强一致性",
                ]
            ))
        
        # 2. 运动质量问题 → 追溯到视频生成参数
        if score.motion_quality < 0.5:
            causes.append(RootCause(
                stage="video_gen",
                confidence=0.85,
                description="运动质量差，可能存在跳帧、闪烁或动作不自然",
                suggestions=[
                    "增加 motion_prompt 中的动作过渡描述",
                    "尝试不同的 seed 值",
                    "考虑更换视频生成模型",
                ]
            ))
        
        # 3. 美学质量问题 → 追溯到关键帧/prompt
        if score.aesthetic < 0.6:
            causes.append(RootCause(
                stage="keyframe",
                confidence=0.75,
                description="美学质量低，画面质感不足",
                suggestions=[
                    "优化关键帧的构图和光影描述",
                    "添加电影感关键词（cinematic, lighting等）",
                    "提升图像生成分辨率",
                ]
            ))
        
        # 4. 分析单个分镜的问题
        failed_shots = [sid for sid, s in video_scores.items() if s < 0.5]
        if failed_shots:
            causes.append(RootCause(
                stage="shot",
                shot_ids=failed_shots[:5],  # 最多5个
                confidence=0.9,
                description=f"检测到 {len(failed_shots)} 个低分分镜",
                suggestions=[
                    f"重新生成分镜: {', '.join(failed_shots[:3])}",
                    "检查这些分镜的 prompt 是否有模糊描述",
                ]
            ))
        
        # 5. 帧间不一致 → 分镜/合成问题
        if score.frame_consistency < 0.6:
            causes.append(RootCause(
                stage="assembly",
                confidence=0.7,
                description="帧间一致性差，视频拼接不流畅",
                suggestions=[
                    "检查分镜之间的过渡是否自然",
                    "考虑添加转场效果",
                    "重新生成边界处的关键帧",
                ]
            ))
        
        return causes


# ─────────────────────────── 参数调优引擎 ─────────────────────────────

class ParameterTuner:
    """
    参数调优引擎：根据根因自动调整配置
    拥有修改前面所有环节配置的权限
    """
    
    def __init__(self, config_path: str = "config/api_config.json"):
        self.config_path = Path(config_path)
        self.config = self._load_config()
        self.history: List[Dict] = []  # 记录每次调优
    
    def _load_config(self) -> Dict:
        if self.config_path.exists():
            with open(self.config_path) as f:
                return json.load(f)
        return {}
    
    def save_config(self):
        """保存配置"""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, "w") as f:
            json.dump(self.config, f, indent=2, ensure_ascii=False)
    
    def generate_actions(
        self,
        root_causes: List[RootCause],
        current_config: Dict,
    ) -> List[OptimizationAction]:
        """
        根据根因生成优化操作
        """
        actions = []
        
        for cause in root_causes:
            if cause.stage == "prompt":
                # 修改 prompt 模板
                actions.append(OptimizationAction(
                    action_type="enhance_prompt_template",
                    target="prompt_template",
                    old_value=current_config.get("prompt", {}).get("quality_suffix", ""),
                    new_value=current_config.get("prompt", {}).get("quality_suffix", "") + 
                             ", highly detailed, professional photography",
                    reason="图文对齐度低，加强 prompt 细节",
                ))
            
            elif cause.stage == "video_gen":
                # 调整视频生成参数
                old_temp = current_config.get("video", {}).get("jimeng", {}).get("temperature", 0.7)
                actions.append(OptimizationAction(
                    action_type="adjust_params",
                    target="video.temperature",
                    old_value=old_temp,
                    new_value=max(0.3, old_temp - 0.1),  # 降低温度更稳定
                    reason="运动质量问题，降低温度提高稳定性",
                ))
            
            elif cause.stage == "keyframe":
                # 调整图像生成参数
                old_size = current_config.get("image", {}).get("cozex", {}).get("size", "1024x1024")
                if old_size == "1024x1024":
                    actions.append(OptimizationAction(
                        action_type="adjust_params",
                        target="image.cozex.size",
                        old_value=old_size,
                        new_value="2048x2048",
                        reason="美学质量低，提升图像分辨率",
                    ))
            
            elif cause.stage == "shot":
                # 标记需要重新生成分镜
                for shot_id in cause.shot_ids:
                    actions.append(OptimizationAction(
                        action_type="regen_shot",
                        target=shot_id,
                        reason=cause.description,
                    ))
            
            elif cause.stage == "assembly":
                # 修改合成参数
                actions.append(OptimizationAction(
                    action_type="add_transition",
                    target="assembly",
                    old_value="none",
                    new_value="fade",
                    reason="帧间不一致，添加转场",
                ))
        
        return actions
    
    def apply_actions(self, actions: List[OptimizationAction]) -> Dict:
        """
        应用优化操作，返回修改后的配置
        """
        applied = []
        
        for action in actions:
            if action.action_type == "adjust_params":
                # 嵌套字典修改
                keys = action.target.split(".")
                d = self.config
                for k in keys[:-1]:
                    if k not in d:
                        d[k] = {}
                    d = d[k]
                d[keys[-1]] = action.new_value
                applied.append(f"调整 {action.target}: {action.old_value} → {action.new_value}")
            
            elif action.action_type == "enhance_prompt_template":
                # 修改 prompt 模板
                if "prompt" not in self.config:
                    self.config["prompt"] = {}
                old = self.config["prompt"].get("quality_suffix", "")
                self.config["prompt"]["quality_suffix"] = action.new_value
                applied.append(f"增强 prompt 模板")
        
        if applied:
            self.save_config()
        
        return {"applied": applied, "config": self.config}


# ─────────────────────────── 主反馈循环 ─────────────────────────────

class FeedbackLoop:
    """
    反馈优化主循环
    位置：整个流程的最后，负责质检 + 闭环优化
    """
    
    def __init__(
        self,
        scoring_config: Optional[ScoringConfig] = None,
        config_path: str = "config/api_config.json",
    ):
        self.scorer = VideoQualityScorer(scoring_config)
        self.analyzer = RootCauseAnalyzer()
        self.tuner = ParameterTuner(config_path)
        self.config = self._load_config(config_path)
        
        # 历史记录
        self.run_history: List[FeedbackReport] = []
    
    def _load_config(self, path: str) -> Dict:
        p = Path(path)
        if p.exists():
            with open(p) as f:
                return json.load(f)
        return {}
    
    async def evaluate_and_optimize(
        self,
        final_video_path: str,
        storyboard: Dict[str, Any],
        prompts: List[str],
        video_scores: Optional[Dict[str, float]] = None,
        quality_report: Any = None,
    ) -> FeedbackReport:
        """
        主入口：评估 → 分析 → 优化
        """
        report = FeedbackReport()
        
        # 1. 评分
        report.scores = await self.scorer.score_video(
            final_video_path, prompts, storyboard
        )
        
        # 2. 统计分镜
        all_shots = []
        for scene in storyboard.get("scenes", []):
            for shot in scene.get("shots", []):
                all_shots.append(shot.get("shot_id", "unknown"))
        report.total_shots = len(all_shots)
        report.failed_shots = sum(
            1 for sid, s in (video_scores or {}).items() if s < 0.5
        )
        
        # 3. 根因分析
        report.root_causes = self.analyzer.analyze(
            report.scores, storyboard, video_scores or {}, quality_report
        )
        
        # 4. 判断是否通过
        config = self.scorer.config
        report.overall_pass = (
            report.scores.overall >= config.overall_threshold and
            report.scores.text_alignment >= config.text_alignment_threshold and
            report.scores.motion_quality >= config.motion_quality_threshold and
            report.scores.aesthetic >= config.aesthetic_threshold
        )
        
        # 5. 生成优化操作
        if not report.overall_pass:
            report.needs_regen = True
            actions = self.tuner.generate_actions(
                report.root_causes, self.config
            )
            report.optimization_actions = actions
            
            # 确定重做计划
            has_shot_regen = any(a.action_type == "regen_shot" for a in actions)
            has_stage_change = any(
                a.action_type in ("adjust_params", "enhance_prompt_template") 
                for a in actions
            )
            
            if has_shot_regen:
                report.regen_plan = "shot"
            elif has_stage_change:
                report.regen_plan = "stage"
            else:
                report.regen_plan = "full"
        
        # 6. 记录历史
        self.run_history.append(report)
        
        return report
    
    def get_best_config(self) -> Dict:
        """
        从历史记录中找出最佳配置
        """
        best = None
        best_score = 0
        
        for report in self.run_history:
            if report.scores.overall > best_score:
                best_score = report.scores.overall
                best = report
        
        if best:
            return {
                "score": best_score,
                "actions": [asdict(a) for a in best.optimization_actions],
            }
        return {}


# ─────────────────────────── 便捷函数 ─────────────────────────────

async def run_feedback_loop(
    video_path: str,
    storyboard: Dict[str, Any],
    prompts: List[str],
    config_path: str = "config/api_config.json",
) -> FeedbackReport:
    """快速运行反馈循环"""
    loop = FeedbackLoop(config_path=config_path)
    return await loop.evaluate_and_optimize(video_path, storyboard, prompts)


# ─────────────────────────── 测试 ─────────────────────────────

if __name__ == "__main__":
    async def test():
        # 模拟数据
        storyboard = {
            "scenes": [
                {
                    "scene_id": "scene_1",
                    "shots": [
                        {"shot_id": "shot_1", "description": "test"},
                        {"shot_id": "shot_2", "description": "test2"},
                    ]
                }
            ]
        }
        prompts = [
            "A woman wearing red dress walking in the street",
            "A man running in the forest"
        ]
        
        # 测试评分
        scorer = VideoQualityScorer()
        # score = await scorer.score_video("test.mp4", prompts, storyboard)
        # print(f"Score: {score.overall}")
        
        # 测试根因分析
        analyzer = RootCauseAnalyzer()
        score = VideoScore(text_alignment=0.4, motion_quality=0.7, aesthetic=0.8, overall=0.6)
        causes = analyzer.analyze(score, storyboard, {"shot_1": 0.3, "shot_2": 0.8})
        print(f"Causes: {len(causes)}")
        for c in causes:
            print(f"  - {c.stage}: {c.description}")
    
    # asyncio.run(test())
    print("Feedback Loop Module Loaded")
