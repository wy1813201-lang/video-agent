"""
关键帧生成系统 (Keyframe Generator)
SOP 第四阶段：基于分镜 + 角色母版生成结构化关键帧图片

核心原则：
- 每张图片必须引用角色母版外貌锚点
- 禁止模糊描述词，必须使用结构化语言
- 图片作为视频生成的唯一视觉基础（i2v）
- 支持九宫格动作示意图生成
"""

import json
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional, Any

from .character_master import CharacterMaster, CharacterMasterRegistry, VAGUE_TERMS_BLACKLIST

# ─────────────────────────── 数据类 ─────────────────────────────────


@dataclass
class KeyframeSpec:
    """单张关键帧规格（结构化描述）"""
    shot_id: str                  # 所属分镜 ID
    frame_role: str               # 帧的角色: main / nine_grid_start / nine_grid_mid / nine_grid_end / emotion_peak / camera_push

    # 【人物描述】强制引用角色母版锚点
    character_anchors: List[str] = field(default_factory=list)  # CharacterMaster.to_anchor_fragment() 输出

    # 【场景描述】
    location: str = ""            # 空间名称，如 "café interior"
    spatial_structure: str = ""   # 远近层次，如 "foreground table, midground window, background blur"
    time_of_day: str = ""         # 如 "golden hour afternoon"
    weather: str = ""             # 如 "soft overcast light, no harsh shadows"
    background_elements: str = "" # 背景元素（数量精简），如 "2-3 bookshelves, single window frame"

    # 【光线/灯光】
    light_direction: str = ""     # 如 "left-side key light at 45 degrees"
    light_temperature: str = ""   # 如 "5600K daylight"
    contrast_level: str = ""      # 如 "low contrast 2:1 ratio"

    # 【构图】
    shot_type: str = ""           # 景别: extreme_wide / wide / full / medium_wide / medium / medium_close / close_up / extreme_close
    camera_angle: str = ""        # 角度: eye_level / low_angle / high_angle / dutch_angle
    subject_position: str = ""    # 主体位置: center / left_third / right_third
    depth_of_field: str = ""      # 如 "shallow DOF, f1.8, background bokeh"

    # 最终编译后的 prompt（由 build_prompt 填入）
    compiled_prompt: str = ""
    negative_prompt: str = (
        "blurry, low quality, deformed face, extra limbs, "
        "inconsistent character, different outfit, changed hairstyle, "
        "vague features, watermark, text overlay"
    )

    # 生成后图片路径
    image_path: str = ""


@dataclass
class NineGridSpec:
    """
    九宫格动作示意图规格
    用途：动作起始 / 动作中段 / 动作结束 / 情绪强化 / 镜头推进节点
    """
    shot_id: str
    action_start: KeyframeSpec = None
    action_mid: KeyframeSpec = None
    action_end: KeyframeSpec = None
    emotion_peak: KeyframeSpec = None
    camera_push_point: KeyframeSpec = None

    def to_frames_list(self) -> List[KeyframeSpec]:
        frames = []
        for attr in ["action_start", "action_mid", "action_end", "emotion_peak", "camera_push_point"]:
            frame = getattr(self, attr)
            if frame:
                frames.append(frame)
        return frames


# ─────────────────────────── 生成器 ─────────────────────────────────

