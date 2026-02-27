"""
提示词生成器 v2.0
基于 GitHub 最火 Seedance 2.0 提示词格式优化
参考: https://github.com/YouMind-OpenLab/awesome-seedance-2-prompts

核心结构：[时间] 镜头 | 运镜 | 动作描述 | 画面细节
"""

import random
from typing import List, Optional
from dataclasses import dataclass, field
from enum import Enum


class CameraMovement(str, Enum):
    """专业运镜指令 - 基于 Seedance 2.0 最佳实践"""
    # 推进/拉远
    PUSH_IN = "push-in, camera moves closer"
    PULL_BACK = "pull-back, camera retreats"
    DOLLY_ZOOM = "dolly zoom, vertigo effect"

    # 角度
    LOW_ANGLE = "low angle, looking up"
    HIGH_ANGLE = "high angle, looking down"
    EYE_LEVEL = "eye level, neutral angle"

    # 运动
    TRACKING = "tracking shot, following subject"
    PAN = "pan left/right, horizontal sweep"
    TILT = "tilt up/down, vertical sweep"
    ORBIT = "orbiting shot, circling around"
    CRANE = "crane shot, vertical movement"

    # 特效
    SLOW_MO = "slow motion, 0.5x speed"
    FAST_MO = "fast motion, time-lapse"
    HANDHELD = "handheld camera, shake effect"
    STABILIZED = "stabilized, smooth movement"


class ShotType(str, Enum):
    """镜头类型"""
    EXTREME_WIDE = "extreme wide shot, establishing"
    WIDE = "wide shot, full scene"
    FULL = "full shot, entire body"
    MEDIUM_WIDE = "medium wide shot"
    MEDIUM = "medium shot, waist up"
    MEDIUM_CLOSE = "medium close-up, chest up"
    CLOSE_UP = "close-up, face only"
    EXTREME_CLOSE = "extreme close-up, eyes/mouth"
    OVER_SHOULDER = "over the shoulder shot"
    POV = "first-person POV, subjective view"


class LightingStyle(str, Enum):
    """灯光风格"""
    CINEMATIC = "cinematic lighting, professional"
    NATURAL = "natural light, soft glow"
    NEON = "neon lights, colorful glow"
    REMBRANDT = "Rembrandt lighting, dramatic shadows"
    SOFT_BOX = "soft box, even illumination"
    BACKLIGHT = "backlit, rim light, silhouette"
    CHIAROSCURO = "high contrast, chiaroscuro"


# ============ 风格模板 ============

XIANXIA_ACTIONS = [
    "仙人缓缓伸出手掌，掌心凝聚星辰之光",
    "双手托起星河，星光在指尖流转",
    "衣袂飘飘，身形腾空而起",
    "周身环绕金色光芒，长发随风舞动",
    "眼眸中倒映星河，深邃如宇宙",
    "剑指苍穹，万道剑芒齐发",
    "踏云而行，步步生莲",
]

XIANXIA_VISUALS = [
    "浩瀚星空，银河倾泻，星辰之光如瀑布般洒落",
    "云海翻腾，霞光万道，仙人立于云端",
    "金色光芒环绕周身，如同神祇降临",
    "星河在身后旋转，天地为之变色",
    "仙气飘飘，超然脱俗，电影级画质",
    "古风建筑，飞檐翘角，烟雾缭绕",
    "桃花漫天，落英缤纷，如梦似幻",
]

SCIFI_ACTIONS = [
    "战士迈步向前，机甲发出轰鸣",
    "激光剑挥动，光芒四射",
    "飞船引擎启动，火焰喷射",
    "数据传输中，数字流环绕",
    "机械臂展开，精准操作",
]

SCIFI_VISUALS = [
    "霓虹灯闪烁，赛博朋克城市，雨夜反光",
    "机甲反射金属光泽，科技感十足",
    "星空背景，宇宙深空，星云涌动",
    "全息投影，数据流浮动，蓝色光芒",
    "未来都市，摩天大楼，飞行器穿梭",
]

STYLE_SUFFIXES = [
    "8k, photorealistic, cinematic quality, film grain, professional cinematography",
    "extreme detail, sharp focus, masterpiece, breathtaking view, depth of field",
    "volumetric lighting, god rays, atmospheric fog, depth of field",
    "Rembrandt lighting, dramatic shadows, high contrast, color grading",
]


# ============ 核心数据类 ============

