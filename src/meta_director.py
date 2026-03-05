#!/usr/bin/env python3
"""
Meta Director - 老板 Agent（简化版 MVP）

职责：
1. 审核剧本/分镜/视频质量
2. 决策：继续/退回/生成实验版本
3. 管理实验版本
4. 记录决策数据（为未来AI学习积累数据）

简化版特性：
- 使用规则based审核（不依赖LLM）
- 支持生成多个实验版本
- 人工选择最佳版本
- 记录选择原因
"""

import json
import os
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime
from enum import Enum


class DecisionType(str, Enum):
    """决策类型"""
    APPROVE = "approve"           # 通过，继续下一步
    REJECT = "reject"             # 退回重做
    EXPERIMENT = "experiment"     # 生成实验版本
    MANUAL_REVIEW = "manual"      # 需要人工审核


class ContentType(str, Enum):
    """内容类型"""
    SCRIPT = "script"
    STORYBOARD = "storyboard"
    VIDEO = "video"


@dataclass
class QualityScore:
    """质量评分"""
    overall: float  # 总分 0-10
    hook_strength: float = 0.0      # Hook吸引力
    plot_structure: float = 0.0     # 剧情结构
    emotion_rhythm: float = 0.0     # 情绪节奏
    shot_logic: float = 0.0         # 镜头逻辑
    visual_quality: float = 0.0     # 画面质量
    issues: List[str] = field(default_factory=list)  # 问题列表
    suggestions: List[str] = field(default_factory=list)  # 改进建议


@dataclass
class Decision:
    """决策结果"""
    decision_type: DecisionType
    score: QualityScore
    reason: str
    timestamp: str
    content_type: ContentType
    experiment_params: Optional[Dict[str, Any]] = None


@dataclass
class ExperimentVersion:
    """实验版本"""
    version_id: str
    params: Dict[str, Any]  # 变化的参数
    content: Any
    score: Optional[QualityScore] = None
    selected: bool = False
    selection_reason: str = ""


@dataclass
class ProductionRecord:
    """生产记录（用于数据积累）"""
    record_id: str
    topic: str
    episode_num: int
    decisions: List[Decision] = field(default_factory=list)
    experiments: List[ExperimentVersion] = field(default_factory=list)
    final_version_id: Optional[str] = None
    platform_data: Dict[str, Any] = field(default_factory=dict)  # 平台表现数据
    created_at: str = ""