class KeyframeGenerator:
    """
    关键帧生成器
    负责：prompt 构建 → 校验 → 调用 CozexClient → 保存图片路径
    """

    # 景别英文描述映射
    SHOT_TYPE_MAP = {
        "远景": "extreme wide establishing shot",
        "全景": "wide shot, full scene visible",
        "全身": "full body shot, head to toe",
        "中远景": "medium wide shot",
        "中景": "medium shot, waist up",
        "中近景": "medium close-up, chest and shoulders",
        "近景": "close-up shot, face only",
        "特写": "extreme close-up, eyes and lips only",
        "过肩": "over-the-shoulder shot",
        "pov": "first-person POV, subjective view",
    }

    # 镜头角度映射
    ANGLE_MAP = {
        "平视": "eye level, neutral perspective",
        "仰拍": "low angle shot, looking up, conveys power",
        "俯拍": "high angle shot, looking down, bird's eye",
        "斜角": "dutch angle, tilted frame, creates tension",
        "极低": "worm's eye view, extreme low angle",
    }

    # 主体位置映射
    POSITION_MAP = {
        "居中": "subject centered, rule of thirds ignored, symmetrical",
        "左三分之一": "subject on left third of frame, right side open space",
        "右三分之一": "subject on right third of frame, left side open space",
        "左侧": "subject on far left, wide negative space right",
        "右侧": "subject on far right, wide negative space left",
    }

    def __init__(self, output_dir: str = "output/keyframes"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    # ─── prompt 构建 ────────────────────────────────────────────────

    def build_keyframe_prompt(
        self,
        shot: Dict[str, Any],
        character_masters: List[CharacterMaster],
        frame_role: str = "main",
        action_override: str = "",
    ) -> KeyframeSpec:
        """
        构建完整的关键帧规格（KeyframeSpec）。

        Args:
            shot: 来自 film_director_agent 的分镜 dict，包含 shot_id, scene, emotion, action, shot_type, angle 等
            character_masters: 该分镜中出场角色的母版列表
            frame_role: 帧角色标识
            action_override: 覆盖动作描述（九宫格中段/结束帧使用）
        """
        shot_id = shot.get("shot_id", "s_unknown")

        # ── 角色锚点 ──
        character_anchors = [cm.to_anchor_fragment() for cm in character_masters]

        # ── 场景信息 ──
        location = shot.get("location", "")
        time_of_day = shot.get("time_of_day", "daytime")
        weather = shot.get("weather", "clear")
        emotion = shot.get("emotion", "neutral")

        # ── 光线（优先使用场景指定，否则用角色母版基准）──
        if character_masters:
            light_direction, light_temp, contrast = self._parse_lighting_anchor(
                character_masters[0].lighting_anchor
            )
        else:
            light_direction = "soft front-side key light at 45 degrees"
            light_temp = "5600K daylight"
            contrast = "low contrast 2:1 ratio"

        # ── 构图 ──
        shot_type_raw = shot.get("shot_type", "中景")
        camera_angle_raw = shot.get("angle", "平视")
        subject_pos_raw = shot.get("subject_position", "居中")

        shot_type_en = self.SHOT_TYPE_MAP.get(shot_type_raw, shot_type_raw)
        angle_en = self.ANGLE_MAP.get(camera_angle_raw, camera_angle_raw)
        position_en = self.POSITION_MAP.get(subject_pos_raw, subject_pos_raw)

        # ── 动作描述 ──
        action = action_override if action_override else shot.get("action", "")

        spec = KeyframeSpec(
            shot_id=shot_id,
            frame_role=frame_role,
            character_anchors=character_anchors,
            location=location,
            time_of_day=time_of_day,
            weather=weather,
            background_elements=shot.get("background_elements", ""),
            light_direction=light_direction,
            light_temperature=light_temp,
            contrast_level=contrast,
            shot_type=shot_type_en,
            camera_angle=angle_en,
            subject_position=position_en,
            depth_of_field=self._infer_dof(shot_type_raw),
        )

        spec.compiled_prompt = self._compile_prompt(spec, action, emotion)
        return spec

    def build_keyframe_prompt_text(
        self,
        shot: Dict[str, Any],
        character_master: CharacterMaster,
    ) -> str:
        """便捷方法：直接返回 prompt 字符串（用于冒烟测试）"""
        spec = self.build_keyframe_prompt(shot, [character_master])
        return spec.compiled_prompt

    def build_nine_grid_prompt(
        self,
        shot: Dict[str, Any],
        character_masters: List[CharacterMaster],
    ) -> KeyframeSpec:
        """
        生成包含九宫格连续动作描述的单一图像 prompt。
        使用 9-panel storyboard grid 结构。
        """
        action = shot.get("action", shot.get("description", ""))
        panels = self._generate_9_panel_actions(action)
        
        # 使用基础 prompt 构建
        base_spec = self.build_keyframe_prompt(shot, character_masters, "nine_grid_storyboard")
        
        # 改写 compiled_prompt，强制加入九宫格结构
        panel_descriptions = " ".join([f"Panel {i+1}: {act}." for i, act in enumerate(panels)])
        
        nine_grid_prefix = "A 3x3 9-panel storyboard grid. " + panel_descriptions
        
        # 重新组合 prompt，将 9 宫格描述放在最前面
        base_spec.compiled_prompt = nine_grid_prefix + " " + base_spec.compiled_prompt
        return base_spec

    def _generate_9_panel_actions(self, action: str) -> List[str]:
        """
        将核心动作打碎成 9 个微小的连续动作步骤。
        """
        if not action:
            action = "acting in the scene"
            
        return [
            f"preparing for {action}, initial stance",
            f"starting the motion of {action}",
            f"early phase of {action}",
            f"mid-action progression of {action}",
            f"peak motion of {action}",
            f"follow-through of {action}",
            f"reaction and settling from {action}",
            f"post-action pose of {action}",
            f"final resolution of {action}"
        ]

    # ─── prompt 校验 ────────────────────────────────────────────────

    def _validate_no_vague_terms(self, prompt: str) -> bool:
        """
        校验 prompt 不含模糊描述词。
        返回 True 表示通过（无模糊词）；False 表示有问题。
        """
        prompt_lower = prompt.lower()
        found = [term for term in VAGUE_TERMS_BLACKLIST if term.lower() in prompt_lower]
        if found:
            print(f"[KeyframeGenerator][WARNING] 检测到模糊词: {found}")
            return False
        return True

    def validate_prompt(self, prompt: str) -> List[str]:
        """返回所有违规项列表，空列表表示通过"""
        issues = []
        prompt_lower = prompt.lower()
        for term in VAGUE_TERMS_BLACKLIST:
            if term.lower() in prompt_lower:
                issues.append(f"含模糊词: '{term}'")
        if len(prompt) < 50:
            issues.append("prompt 过短（< 50字符），描述可能不充分")
        return issues

    # ─── 图片生成（调用 CozexClient）────────────────────────────────

    async def generate_keyframe(
        self,
        spec: KeyframeSpec,
        client,         # CozexClient 实例
        shot_dir: Optional[str] = None,
    ) -> str:
        """
        调用 CozexClient 生成关键帧图片。
        返回生成图片的本地路径。
        """
        # 校验
        issues = self.validate_prompt(spec.compiled_prompt)
        if issues:
            print(f"[KeyframeGenerator][WARN] 分镜 {spec.shot_id} prompt 校验警告: {issues}")

        save_dir = Path(shot_dir) if shot_dir else self.output_dir / spec.shot_id
        save_dir.mkdir(parents=True, exist_ok=True)

        try:
            result = client.image_generation(spec.compiled_prompt)
            image_path = result.get("saved_path", "")
            spec.image_path = image_path
            # 同步保存 spec JSON
            spec_path = save_dir / f"{spec.frame_role}_spec.json"
            with open(spec_path, "w", encoding="utf-8") as f:
                json.dump(asdict(spec), f, ensure_ascii=False, indent=2)
            print(f"[KeyframeGenerator] 关键帧生成成功: {image_path}")
            return image_path
        except Exception as e:
            print(f"[KeyframeGenerator][ERROR] 分镜 {spec.shot_id} 图片生成失败: {e}")
            raise

    async def generate_nine_grid(
        self,
        nine_grid: NineGridSpec,
        client,
        shot_dir: Optional[str] = None,
    ) -> Dict[str, str]:
        """
        批量生成九宫格所有帧。返回 {frame_role: image_path} 映射。
        """
        results = {}
        for frame in nine_grid.to_frames_list():
            try:
                path = await self.generate_keyframe(frame, client, shot_dir)
                results[frame.frame_role] = path
            except Exception as e:
                results[frame.frame_role] = f"ERROR:{e}"
        return results

    # ─── 工具方法 ───────────────────────────────────────────────────

    def _compile_prompt(
        self,
        spec: KeyframeSpec,
        action: str,
        emotion: str,
    ) -> str:
        """将 KeyframeSpec 编译为最终 prompt 字符串（SOP 规范格式）"""
        parts = []

        # 1. 角色外貌锚点（必须第一位）
        if spec.character_anchors:
            parts.append(", ".join(spec.character_anchors))

        # 2. 动作
        if action:
            parts.append(action)

        # 3. 情绪状态
        if emotion:
            parts.append(f"{emotion} emotional expression")

        # 4. 场景
        scene_parts = [spec.location]
        if spec.time_of_day:
            scene_parts.append(spec.time_of_day)
        if spec.weather:
            scene_parts.append(spec.weather)
        if spec.background_elements:
            scene_parts.append(spec.background_elements)
        parts.append(", ".join(p for p in scene_parts if p))

        # 5. 光线
        lighting_parts = [spec.light_direction, spec.light_temperature, spec.contrast_level]
        parts.append(", ".join(p for p in lighting_parts if p))

        # 6. 构图
        composition_parts = [spec.shot_type, spec.camera_angle, spec.subject_position]
        if spec.depth_of_field:
            composition_parts.append(spec.depth_of_field)
        parts.append(", ".join(p for p in composition_parts if p))

        # 7. 质量后缀
        parts.append(
            "hyper-realistic, highly attractive idol-drama aesthetic, high color saturation, "
            "photorealistic, high detail, 8k resolution, cinematic composition, "
            "portrait vertical 9:16, consistent character design, masterpiece"
        )

        return ", ".join(p for p in parts if p)

    def _parse_lighting_anchor(self, lighting_anchor: str):
        """从 lighting_anchor 字符串解析方向、色温、对比度"""
        direction = "soft left-side key light at 45 degrees"
        temperature = "5600K daylight"
        contrast = "low contrast 2:1 ratio"
        if "K" in lighting_anchor:
            for segment in lighting_anchor.split(","):
                segment = segment.strip()
                if "K" in segment and any(c.isdigit() for c in segment):
                    temperature = segment
                elif "contrast" in segment.lower():
                    contrast = segment
                elif "light" in segment.lower():
                    direction = segment
        return direction, temperature, contrast

    def _infer_dof(self, shot_type_raw: str) -> str:
        """根据景别推断景深设置"""
        dof_map = {
            "特写": "extremely shallow DOF, f1.2, heavy bokeh",
            "近景": "shallow DOF, f1.8, soft background bokeh",
            "中近景": "moderate DOF, f2.8, slightly blurred background",
            "中景": "standard DOF, f4, background identifiable",
            "中远景": "deep DOF, f8, background clear",
            "全景": "deep DOF, f11, full scene in focus",
            "远景": "deep DOF, f16, panoramic clarity",
        }
        return dof_map.get(shot_type_raw, "standard DOF, f4")

    def save_storyboard_with_keyframes(
        self,
        storyboard: Dict[str, Any],
        keyframe_results: Dict[str, str],
        output_path: str,
    ) -> None:
        """
        将关键帧图片路径注入分镜 JSON 并保存。
        keyframe_results: {shot_id: image_path}
        """
        for scene in storyboard.get("scenes", []):
            for shot in scene.get("shots", []):
                shot_id = shot.get("shot_id", "")
                if shot_id in keyframe_results:
                    shot["keyframe_image_path"] = keyframe_results[shot_id]

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(storyboard, f, ensure_ascii=False, indent=2)
        print(f"[KeyframeGenerator] 分镜（含关键帧路径）已保存: {output_path}")