@dataclass
class CinematicShot:
    """
    单镜头数据 - Seedance 2.0 格式
    输出结构: [时间] 镜头 | 运镜 | 动作描述 | 画面细节
    """
    start_time: float
    end_time: float
    shot_type: ShotType
    camera_movement: CameraMovement
    action: str
    visual: str
    lighting: LightingStyle = LightingStyle.CINEMATIC
    effects: str = ""

    def to_prompt(self) -> str:
        """转换为 Seedance 2.0 标准格式"""
        time_str = f"{self.start_time:.1f}-{self.end_time:.1f}s"
        parts = [
            f"[{time_str}]",
            self.shot_type.value,
            self.camera_movement.value,
            self.action,
            self.visual,
            self.lighting.value,
        ]
        if self.effects:
            parts.append(self.effects)
        return " | ".join(parts)

    def to_simple_prompt(self) -> str:
        """简化版提示词（适合单图/单镜头生成）"""
        return (
            f"{self.shot_type.value}, {self.camera_movement.value}, "
            f"{self.action}, {self.visual}, {self.lighting.value}"
        )


@dataclass
class VideoPrompt:
    """
    完整视频提示词 - 支持多镜头组合
    """
    shots: List[CinematicShot] = field(default_factory=list)
    overall_style: str = ""
    resolution: str = "720p"
    aspect_ratio: str = "9:16"
    duration: float = 5.0

    def add_shot(self, shot: CinematicShot) -> "VideoPrompt":
        """链式添加镜头"""
        self.shots.append(shot)
        return self

    def to_seedance_prompt(self) -> str:
        """
        输出完整 Seedance 2.0 格式（带时间轴）
        适合支持时间标记的平台
        """
        if not self.shots:
            return ""
        lines = [shot.to_prompt() for shot in self.shots]
        if self.overall_style:
            lines.append(f"[Overall Style] {self.overall_style}")
        return "\n".join(lines)

    def to_jimeng_prompt(self) -> str:
        """
        输出即梦 AI 格式（无时间标记，连续描述）
        """
        if not self.shots:
            return ""
        parts = []
        for shot in self.shots:
            parts.append(shot.action)
            parts.append(shot.visual)
        base = ". ".join(parts)
        suffix = self._get_style_suffix()
        return f"{base}. {suffix}"

    def _get_style_suffix(self) -> str:
        suffix = random.choice(STYLE_SUFFIXES)
        if self.aspect_ratio == "9:16":
            suffix += ", vertical video, 9:16 aspect ratio"
        elif self.aspect_ratio == "16:9":
            suffix += ", horizontal video, 16:9 aspect ratio"
        return suffix


# ============ 主生成器 ============

class PromptBuilderV2:
    """AI视频提示词生成器 v2.0 - 基于 Seedance 2.0 最佳实践"""

    def __init__(self, config=None):
        self.config = config
        self.style = getattr(config, "style", "cinematic") if config else "cinematic"

    def generate_cinematic_prompt(
        self,
        description: str,
        duration: float = 5.0,
        style: str = "xianxia",
        lighting: Optional[LightingStyle] = None,
    ) -> VideoPrompt:
        """
        从场景描述生成电影感多镜头提示词

        Args:
            description: 场景描述
            duration: 视频时长（秒）
            style: 风格 (xianxia / scifi / cinematic)
            lighting: 灯光风格，默认自动选择

        Returns:
            VideoPrompt 对象
        """
        prompt = VideoPrompt(duration=duration)
        num_shots = max(2, int(duration / 2))
        shot_duration = duration / num_shots

        for i in range(num_shots):
            start = i * shot_duration
            end = (i + 1) * shot_duration
            light = lighting or random.choice(list(LightingStyle))

            if i == 0:
                # 开场：建立场景，推进镜头
                shot = CinematicShot(
                    start_time=start,
                    end_time=end,
                    shot_type=ShotType.WIDE,
                    camera_movement=CameraMovement.PUSH_IN,
                    action=self._pick_action(description, style),
                    visual=self._pick_visual(description, style),
                    lighting=LightingStyle.CINEMATIC,
                    effects="establishing shot, scene setting",
                )
            elif i == num_shots - 1:
                # 结尾：特写收尾，拉远
                shot = CinematicShot(
                    start_time=start,
                    end_time=end,
                    shot_type=ShotType.CLOSE_UP,
                    camera_movement=CameraMovement.PULL_BACK,
                    action="镜头缓缓拉远，画面渐隐",
                    visual="余韵悠长，意境深远",
                    lighting=light,
                    effects="fade out, conclusion",
                )
            else:
                # 中间：动态运镜
                shot = CinematicShot(
                    start_time=start,
                    end_time=end,
                    shot_type=random.choice([
                        ShotType.MEDIUM,
                        ShotType.MEDIUM_CLOSE,
                        ShotType.CLOSE_UP,
                    ]),
                    camera_movement=random.choice([
                        CameraMovement.TRACKING,
                        CameraMovement.ORBIT,
                        CameraMovement.SLOW_MO,
                        CameraMovement.DOLLY_ZOOM,
                    ]),
                    action=self._pick_action(description, style),
                    visual=self._pick_visual(description, style),
                    lighting=light,
                    effects="dynamic movement, cinematic",
                )

            prompt.shots.append(shot)

        return prompt

    def _pick_action(self, description: str, style: str) -> str:
        if style == "xianxia":
            return random.choice(XIANXIA_ACTIONS)
        elif style == "scifi":
            return random.choice(SCIFI_ACTIONS)
        return description

    def _pick_visual(self, description: str, style: str) -> str:
        if style == "xianxia":
            return random.choice(XIANXIA_VISUALS)
        elif style == "scifi":
            return random.choice(SCIFI_VISUALS)
        return description

    def generate_xianxia_prompt(self, theme: str, duration: float = 5.0) -> str:
        """生成仙侠风格提示词（即梦格式）"""
        prompt = self.generate_cinematic_prompt(
            description=theme,
            duration=duration,
            style="xianxia",
        )
        return prompt.to_jimeng_prompt()

    def enhance_prompt(self, base_prompt: str) -> str:
        """增强现有提示词，注入专业运镜和质量关键词"""
        camera = random.choice([
            "tracking shot", "push-in", "pull-back", "dolly zoom",
            "low-angle", "handheld", "cinematic lighting",
        ])
        quality = random.choice([
            "8k, photorealistic, film grain, depth of field",
            "cinematic lighting, professional cinematography",
            "high contrast, color grading, masterpiece",
        ])
        return f"{base_prompt}, {camera}, {quality}"


