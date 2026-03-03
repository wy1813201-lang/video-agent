"""
质量审核系统 (Quality Auditor)
SOP 第七阶段：按工业标准验收每个阶段输出

审核标准（来自 SOP）：
- 人物一致性 ≥ 90%（角色外貌锚点对比）
- 服装不变形
- 发型不漂移
- 角色五官比例不变化
- 光影统一
- 镜头运动逻辑合理
- 剧情节奏连续
"""

import json
import re
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .character_master import CharacterMaster, VAGUE_TERMS_BLACKLIST

# ─────────────────────────── SOP 阈值 ────────────────────────────────

SOP_THRESHOLDS = {
    "character_consistency": 0.90,   # ≥ 90%
    "prompt_quality_min_length": 80, # prompt 最小字符数
    "max_vague_terms_allowed": 0,    # 容忍的模糊词数量（0 = 零容忍）
    "min_shots_per_scene": 1,
    "max_actions_per_shot": 1,       # 每个镜头最多 1 个主要动作
}

# 镜头运动合法值
VALID_CAMERA_MOTIONS = {
    "push", "push-in", "pull", "pull-back", "pan", "tilt",
    "orbit", "crane", "handheld", "static", "fixed",
    "dolly", "gimbal", "slow motion", "stabilized"
}

# 非法的、会破坏连续性的环境突变关键词
CONTINUITY_BREAK_KEYWORDS = [
    "suddenly changes", "completely different location",
    "different time of day", "background swap", "environment change",
    "突然变换", "完全不同的背景", "场景突变",
]

# ─────────────────────────── 数据类 ─────────────────────────────────


@dataclass
class ShotAuditResult:
    """单个分镜的审核结果"""
    shot_id: str
    character_consistency_score: float = 0.0
    outfit_stable: bool = True
    hair_drift: bool = False          # True = 发型发生漂移（不合格）
    face_ratio_stable: bool = True
    lighting_consistent: bool = True
    camera_motion_logical: bool = True
    vague_terms_found: List[str] = field(default_factory=list)
    prompt_length_ok: bool = True
    issues: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return (
            self.character_consistency_score >= SOP_THRESHOLDS["character_consistency"]
            and self.outfit_stable
            and not self.hair_drift
            and self.face_ratio_stable
            and self.lighting_consistent
            and self.camera_motion_logical
            and len(self.vague_terms_found) <= SOP_THRESHOLDS["max_vague_terms_allowed"]
            and self.prompt_length_ok
        )


@dataclass
class AuditReport:
    """完整的审核报告"""
    episode: str = ""
    total_shots: int = 0
    passed_shots: int = 0
    failed_shots: int = 0

    # 聚合分数
    avg_character_consistency: float = 0.0
    lighting_consistency_rate: float = 0.0
    story_continuity: bool = True
    overall_pass: bool = False

    shot_results: List[ShotAuditResult] = field(default_factory=list)
    global_issues: List[str] = field(default_factory=list)
    global_suggestions: List[str] = field(default_factory=list)

    def summary_text(self) -> str:
        """生成人类可读的审核摘要"""
        lines = [
            f"=== 质量审核报告 [{self.episode}] ===",
            f"总分镜数: {self.total_shots}",
            f"通过: {self.passed_shots} | 不通过: {self.failed_shots}",
            f"人物一致性平均分: {self.avg_character_consistency:.1%}",
            f"光影一致性: {self.lighting_consistency_rate:.1%}",
            f"整体结论: {'✅ 通过' if self.overall_pass else '❌ 不通过'}",
        ]
        if self.global_issues:
            lines.append("\n[全局问题]")
            for issue in self.global_issues:
                lines.append(f"  ⚠ {issue}")
        if self.global_suggestions:
            lines.append("\n[改进建议]")
            for sug in self.global_suggestions:
                lines.append(f"  → {sug}")
        # 列出不通过的分镜
        failed = [r for r in self.shot_results if not r.passed]
        if failed:
            lines.append(f"\n[不通过分镜 ({len(failed)}个)]")
            for r in failed:
                lines.append(f"  分镜 {r.shot_id}: {'; '.join(r.issues)}")
        return "\n".join(lines)


# ─────────────────────────── 审核器 ─────────────────────────────────