class MetaDirector:
    """
    Meta Director - 老板 Agent

    简化版实现：
    - 规则based审核
    - 支持实验版本
    - 记录决策数据
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.min_score = self.config.get("min_score", 7.0)  # 最低通过分数
        self.enable_experiments = self.config.get("enable_experiments", True)
        self.experiment_count = self.config.get("experiment_count", 2)  # 实验版本数
        self.records_dir = self.config.get("records_dir", "data/production_records")
        self.current_record: Optional[ProductionRecord] = None

        os.makedirs(self.records_dir, exist_ok=True)

    def start_production(self, topic: str, episode_num: int) -> str:
        """开始新的生产流程"""
        record_id = f"{topic}_ep{episode_num:02d}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.current_record = ProductionRecord(
            record_id=record_id,
            topic=topic,
            episode_num=episode_num,
            created_at=datetime.now().isoformat()
        )
        return record_id

    # ================================================================
    # 审核系统
    # ================================================================

    def review_script(self, script: str) -> Decision:
        """
        审核剧本

        评分维度：
        - Hook吸引力：开头3秒是否有冲突
        - 剧情结构：是否有明确的冲突和反转
        - 情绪节奏：情绪变化是否明显
        """
        score = QualityScore(overall=0.0)

        # 1. Hook吸引力检测
        hook_score = self._check_hook_strength(script)
        score.hook_strength = hook_score

        # 2. 剧情结构检测
        structure_score = self._check_plot_structure(script)
        score.plot_structure = structure_score

        # 3. 情绪节奏检测
        emotion_score = self._check_emotion_rhythm(script)
        score.emotion_rhythm = emotion_score

        # 计算总分
        score.overall = (hook_score + structure_score + emotion_score) / 3

        # 决策（传入完整 score 对象以检查所有维度）
        decision_type = self._make_decision(score.overall, score)

        decision = Decision(
            decision_type=decision_type,
            score=score,
            reason=self._generate_reason(score),
            timestamp=datetime.now().isoformat(),
            content_type=ContentType.SCRIPT
        )

        if self.current_record:
            self.current_record.decisions.append(decision)

        return decision

    def review_storyboard(self, storyboard_data: Dict[str, Any]) -> Decision:
        """
        审核分镜

        评分维度：
        - 镜头逻辑：镜头类型是否合理
        - 镜头数量：是否符合短剧节奏
        - 角色一致性：角色描述是否一致
        """
        score = QualityScore(overall=0.0)

        shots = storyboard_data.get("film_storyboard", [])

        # 1. 镜头逻辑检测
        logic_score = self._check_shot_logic(shots)
        score.shot_logic = logic_score

        # 2. 镜头数量检测
        count_score = self._check_shot_count(shots)

        # 3. 角色一致性检测
        consistency_score = self._check_character_consistency(storyboard_data)

        score.overall = (logic_score + count_score + consistency_score) / 3

        decision_type = self._make_decision(score.overall, score)

        decision = Decision(
            decision_type=decision_type,
            score=score,
            reason=self._generate_reason(score),
            timestamp=datetime.now().isoformat(),
            content_type=ContentType.STORYBOARD
        )

        if self.current_record:
            self.current_record.decisions.append(decision)

        return decision

    def review_video(self, video_path: str, quality_score: float) -> Decision:
        """
        审核视频

        评分维度：
        - 视觉质量：技术质量评分
        - 时长：是否符合要求
        """
        score = QualityScore(overall=0.0)
        score.visual_quality = quality_score * 10  # 转换为0-10分

        # 检查视频时长
        duration_score = self._check_video_duration(video_path)

        score.overall = (score.visual_quality + duration_score) / 2

        decision_type = self._make_decision(score.overall, score)

        decision = Decision(
            decision_type=decision_type,
            score=score,
            reason=self._generate_reason(score),
            timestamp=datetime.now().isoformat(),
            content_type=ContentType.VIDEO
        )

        if self.current_record:
            self.current_record.decisions.append(decision)

        return decision

    # ================================================================
    # 实验系统
    # ================================================================

    def should_experiment(self, score: QualityScore) -> bool:
        """判断是否需要生成实验版本"""
        if not self.enable_experiments:
            return False

        # 如果分数在及格线附近，生成实验版本
        if self.min_score - 1.0 <= score.overall <= self.min_score + 1.0:
            return True

        return False

    def generate_experiment_params(self, content_type: ContentType) -> List[Dict[str, Any]]:
        """
        生成实验参数

        根据内容类型生成不同的变化参数
        """
        params_list = []

        if content_type == ContentType.SCRIPT:
            # 剧本实验参数
            params_list = [
                {"conflict_timing": "early", "reversal_count": 2, "emotion_intensity": "high"},
                {"conflict_timing": "immediate", "reversal_count": 3, "emotion_intensity": "extreme"},
            ]

        elif content_type == ContentType.STORYBOARD:
            # 分镜实验参数
            params_list = [
                {"shot_count": "more", "closeup_ratio": 0.4, "camera_motion": "dynamic"},
                {"shot_count": "less", "closeup_ratio": 0.6, "camera_motion": "stable"},
            ]

        elif content_type == ContentType.VIDEO:
            # 视频实验参数
            params_list = [
                {"transition_style": "fast", "color_grade": "warm", "music_intensity": "high"},
                {"transition_style": "smooth", "color_grade": "cinematic", "music_intensity": "medium"},
            ]

        return params_list[:self.experiment_count]

    def record_experiment(self, version_id: str, params: Dict[str, Any], content: Any):
        """记录实验版本"""
        if not self.current_record:
            return

        experiment = ExperimentVersion(
            version_id=version_id,
            params=params,
            content=content
        )
        self.current_record.experiments.append(experiment)

    def select_best_version(self, version_id: str, reason: str):
        """选择最佳版本（人工选择）"""
        if not self.current_record:
            return

        for exp in self.current_record.experiments:
            if exp.version_id == version_id:
                exp.selected = True
                exp.selection_reason = reason
                self.current_record.final_version_id = version_id
                break

    # ================================================================
    # 数据记录
    # ================================================================

    def save_record(self):
        """保存生产记录"""
        if not self.current_record:
            return

        path = os.path.join(self.records_dir, f"{self.current_record.record_id}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(asdict(self.current_record), f, ensure_ascii=False, indent=2)

        print(f"[MetaDirector] 生产记录已保存: {path}")

    def update_platform_data(self, data: Dict[str, Any]):
        """更新平台表现数据（手动录入或API获取）"""
        if not self.current_record:
            return

        self.current_record.platform_data.update(data)
        self.save_record()

    # ================================================================
    # 内部辅助方法
    # ================================================================

    def _check_hook_strength(self, script: str) -> float:
        """检测Hook吸引力（0-10分）"""
        score = 5.0  # 基础分

        # 检测开头是否有强冲突关键词
        hook_keywords = [
            "重生", "复仇", "震惊", "发现", "背叛", "秘密",
            "死亡", "醒来", "穿越", "系统", "觉醒", "身份"
        ]

        first_100_chars = script[:100]
        for keyword in hook_keywords:
            if keyword in first_100_chars:
                score += 1.0

        # 检测是否有对话（开头有对话更吸引人）
        if ":" in first_100_chars or "：" in first_100_chars:
            score += 1.0

        return min(10.0, score)

    def _check_plot_structure(self, script: str) -> float:
        """检测剧情结构（0-10分）"""
        score = 5.0

        # 检测场景数量
        scene_count = script.count("场景")
        if 3 <= scene_count <= 5:
            score += 2.0
        elif scene_count > 5:
            score += 1.0

        # 检测冲突关键词
        conflict_keywords = ["冲突", "对抗", "争吵", "打", "骂", "揭穿", "曝光"]
        conflict_count = sum(1 for kw in conflict_keywords if kw in script)
        score += min(2.0, conflict_count * 0.5)

        # 检测反转关键词
        reversal_keywords = ["原来", "竟然", "没想到", "真相", "其实", "突然"]
        reversal_count = sum(1 for kw in reversal_keywords if kw in script)
        score += min(1.0, reversal_count * 0.3)

        return min(10.0, score)

    def _check_emotion_rhythm(self, script: str) -> float:
        """检测情绪节奏（0-10分）"""
        score = 5.0

        # 检测情绪关键词
        emotion_keywords = {
            "愤怒": ["愤怒", "生气", "暴怒", "怒"],
            "悲伤": ["悲伤", "哭", "泪", "痛苦"],
            "惊讶": ["震惊", "惊讶", "不敢相信", "天啊"],
            "喜悦": ["开心", "高兴", "笑", "幸福"],
        }

        emotion_types = 0
        for emotion_type, keywords in emotion_keywords.items():
            if any(kw in script for kw in keywords):
                emotion_types += 1

        score += emotion_types * 1.0

        return min(10.0, score)

    def _check_shot_logic(self, shots: List[Dict[str, Any]]) -> float:
        """检测镜头逻辑（0-10分）"""
        if not shots:
            return 0.0

        score = 5.0

        # 检测是否有establishing shot（建立镜头）
        has_establishing = any(s.get("shot_type") == "establishing" for s in shots)
        if has_establishing:
            score += 2.0

        # 检测镜头类型多样性
        shot_types = set(s.get("shot_type", "") for s in shots)
        score += min(3.0, len(shot_types) * 0.5)

        return min(10.0, score)

    def _check_shot_count(self, shots: List[Dict[str, Any]]) -> float:
        """检测镜头数量（0-10分）"""
        count = len(shots)

        # 短剧理想镜头数：8-15个
        if 8 <= count <= 15:
            return 10.0
        elif 5 <= count < 8:
            return 7.0
        elif 15 < count <= 20:
            return 7.0
        else:
            return 5.0

    def _check_character_consistency(self, storyboard_data: Dict[str, Any]) -> float:
        """检测角色一致性（0-10分）"""
        characters = storyboard_data.get("characters", {})

        if not characters:
            return 5.0

        score = 5.0

        # 检测角色是否有完整描述
        for char_data in characters.values():
            if isinstance(char_data, dict):
                if char_data.get("face_identity"):
                    score += 1.0
                if char_data.get("clothing_style"):
                    score += 1.0

        return min(10.0, score)

    def _check_video_duration(self, video_path: str) -> float:
        """检测视频时长（0-10分）"""
        try:
            import subprocess
            cmd = [
                "ffprobe", "-v", "quiet", "-print_format", "json",
                "-show_format", video_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            data = json.loads(result.stdout or "{}")
            duration = float(data.get("format", {}).get("duration", 0) or 0)

            # 理想时长：50-70秒
            if 50 <= duration <= 70:
                return 10.0
            elif 40 <= duration < 50 or 70 < duration <= 80:
                return 7.0
            else:
                return 5.0
        except Exception:
            return 5.0

    def _make_decision(self, overall_score: float, score: QualityScore = None) -> DecisionType:
        """
        根据分数做决策

        新规则：所有维度都必须达到 8.5 才直接通过
        否则进入人工评选（实验模式）
        """
        # 检查所有维度是否都达到 8.5
        if score:
            all_dimensions = [
                score.hook_strength,
                score.plot_structure,
                score.emotion_rhythm,
                score.shot_logic,
                score.visual_quality
            ]
            # 过滤掉 0 分的维度（未评分的维度）
            valid_dimensions = [d for d in all_dimensions if d > 0]

            if valid_dimensions and all(d >= 8.5 for d in valid_dimensions):
                return DecisionType.APPROVE
            else:
                # 任何维度低于 8.5，进入人工评选
                return DecisionType.EXPERIMENT if self.enable_experiments else DecisionType.REJECT

        # 兜底逻辑（如果没有传入 score）
        if overall_score >= 8.5:
            return DecisionType.APPROVE
        else:
            return DecisionType.EXPERIMENT if self.enable_experiments else DecisionType.REJECT

    def _generate_reason(self, score: QualityScore) -> str:
        """生成决策理由"""
        reasons = []

        if score.hook_strength > 0 and score.hook_strength < 8.5:
            reasons.append(f"Hook吸引力未达标({score.hook_strength:.1f}/10，需≥8.5)")
        if score.plot_structure > 0 and score.plot_structure < 8.5:
            reasons.append(f"剧情结构未达标({score.plot_structure:.1f}/10，需≥8.5)")
        if score.emotion_rhythm > 0 and score.emotion_rhythm < 8.5:
            reasons.append(f"情绪节奏未达标({score.emotion_rhythm:.1f}/10，需≥8.5)")
        if score.shot_logic > 0 and score.shot_logic < 8.5:
            reasons.append(f"镜头逻辑未达标({score.shot_logic:.1f}/10，需≥8.5)")
        if score.visual_quality > 0 and score.visual_quality < 8.5:
            reasons.append(f"视觉质量未达标({score.visual_quality:.1f}/10，需≥8.5)")

        if not reasons:
            return f"所有维度均达到8.5标准，总分{score.overall:.1f}/10"

        return "；".join(reasons)