# ============ 快捷函数 ============

def create_xianxia_prompt(theme: str, duration: float = 5.0) -> str:
    """
    创建仙侠风格提示词

    Args:
        theme: 主题描述，如"徒手摘星辰"
        duration: 视频时长（秒）

    Returns:
        即梦可用的提示词字符串

    Example:
        >>> print(create_xianxia_prompt("仙人徒手摘星辰", 6.0))
    """
    return PromptBuilderV2().generate_xianxia_prompt(theme, duration)


def create_cinematic_prompt(
    description: str,
    duration: float = 5.0,
    style: str = "xianxia",
    output_format: str = "jimeng",
) -> str:
    """
    创建电影感提示词

    Args:
        description: 场景描述
        duration: 视频时长（秒）
        style: 风格 (xianxia / scifi / cinematic)
        output_format: 输出格式 (jimeng / seedance)

    Returns:
        提示词字符串

    Example:
        >>> print(create_cinematic_prompt("赛博朋克街头追逐", style="scifi"))
        >>> print(create_cinematic_prompt("仙人御剑飞行", output_format="seedance"))
    """
    builder = PromptBuilderV2()
    prompt = builder.generate_cinematic_prompt(description, duration, style)
    if output_format == "seedance":
        return prompt.to_seedance_prompt()
    return prompt.to_jimeng_prompt()


# ============ 测试 ============

if __name__ == "__main__":
    print("=" * 60)
    print("Seedance 2.0 提示词生成器 v2.0 测试")
    print("=" * 60)

    # 测试1: 仙侠快捷函数
    print("\n[测试1] 仙侠风格 - 即梦格式")
    print(create_xianxia_prompt("仙人徒手摘星辰", duration=6.0))

    # 测试2: 科幻风格
    print("\n[测试2] 科幻风格 - 即梦格式")
    print(create_cinematic_prompt("赛博朋克街头追逐", style="scifi", duration=4.0))

    # 测试3: Seedance 完整格式（带时间轴）
    print("\n[测试3] 仙侠风格 - Seedance 时间轴格式")
    print(create_cinematic_prompt("古装美女御剑飞行", duration=6.0, output_format="seedance"))

    # 测试4: 手动构建镜头
    print("\n[测试4] 手动构建多镜头")
    vp = VideoPrompt(duration=6.0, aspect_ratio="9:16")
    vp.add_shot(CinematicShot(
        start_time=0.0, end_time=2.0,
        shot_type=ShotType.WIDE,
        camera_movement=CameraMovement.PUSH_IN,
        action="仙人立于山巅，俯瞰云海",
        visual="云海翻腾，霞光万道",
        lighting=LightingStyle.CINEMATIC,
    ))
    vp.add_shot(CinematicShot(
        start_time=2.0, end_time=4.0,
        shot_type=ShotType.CLOSE_UP,
        camera_movement=CameraMovement.SLOW_MO,
        action="手指轻触星辰，星光流转",
        visual="金色光芒在指尖凝聚",
        lighting=LightingStyle.BACKLIGHT,
    ))
    vp.add_shot(CinematicShot(
        start_time=4.0, end_time=6.0,
        shot_type=ShotType.MEDIUM,
        camera_movement=CameraMovement.PULL_BACK,
        action="身形腾空，御剑而去",
        visual="剑光划破苍穹，消失于星河",
        lighting=LightingStyle.CHIAROSCURO,
    ))
    print(vp.to_seedance_prompt())

    # 测试5: enhance_prompt
    print("\n[测试5] 增强现有提示词")
    builder = PromptBuilderV2()
    raw = "一个女孩站在海边看日落"
    print(builder.enhance_prompt(raw))