class QualityAuditor:
    """
    SOP 质量审核器
    基于 prompt 文本分析 + 元数据比对进行规则驱动审核
    （若将来集成视觉模型，可在 _score_character_consistency_visual 中扩展）
    """

    def __init__(self, thresholds: Optional[Dict[str, Any]] = None):
        self.thresholds = {**SOP_THRESHOLDS, **(thresholds or {})}

    # ─── 主入口 ─────────────────────────────────────────────────────

    def audit_storyboard(
        self,
        storyboard: Dict[str, Any],
        character_masters: Optional[List[CharacterMaster]] = None,
        episode: str = "unknown",
    ) -> AuditReport:
        """
        对整个分镜 JSON 进行全面审核。

        Args:
            storyboard: film_director_agent 输出的 FILM_STORYBOARD dict
            character_masters: 本集出场的角色母版列表
            episode: 集数标识

        Returns:
            AuditReport
        """
        report = AuditReport(episode=episode)
        shot_results = []

        # 全局光影基准（取第一个角色母版的 lighting_anchor）
        global_lighting_anchor = ""
        if character_masters:
            global_lighting_anchor = character_masters[0].lighting_anchor

        # 逐场景 → 逐分镜审核
        scenes = storyboard.get("scenes", [])
        for scene in scenes:
            shots = scene.get("shots", [])
            if len(shots) < self.thresholds["min_shots_per_scene"]:
                report.global_issues.append(
                    f"场景 {scene.get('scene_id','?')} 分镜数量不足（{len(shots)}个）"
                )

            for shot in shots:
                result = self._audit_shot(shot, character_masters, global_lighting_anchor)
                shot_results.append(result)

        # 叙事连续性检查
        report.story_continuity = self.audit_story_continuity(storyboard)
        if not report.story_continuity:
            report.global_issues.append("检测到叙事连续性中断（场景突变或环境不一致）")

        # 聚合统计
        report.shot_results = shot_results
        report.total_shots = len(shot_results)
        report.passed_shots = sum(1 for r in shot_results if r.passed)
        report.failed_shots = report.total_shots - report.passed_shots

        if shot_results:
            report.avg_character_consistency = sum(
                r.character_consistency_score for r in shot_results
            ) / len(shot_results)
            report.lighting_consistency_rate = sum(
                1 for r in shot_results if r.lighting_consistent
            ) / len(shot_results)

        report.overall_pass = (
            report.passed_shots == report.total_shots
            and report.story_continuity
            and report.avg_character_consistency >= self.thresholds["character_consistency"]
        )

        # 全局建议
        if report.avg_character_consistency < self.thresholds["character_consistency"]:
            report.global_suggestions.append(
                f"人物一致性 {report.avg_character_consistency:.1%} 低于 SOP 要求 "
                f"{self.thresholds['character_consistency']:.0%}，"
                "建议在 prompt 中加强角色外貌锚点描述或启用 IP-Adapter"
            )
        if report.failed_shots > 0:
            report.global_suggestions.append(
                f"共 {report.failed_shots} 个分镜未通过，建议优先修复含模糊描述词的 prompt"
            )

        return report

    # ─── 分镜级审核 ─────────────────────────────────────────────────

    def _audit_shot(
        self,
        shot: Dict[str, Any],
        character_masters: Optional[List[CharacterMaster]],
        global_lighting_anchor: str,
    ) -> ShotAuditResult:
        shot_id = shot.get("shot_id", "unknown")
        result = ShotAuditResult(shot_id=shot_id)

        # 取 prompt 文本（keyframe + video prompts）
        prompts = []
        for key in ["keyframe_image_prompt", "video_prompt", "prompt", "motion_prompt", "t2v_prompt"]:
            if p := shot.get(key, ""):
                prompts.append(p)
        combined_prompt = " ".join(prompts)

        # 1. 角色一致性（文本锚点比对）
        result.character_consistency_score = self.audit_character_consistency(
            combined_prompt, character_masters
        )
        if result.character_consistency_score < self.thresholds["character_consistency"]:
            result.issues.append(
                f"人物一致性 {result.character_consistency_score:.1%} 低于要求 "
                f"{self.thresholds['character_consistency']:.0%}"
            )
            result.suggestions.append("在 prompt 中添加角色母版 to_anchor_fragment() 输出")

        # 2. 服装一致性（检测服装关键词是否与母版匹配）
        result.outfit_stable, outfit_issue = self._check_outfit_stability(
            combined_prompt, character_masters
        )
        if not result.outfit_stable:
            result.issues.append(outfit_issue)

        # 3. 发型漂移检测
        result.hair_drift, hair_issue = self._check_hair_drift(
            combined_prompt, character_masters
        )
        if result.hair_drift:
            result.issues.append(hair_issue)

        # 4. 光影一致性
        result.lighting_consistent = self.audit_lighting_consistency_shot(
            combined_prompt, global_lighting_anchor
        )
        if not result.lighting_consistent:
            result.issues.append("光影参数与全局基准不一致")
            result.suggestions.append(f"使用统一光影基准: '{global_lighting_anchor}'")

        # 5. 镜头运动合理性
        result.camera_motion_logical = self.audit_camera_motion(shot)
        if not result.camera_motion_logical:
            result.issues.append("镜头运动描述包含多个相互矛盾的方向，逻辑混乱")

        # 6. prompt 质量
        vague_found = self.audit_prompt_quality_terms(combined_prompt)
        result.vague_terms_found = vague_found
        if vague_found:
            result.issues.append(f"含模糊描述词: {vague_found}")
            result.suggestions.append("替换为结构化描述（发色、服装材质、面部比例等）")

        result.prompt_length_ok = len(combined_prompt) >= self.thresholds["prompt_quality_min_length"]
        if not result.prompt_length_ok:
            result.issues.append(f"prompt 过短（{len(combined_prompt)}字符 < 要求{self.thresholds['prompt_quality_min_length']}字符）")

        return result

    # ─── 分类审核方法 ───────────────────────────────────────────────

    def audit_character_consistency(
        self,
        prompt: str,
        character_masters: Optional[List[CharacterMaster]],
    ) -> float:
        """
        文本层面的人物一致性评分（0~1）。
        通过计算角色锚点关键词在 prompt 中的覆盖率来估算一致性。
        """
        if not character_masters or not prompt:
            return 0.0

        total_score = 0.0
        for master in character_masters:
            anchor = master.to_anchor_fragment()
            # 将锚点拆成关键词
            anchor_keywords = [
                kw.strip().lower()
                for kw in re.split(r"[,，]", anchor)
                if len(kw.strip()) > 3
            ]
            if not anchor_keywords:
                continue
            prompt_lower = prompt.lower()
            matched = sum(1 for kw in anchor_keywords if kw in prompt_lower)
            score = matched / len(anchor_keywords)
            total_score += score

        return total_score / len(character_masters)

    def audit_prompt_quality(self, prompts: List[str]) -> "AuditReport":
        """
        快捷方法：仅对 prompt 列表进行质量审核（不依赖分镜 JSON）。
        返回简化的 AuditReport。
        注: 此模式跳过角色一致性分数检查（prompt-only 无角色参考信息）。
        """
        report = AuditReport(episode="prompt_only_audit")
        report.total_shots = len(prompts)
        for i, prompt in enumerate(prompts):
            result = ShotAuditResult(shot_id=f"p_{i}")
            # 在 prompt-only 模式下，不评估角色一致性
            result.character_consistency_score = SOP_THRESHOLDS["character_consistency"]  # 视为满分
            vague = self.audit_prompt_quality_terms(prompt)
            result.vague_terms_found = vague
            result.prompt_length_ok = len(prompt) >= self.thresholds["prompt_quality_min_length"]
            if vague:
                result.issues.append(f"含模糊词: {vague}")
            if not result.prompt_length_ok:
                result.issues.append("prompt 过短")
            report.shot_results.append(result)

        report.passed_shots = sum(1 for r in report.shot_results if r.passed)
        report.failed_shots = report.total_shots - report.passed_shots
        report.overall_pass = report.failed_shots == 0
        return report

    def audit_prompt_quality_terms(self, prompt: str) -> List[str]:
        """返回 prompt 中所有模糊词列表"""
        prompt_lower = prompt.lower()
        return [term for term in VAGUE_TERMS_BLACKLIST if term.lower() in prompt_lower]

    def audit_lighting_consistency(self, storyboard: Dict[str, Any]) -> float:
        """
        检查整个分镜的光影参数一致性。
        返回一致性比率（0~1）。
        """
        all_prompts = []
        for scene in storyboard.get("scenes", []):
            for shot in scene.get("shots", []):
                for key in ["keyframe_image_prompt", "video_prompt", "prompt"]:
                    if p := shot.get(key, ""):
                        all_prompts.append(p)

        if not all_prompts:
            return 1.0

        # 简单实现：检查是否所有 prompt 都包含色温关键词
        temp_keywords = ["5600k", "5500k", "daylight", "warm", "cool", "3200k", "tungsten"]
        has_temp = [
            any(kw in p.lower() for kw in temp_keywords) for p in all_prompts
        ]
        return sum(has_temp) / len(has_temp)

    def audit_lighting_consistency_shot(
        self,
        prompt: str,
        global_anchor: str,
    ) -> bool:
        """
        检查单个分镜 prompt 的色温是否与全局基准一致。
        简化版：提取色温数值进行比对。
        """
        if not global_anchor or not prompt:
            return True
        global_temp = self._extract_color_temperature(global_anchor)
        shot_temp = self._extract_color_temperature(prompt)
        if shot_temp is None:
            return True  # 未指定色温，不强制报错
        if global_temp is None:
            return True
        return abs(global_temp - shot_temp) <= 500  # 允许 ±500K 浮动

    def audit_camera_motion(self, shot: Dict[str, Any]) -> bool:
        """
        检查镜头运动逻辑合理性：
        不得在单个分镜中同时出现相互矛盾的方向。
        """
        motion_text = ""
        for key in ["camera_motion", "motion_prompt", "video_prompt"]:
            motion_text += " " + shot.get(key, "")
        motion_lower = motion_text.lower()

        # 检测矛盾对
        contradiction_pairs = [
            ("push", "pull-back"),
            ("push-in", "pull"),
            ("pan left", "pan right"),
            ("tilt up", "tilt down"),
            ("zoom in", "zoom out"),
        ]
        for a, b in contradiction_pairs:
            if a in motion_lower and b in motion_lower:
                return False
        return True

    def audit_story_continuity(self, storyboard: Dict[str, Any]) -> bool:
        """
        检测叙事连续性：查找场景描述中的突变关键词。
        """
        for scene in storyboard.get("scenes", []):
            for shot in scene.get("shots", []):
                for key in ["description", "video_prompt", "prompt"]:
                    text = shot.get(key, "").lower()
                    for kw in CONTINUITY_BREAK_KEYWORDS:
                        if kw.lower() in text:
                            return False
        return True

    # ─── 内部工具 ───────────────────────────────────────────────────

    def _check_outfit_stability(
        self,
        prompt: str,
        character_masters: Optional[List[CharacterMaster]],
    ) -> Tuple[bool, str]:
        """检查服装关键词是否与角色母版主服装一致"""
        if not character_masters:
            return True, ""
        for master in character_masters:
            if not master.outfit_primary:
                continue
            # 取服装主关键词（第一个名词）
            outfit_kw = master.outfit_primary.split()[0].lower()
            if outfit_kw and outfit_kw not in prompt.lower():
                return False, (
                    f"角色 {master.name} 的服装关键词 '{outfit_kw}' "
                    f"未出现在 prompt 中（母版: {master.outfit_primary}）"
                )
        return True, ""

    def _check_hair_drift(
        self,
        prompt: str,
        character_masters: Optional[List[CharacterMaster]],
    ) -> Tuple[bool, str]:
        """检测发型描述与角色母版是否一致"""
        if not character_masters:
            return False, ""
        for master in character_masters:
            if not master.hair_style:
                continue
            # 取发型的关键描述词（长/短/卷/直）
            hair_kw = master.hair_style.split()[0].lower()
            if hair_kw and len(hair_kw) > 3:
                if hair_kw not in prompt.lower():
                    # 检测是否出现了相反描述
                    opposites = {
                        "waist": ["short", "bob", "pixie"],
                        "short": ["long", "waist", "flowing"],
                        "straight": ["curly", "wavy", "permed"],
                        "curly": ["straight", "flat"],
                    }
                    for kw, opp_list in opposites.items():
                        if kw in master.hair_style.lower():
                            for opp in opp_list:
                                if opp in prompt.lower():
                                    return True, (
                                        f"角色 {master.name} 发型从 '{master.hair_style}' "
                                        f"漂移为含 '{opp}' 的描述"
                                    )
        return False, ""

    def _extract_color_temperature(self, text: str) -> Optional[int]:
        """从文本中提取色温数值（K）"""
        match = re.search(r"(\d{4,5})\s*[Kk]", text)
        if match:
            return int(match.group(1))
        return None

    # ─── 报告保存 ────────────────────────────────────────────────────

    def save_report(self, report: AuditReport, output_path: str) -> None:
        """保存审核报告为 JSON"""
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(asdict(report), f, ensure_ascii=False, indent=2)
        print(f"[QualityAuditor] 审核报告已保存: {output_path}")
        print(report.summary_text())
