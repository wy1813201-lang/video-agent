#!/usr/bin/env python3
"""
AI Film Director Agent V3
将剧本文本转换为电影级分镜系统

执行流程：
1. DIRECTOR INTENT ANALYSIS - 分析导演意图
2. SEMANTIC SCENE SEGMENTATION - 语义分镜
3. SHOT PLANNING SYSTEM - 镜头规划
4. VISUAL DIRECTOR ENHANCEMENT - 视觉增强
5. CHARACTER CONSISTENCY SYSTEM - 角色一致性
6. CAMERA MOTION GENERATION - 运镜设计
7. PROMPT COMPILER - Prompt 编译
8. OUTPUT FORMAT - 输出 FILM_STORYBOARD JSON
"""

import json
import re
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional
from enum import Enum


class CameraMovement(str, Enum):
    """运镜指令"""
    SLOW_PUSH = "slow push, camera slowly moves closer"
    DOLLY_IN = "dolly in, smooth forward movement"
    DOLLY_OUT = "dolly out, revealing wider scene"
    PULL_BACK = "pull back, camera retreats"
    TRACKING = "tracking shot, camera follows subject"
    ORBIT = "orbit shot, camera circles around subject"
    HANDHELD = "handheld camera, organic shake"
    TILT_UP = "tilt up, vertical pan upward"
    PAN = "pan shot, horizontal sweep"
    CRANE = "crane shot, rising elevation"
    WHIP_PAN = "whip pan, fast horizontal transition"
    SLOW_MO = "slow motion, time dilation"
    STABILIZED = "gimbal stabilized, ultra-smooth"


class CameraAngle(str, Enum):
    """镜头角度"""
    LOW = "low angle, looking up, heroic"
    HIGH = "high angle, bird's eye, dominant"
    EYE = "eye level, neutral perspective"
    DUTCH = "dutch angle, tilted, tension"
    WORM = "worm's eye, extreme low"
    WIDE = "wide angle, establishing scene"  # 添加


class LensType(str, Enum):
    """镜头类型"""
    WIDE = "wide angle lens, expansive view"
    STANDARD = "standard lens, natural perspective"
    TELEPHOTO = "telephoto lens, compressed depth"
    MACRO = "macro lens, extreme close-up"
    FISHEYE = "fisheye lens, dramatic distortion"


class LightingStyle(str, Enum):
    """灯光风格"""
    NATURAL = "natural daylight, soft shadows"
    CHIAROSCURO = "chiaroscuro, dramatic light and shadow"
    NEON = "neon lighting, cyberpunk atmosphere"
    WARM = "warm lighting, cozy intimate"
    COOL = "cool lighting, clinical mood"
    HIGH_KEY = "high key, bright airy"
    LOW_KEY = "low key, dark mysterious"


@dataclass
class Character:
    """角色数据库"""
    character_id: str
    name: str
    face_identity: str
    clothing_style: str
    color_palette: str
    visual_presence: str


@dataclass
class Shot:
    """单个镜头"""
    shot_id: str
    shot_type: str  # establishing, medium, close-up, detail, motion
    description: str
    camera_angle: str
    lens_type: str
    lighting_style: str
    composition: str
    mood: str
    camera_motion: str
    prompt: str
    # Two-step prompts (populated by compile_prompts_two_step)
    keyframe_image_prompt: str = ""   # STEP 1: for image generation (CoZex/Jimeng)
    video_prompt: str = ""            # STEP 2: for video generation (Jimeng i2v)
    continuity_from_shot_id: str = ""   # 上一镜头 ID（用于连续性）
    continuity_state: Dict[str, str] = field(default_factory=dict)  # 当前镜头连续性状态


@dataclass
class Scene:
    """场景"""
    scene_id: str
    location: str
    time_of_day: str
    emotional_tone: str
    content: str = ""
    shots: List[Shot] = field(default_factory=list)


@dataclass
class DirectorIntent:
    """导演意图分析结果"""
    main_emotion: str
    narrative_rhythm: str
    visual_style: str
    story_focus: str


class FilmDirectorAgent:
    """AI Film Director Agent - 电影级分镜生成器"""
    
    # 角色数据库
    characters: Dict[str, Character] = {}
    
    def __init__(self, script: str):
        self.script = script
        self.scenes: List[Scene] = []
        self.director_intent: Optional[DirectorIntent] = None
    
    # ------------------------------------------------------------------
    # STEP 1: DIRECTOR INTENT ANALYSIS
    # ------------------------------------------------------------------
    def analyze_director_intent(self) -> DirectorIntent:
        """
        分析剧本整体导演意图
        输出：Main Emotion, Narrative Rhythm, Visual Style, Story Focus
        """
        script_lower = self.script.lower()
        
        # 分析主要情感
        emotions = []
        if any(w in script_lower for w in ["复仇", "愤怒", "战斗", "爆发"]):
            emotions.append("复仇/愤怒")
        if any(w in script_lower for w in ["爱情", "温柔", "甜蜜", "拥抱"]):
            emotions.append("爱情/温情")
        if any(w in script_lower for w in ["悬疑", "紧张", "恐怖", "黑暗"]):
            emotions.append("悬疑/紧张")
        if any(w in script_lower for w in ["搞笑", "幽默", "尴尬", "乌龙"]):
            emotions.append("喜剧/幽默")
        
        main_emotion = emotions[0] if emotions else "剧情/冲突"
        
        # 分析叙事节奏
        if "反转" in self.script or "震惊" in self.script:
            narrative_rhythm = "快节奏，多反转"
        elif "回忆" in self.script or "过去" in self.script:
            narrative_rhythm = "中节奏，回忆穿插"
        else:
            narrative_rhythm = "标准节奏，循序渐进"
        
        # 分析视觉风格
        if "豪门" in self.script or "总裁" in self.script:
            visual_style = "高端时尚，都市奢华"
        elif "古代" in self.script or "皇宫" in self.script:
            visual_style = "古风典雅，东方美学"
        elif "科幻" in self.script or "未来" in self.script:
            visual_style = "赛博朋克，未来科技"
        else:
            visual_style = "现代简约，电影质感"
        
        # 分析故事焦点
        story_focus = "人物命运与情感冲突"
        
        self.director_intent = DirectorIntent(
            main_emotion=main_emotion,
            narrative_rhythm=narrative_rhythm,
            visual_style=visual_style,
            story_focus=story_focus
        )
        
        return self.director_intent
    
    # ------------------------------------------------------------------
    # STEP 2: SEMANTIC SCENE SEGMENTATION
    # ------------------------------------------------------------------
    def segment_scenes(self) -> List[Scene]:
        """
        语义分镜 - 按地点/时间/动作/情绪变化自动划分
        不使用"场景"关键词切分
        """
        # 提取场景块（基于位置标记如 [xxx] 或 场景X:）
        scene_patterns = [
            r'\[([^\]]+)\]',  # [公司大厅]
            r'场景\d+[:：]',   # 场景1:
        ]
        
        segments = []
        current_pos = 0
        
        for pattern in scene_patterns:
            matches = list(re.finditer(pattern, self.script))
            for match in matches:
                location = match.group(1) if match.lastindex else "未知地点"
                start = match.end()
                
                # 找到下一个场景开始位置
                next_match = None
                for p in scene_patterns:
                    next_matches = list(re.finditer(p, self.script[start:]))
                    if next_matches:
                        next_match = next_matches[0]
                        break
                
                end = start + next_match.start() if next_match else len(self.script)
                text = self.script[start:end].strip()
                
                if text:
                    segments.append({
                        "location": location,
                        "text": text
                    })
        
        # 如果没有匹配到任何场景标记，整个剧本作为一个场景
        if not segments:
            segments = [{"location": "场景1", "text": self.script}]
        
        # 创建 Scene 对象
        self.scenes = []
        for i, seg in enumerate(segments, 1):
            scene = Scene(
                scene_id=f"Scene_{i:02d}",
                location=seg["location"],
                time_of_day=self._infer_time(seg["text"]),
                emotional_tone=self._infer_emotion(seg["text"]),
                content=seg["text"],
                shots=[]
            )
            self.scenes.append(scene)
        
        return self.scenes
    
    def _infer_time(self, text: str) -> str:
        """推断时间"""
        text_lower = text.lower()
        if "清晨" in text or "早晨" in text:
            return "清晨/早晨"
        elif "黄昏" in text or "傍晚" in text:
            return "黄昏/傍晚"
        elif "夜晚" in text or "深夜" in text:
            return "夜晚/深夜"
        elif "中午" in text or "午" in text:
            return "中午"
        return "日间"
    
    def _infer_emotion(self, text: str) -> str:
        """推断情绪"""
        if any(w in text for w in ["愤怒", "争吵", "质问"]):
            return "紧张/对抗"
        elif any(w in text for w in ["笑", "开心", "幽默"]):
            return "轻松/幽默"
        elif any(w in text for w in ["哭", "悲伤", "离开"]):
            return "悲伤/离别"
        elif any(w in text for w in ["震惊", "反转", "惊讶"]):
            return "震惊/反转"
        return "平静/叙事"
    
    # ------------------------------------------------------------------
    # STEP 3: SHOT PLANNING SYSTEM
    # ------------------------------------------------------------------
    def plan_shots(self) -> None:
        """为每个场景生成电影镜头结构"""
        for scene in self.scenes:
            # 建立镜 (Establishing)
            establishing = Shot(
                shot_id=f"{scene.scene_id}_EST",
                shot_type="establishing",
                description=f"建立场景：{scene.location}",
                camera_angle=CameraAngle.WIDE.value,
                lens_type=LensType.WIDE.value,
                lighting_style=LightingStyle.NATURAL.value,
                composition="centered, symmetric",
                mood="neutral",
                camera_motion=CameraMovement.CRANE.value,
                prompt=""
            )
            scene.shots.append(establishing)
            
            # 中镜 (Medium Shot)
            medium = Shot(
                shot_id=f"{scene.scene_id}_MED",
                shot_type="medium",
                description="角色对话/动作",
                camera_angle=CameraAngle.EYE.value,
                lens_type=LensType.STANDARD.value,
                lighting_style=LightingStyle.NATURAL.value,
                composition="rule of thirds",
                mood=scene.emotional_tone,
                camera_motion=CameraMovement.STABILIZED.value,
                prompt=""
            )
            scene.shots.append(medium)
            
            # 特写 (Close-up)
            closeup = Shot(
                shot_id=f"{scene.scene_id}_CU",
                shot_type="close-up",
                description="角色表情/反应",
                camera_angle=CameraAngle.EYE.value,
                lens_type=LensType.TELEPHOTO.value,
                lighting_style=LightingStyle.CHIAROSCURO.value,
                composition="centered face",
                mood=scene.emotional_tone,
                camera_motion=CameraMovement.SLOW_PUSH.value,
                prompt=""
            )
            scene.shots.append(closeup)
            
            # 细节镜 (Detail)
            detail = Shot(
                shot_id=f"{scene.scene_id}_DET",
                shot_type="detail",
                description="关键物体/道具",
                camera_angle=CameraAngle.HIGH.value,
                lens_type=LensType.MACRO.value,
                lighting_style=LightingStyle.HIGH_KEY.value,
                composition="centered object",
                mood="focused",
                camera_motion=CameraMovement.STABILIZED.value,
                prompt=""
            )
            scene.shots.append(detail)
            
            # 运动镜 (Motion)
            motion = Shot(
                shot_id=f"{scene.scene_id}_MOT",
                shot_type="motion",
                description="角色移动/场景转换",
                camera_angle=CameraAngle.LOW.value,
                lens_type=LensType.WIDE.value,
                lighting_style=LightingStyle.NATURAL.value,
                composition="dynamic leading",
                mood="energetic",
                camera_motion=CameraMovement.TRACKING.value,
                prompt=""
            )
            scene.shots.append(motion)
    
    # ------------------------------------------------------------------
    # STEP 4: VISUAL DIRECTOR ENHANCEMENT
    # ------------------------------------------------------------------
    def enhance_visuals(self) -> None:
        """为每个镜头补全视觉语言"""
        for scene in self.scenes:
            for shot in scene.shots:
                # 根据场景位置和情绪增强视觉
                location_info = self._get_location_details(scene.location)
                
                # 更新灯光和构图
                if shot.shot_type == "establishing":
                    shot.lighting_style = f"{LightingStyle.NATURAL.value}, {location_info.get('lighting', 'soft light')}"
                    shot.composition = f"{shot.composition}, {location_info.get('composition', 'wide establishing')}"
                
                elif shot.shot_type == "medium":
                    shot.lighting_style = f"{LightingStyle.CHIAROSCURO.value}, key light with fill"
                    shot.composition = f"{shot.composition}, character centered"
                
                elif shot.shot_type == "close-up":
                    shot.lighting_style = f"{LightingStyle.LOW_KEY.value}, dramatic shadows"
                    shot.composition = f"{shot.composition}, face fills frame"
    
    def _get_location_details(self, location: str) -> Dict[str, str]:
        """获取场景位置的视觉细节"""
        location_lower = location.lower()
        
        if "大厅" in location or "会议室" in location:
            return {
                "lighting": "ceiling lights, ambient illumination",
                "composition": "architectural lines lead to subject"
            }
        elif "办公室" in location:
            return {
                "lighting": "window light, desk lamp",
                "composition": "workspace context"
            }
        elif "街头" in location or "外面" in location:
            return {
                "lighting": "natural daylight or street lamps",
                "composition": "environmental context"
            }
        elif "室内" in location:
            return {
                "lighting": "interior ambient",
                "composition": "room context"
            }
        
        return {"lighting": "balanced", "composition": "standard"}
    
    # ------------------------------------------------------------------
    # STEP 5: CHARACTER CONSISTENCY SYSTEM
    # ------------------------------------------------------------------
    def extract_characters(self) -> Dict[str, Character]:
        """建立角色数据库"""
        # 简单提取对话中的角色名（按剧本出现顺序保留）
        character_names: List[str] = []
        seen = set()
        for line in self.script.split('\n'):
            # 匹配 "角色名:" 格式
            match = re.match(r'^([^：:\n]+)[:：]', line.strip())
            if match:
                name = match.group(1).strip()
                if re.match(r'^场景\d+$', name):
                    continue
                if name in {"对话", "台词", "旁白", "字幕"}:
                    continue
                if name and len(name) < 10 and name not in seen:  # 过滤太长的文本
                    seen.add(name)
                    character_names.append(name)
        
        # 为每个角色分配 ID 和固定外观描述
        char_id_map = {
            "林晚": ("CHAR_A", "年轻女性,长直发,精致妆容,黑色职业套装", "深色系,黑色白色", "自信干练"),
            "女主": ("CHAR_A", "年轻女性,长直发,精致妆容,黑色职业套装", "深色系,黑色白色", "自信干练"),
            "保安": ("CHAR_B", "中年男性,制服,身材魁梧", "深蓝色制服", "严厉冷漠"),
            "秘书": ("CHAR_C", "年轻女性,职业套装,高跟鞋", "浅色系,米白色", "傲慢轻视"),
            "陈总": ("CHAR_D", "中年男性,西装,商务气质", "深色西装", "威严自信"),
            "男主": ("CHAR_E", "年轻男性,西装,精英气质", "深色系", "深沉神秘"),
        }
        
        characters = {}
        for name in character_names:
            if name in char_id_map:
                char_id, face, clothing, presence = char_id_map[name]
                characters[name] = Character(
                    character_id=char_id,
                    name=name,
                    face_identity=face,
                    clothing_style=clothing,
                    color_palette="",
                    visual_presence=presence
                )
            else:
                # 未知角色分配新 ID
                char_num = len(characters) + 1
                characters[name] = Character(
                    character_id=f"CHAR_{chr(64+char_num)}",
                    name=name,
                    face_identity="",
                    clothing_style="",
                    color_palette="",
                    visual_presence=""
                )
        
        self.characters = characters
        return characters
    
    # ------------------------------------------------------------------
    # STEP 6: CAMERA MOTION GENERATION
    # ------------------------------------------------------------------
    def generate_camera_motions(self) -> None:
        """为每个镜头生成运镜"""
        motion_mapping = {
            "establishing": [CameraMovement.CRANE, CameraMovement.PULL_BACK],
            "medium": [CameraMovement.STABILIZED, CameraMovement.TRACKING],
            "close-up": [CameraMovement.SLOW_PUSH, CameraMovement.DOLLY_IN],
            "detail": [CameraMovement.TILT_UP, CameraMovement.PAN],
            "motion": [CameraMovement.TRACKING, CameraMovement.ORBIT, CameraMovement.WHIP_PAN],
        }
        
        for scene in self.scenes:
            for shot in scene.shots:
                motions = motion_mapping.get(shot.shot_type, [CameraMovement.STABILIZED])
                shot.camera_motion = motions[0].value
    
    # ------------------------------------------------------------------
    # STEP 7: PROMPT COMPILER (Two-Step: Image → Video)
    # ------------------------------------------------------------------

    def _build_keyframe_image_prompt(self, scene: Scene, shot: Shot) -> str:
        """
        STEP 1: Keyframe Image Prompt - 建立视觉锚点
        
        规范：
        - 人物描述：性别、年龄、体型、服装、发型、外观特征（禁止抽象词）
        - 场景描述：室内/室外、时间、空间结构
        - 光线/灯光：光源方向、光线性质
        - 构图：镜头类型、九宫格构图
        
        用于：CoZex / Jimeng 图像生成
        """
        # ===== 1. 镜头类型 → 构图 =====
        framing_map = {
            "establishing": "establishing wide shot, full scene view",
            "medium": "medium shot, waist up",
            "close-up": "close-up, face visible",
            "detail": "extreme close-up, detail focus",
            "motion": "dynamic action shot",
        }
        framing = framing_map.get(shot.shot_type, "cinematic shot")
        
        # ===== 2. 人物描述 =====
        # 必须包含：性别、年龄、体型、服装、发型、外观特征
        char_desc = self._build_character_anchor(scene)
        
        # ===== 3. 场景描述 =====
        # 室内/室外 + 时间 + 空间结构
        time_of_day = scene.time_of_day or "daytime"
        location = scene.location
        
        # ===== 4. 光线/灯光 =====
        # 光源方向 + 光线性质（用于强化情绪）
        lighting = shot.lighting_style or "natural lighting"
        
        # ===== 5. 构图 =====
        # 九宫格或视觉中心构图
        comp_map = {
            "establishing": "rule of thirds, balanced composition",
            "medium": "rule of thirds, subject positioned left or right",
            "close-up": "centered composition, face as focal point",
            "detail": "centered, isolated subject",
            "motion": "leading room, space for movement",
        }
        composition = comp_map.get(shot.shot_type, "centered composition")
        
        # ===== 组合 Prompt =====
        # 格式：构图 + 场景 + 人物 + 光线 + 构图 + 质量
        parts = [
            framing,
            f"{self._infer_space_type(location)}, {location}, {time_of_day}",
            char_desc,
            lighting,
            composition,
            "cinematic quality, photorealistic, 4k, vertical",
        ]
        return ", ".join(p for p in parts if p)

    def _build_video_prompt(self, scene: Scene, shot: Shot, prev_shot: Optional[Shot] = None) -> str:
        """
        STEP 2: Video Prompt - 仅负责运动层
        
        规范：
        - 镜头运动：只描述运动，不重新描述画面，一种主要运动
        - 人物动作：从关键帧姿态自然开始，一个核心动作，优先微动作
        - 氛围变化：仅允许渐变变化，禁止突然风格切换
        
        用于：Jimeng image-to-video 生成
        """
        # ===== 1. 镜头运动 =====
        # 只描述运动方式，不重新描述画面
        motion_map = {
            "establishing": "static, no camera movement",
            "medium": "gentle push in",
            "close-up": "static hold with subtle rack focus",
            "detail": "static with subtle focus shift",
            "motion": "tracking shot, follow movement",
        }
        camera_motion = motion_map.get(shot.shot_type, "gentle camera movement")
        
        # ===== 2. 人物动作 =====
        # 从关键帧姿态自然开始，优先微动作
        action_map = {
            "establishing": "no character movement, ambient scene",
            "medium": "subtle body movement, slight gesture",
            "close-up": "minimal facial movement, eyes may blink",
            "detail": "static subject, no movement",
            "motion": "character takes a few natural steps through frame",
        }
        character_motion = action_map.get(shot.shot_type, "minimal movement")
        
        # ===== 3. 氛围变化 =====
        # 仅允许渐变变化
        atmo_map = {
            "紧张/对抗": "subtle lighting shift, tension builds gradually",
            "轻松/幽默": "soft warm glow increases slightly",
            "悲伤/离别": "light dims gradually, mood deepens",
            "震惊/反转": "brief lighting pulse, then stabilizes",
            "平静/叙事": "steady, unchanged lighting throughout",
        }
        atmosphere = atmo_map.get(scene.emotional_tone, "steady atmospheric conditions")
        
        # ===== 组合 Prompt =====
        # 格式：镜头运动 + 人物动作 + 氛围 + 质量
        parts = [
            camera_motion,
            character_motion,
            atmosphere,
            "smooth motion, natural progression, no sudden scene change or style switch, cinematic feel",
        ]
        continuity_clause = self._build_continuity_clause(shot, prev_shot)
        if continuity_clause:
            parts.append(continuity_clause)
        return ", ".join(p for p in parts if p)

    def _build_continuity_state(self, scene: Scene, shot: Shot) -> Dict[str, str]:
        """构建镜头连续性状态，供下一镜头继承。"""
        state = {
            "identity_lock": self._build_character_anchor(scene),
            "outfit_lock": self._extract_outfit_lock(scene),
            "lighting_lock": shot.lighting_style,
            "location_lock": scene.location,
            "mood_lock": scene.emotional_tone,
            "action_seed": shot.description,
        }
        return {k: v for k, v in state.items() if v}

    def _build_continuity_clause(self, shot: Shot, prev_shot: Optional[Shot]) -> str:
        """为 video prompt 生成连续性约束语句。"""
        if not prev_shot:
            return (
                "start from this keyframe state, keep character identity and outfit stable, "
                "maintain lighting direction and scene geometry"
            )

        prev = prev_shot.continuity_state or {}
        prev_identity = prev.get("identity_lock", "same character identity")
        prev_outfit = prev.get("outfit_lock", "same outfit")
        prev_light = prev.get("lighting_lock", "same lighting direction")
        prev_action = prev.get("action_seed", "previous action")

        return (
            f"continue naturally from previous shot {prev_shot.shot_id}, keep {prev_identity}, "
            f"keep {prev_outfit}, preserve {prev_light}, continue from {prev_action}"
        )

    def _extract_outfit_lock(self, scene: Scene) -> str:
        """从角色锚点中提取服装锁定描述。"""
        outfits = []
        scene_text = scene.content or ""
        for name, char in self.characters.items():
            if scene_text and name not in scene_text:
                continue
            if char.clothing_style:
                outfits.append(char.clothing_style)
            if len(outfits) >= 2:
                break
        if outfits:
            return "; ".join(outfits)
        return "consistent costume details"

    def _build_character_anchor(self, scene: Scene) -> str:
        """为关键帧构建角色锚点描述，优先使用当前场景中出现的角色。"""
        if not self.characters:
            return "adult character, clear facial features, realistic outfit"

        relevant = []
        scene_text = scene.content or ""
        for name, char in self.characters.items():
            if scene_text and name in scene_text:
                relevant.append((name, char))

        if not relevant:
            relevant = list(self.characters.items())[:1]
        else:
            relevant = relevant[:2]

        descs = []
        for name, char in relevant:
            parts = []
            if char.face_identity:
                parts.append(char.face_identity)
            if char.clothing_style:
                parts.append(char.clothing_style)
            if not parts:
                parts.append(f"{name}, adult, clear facial features, realistic clothing")
            descs.append(", ".join(parts))

        return "; ".join(descs)

    def _infer_space_type(self, location: str) -> str:
        """根据场景地点推断室内/室外。"""
        if any(k in location for k in ["街", "街头", "外", "广场", "公园", "天台", "海边", "山", "森林", "路"]):
            return "exterior"
        return "interior"

    def compile_prompts_two_step(self) -> None:
        """
        Two-step prompt generation for all shots:
          - keyframe_image_prompt → static image generation
          - video_prompt          → image-to-video generation
        Also sets legacy `prompt` field for backward compatibility.
        """
        prev_shot: Optional[Shot] = None
        for scene in self.scenes:
            for shot in scene.shots:
                shot.continuity_from_shot_id = prev_shot.shot_id if prev_shot else ""
                shot.keyframe_image_prompt = self._build_keyframe_image_prompt(scene, shot)
                shot.continuity_state = self._build_continuity_state(scene, shot)
                shot.video_prompt = self._build_video_prompt(scene, shot, prev_shot=prev_shot)
                # Keep legacy prompt = keyframe image prompt
                shot.prompt = shot.keyframe_image_prompt
                prev_shot = shot

    def _build_base_prompt(self, scene: "Scene", shot: Shot) -> str:
        """构建基础 prompt，包含剧本具体内容"""
        char_desc = ""
        for name, char in self.characters.items():
            if char.face_identity:
                char_desc = f"{name}: {char.face_identity}, {char.clothing_style}"
                break

        # 格式：运镜 位置 角色 描述 灯光 情绪 质量
        parts = [
            shot.camera_motion,
            f"{scene.location}",
            char_desc,
            shot.description.replace("\n", " "),
            shot.lighting_style,
            shot.mood,
            "cinematic, photorealistic, 4k",
        ]
        return ", ".join(p for p in parts if p)

    def compile_prompts(self, use_gemini: bool = True) -> None:
        """
        统一 Prompt 结构
        
        Args:
            use_gemini: 是否调用 Gemini 网页版优化 prompt（默认开启）
        """
        # 默认保持 legacy prompt 与关键帧 prompt 一致，便于统一下游入参
        for scene in self.scenes:
            for shot in scene.shots:
                shot.prompt = shot.keyframe_image_prompt or self._build_base_prompt(scene, shot)

        if not use_gemini:
            return

        # 尝试用 Gemini 批量优化
        try:
            from .gemini_web_client import GeminiWebClient
        except ImportError:
            try:
                from gemini_web_client import GeminiWebClient
            except ImportError:
                return  # 无法导入，保留规则 prompt

        client = GeminiWebClient()

        # 收集所有 shot 信息
        all_shots = []
        shot_refs = []
        for scene in self.scenes:
            for shot in scene.shots:
                all_shots.append({
                    "shot_type": shot.shot_type,
                    "description": shot.description,
                    "camera_motion": shot.camera_motion,
                    "camera_angle": shot.camera_angle,
                    "lens_type": shot.lens_type,
                    "lighting": shot.lighting_style,
                    "mood": shot.mood,
                    "scene_location": scene.location,
                })
                shot_refs.append(shot)

        # 批量优化（Gemini 会话复用）
        try:
            optimized = client.optimize_prompts_batch(all_shots)
            for shot_ref, new_prompt in zip(shot_refs, optimized):
                if new_prompt and len(new_prompt) > 30:
                    shot_ref.keyframe_image_prompt = new_prompt
                    shot_ref.prompt = new_prompt
        except Exception:
            pass  # Gemini 失败时保留规则 prompt
    
    # ------------------------------------------------------------------
    # STEP 8: OUTPUT FORMAT
    # ------------------------------------------------------------------
    def generate_storyboard(self) -> Dict[str, Any]:
        """生成 FILM_STORYBOARD 输出"""
        storyboard = {
            "director_intent": asdict(self.director_intent) if self.director_intent else {},
            "characters": {name: asdict(char) for name, char in self.characters.items()},
            "film_storyboard": []
        }
        
        for scene in self.scenes:
            for shot in scene.shots:
                storyboard["film_storyboard"].append({
                    "scene_id": scene.scene_id,
                    "scene_location": scene.location,
                    "scene_time": scene.time_of_day,
                    "scene_emotion": scene.emotional_tone,
                    "shot_id": shot.shot_id,
                    "shot_type": shot.shot_type,
                    "description": shot.description,
                    "camera_angle": shot.camera_angle,
                    "lens_type": shot.lens_type,
                    "lighting": shot.lighting_style,
                    "composition": shot.composition,
                    "mood": shot.mood,
                    "camera_motion": shot.camera_motion,
                    "prompt": shot.prompt,
                    "keyframe_image_prompt": shot.keyframe_image_prompt,
                    "video_prompt": shot.video_prompt,
                    "continuity_from_shot_id": shot.continuity_from_shot_id,
                    "continuity_state": shot.continuity_state,
                })
        
        return storyboard
    
    # ------------------------------------------------------------------
    # MAIN EXECUTION
    # ------------------------------------------------------------------
    def run(self, use_gemini: bool = True) -> Dict[str, Any]:
        """
        执行完整导演流程
        
        Args:
            use_gemini: 是否调用 Gemini 网页版优化 prompt（默认开启）
        """
        # Step 1: 导演意图分析
        self.analyze_director_intent()
        
        # Step 2: 语义分镜
        self.segment_scenes()
        
        # Step 3: 镜头规划
        self.plan_shots()
        
        # Step 4: 视觉增强
        self.enhance_visuals()
        
        # Step 5: 角色一致性
        self.extract_characters()
        
        # Step 6: 运镜设计
        self.generate_camera_motions()
        
        # Step 7a: Two-step prompt generation (image + video, always runs)
        self.compile_prompts_two_step()

        # Step 7b: Optional Gemini enhancement of keyframe_image_prompt
        self.compile_prompts(use_gemini=use_gemini)
        
        # Step 8: 输出
        return self.generate_storyboard()


def create_film_storyboard(script: str, use_gemini: bool = True) -> Dict[str, Any]:
    """
    便捷函数：将剧本转换为电影级分镜

    Args:
        script: 剧本文本
        use_gemini: 是否调用 Gemini 网页版优化 prompt（默认开启，失败自动降级）

    Returns:
        FILM_STORYBOARD JSON 结构
    """
    agent = FilmDirectorAgent(script)
    return agent.run(use_gemini=use_gemini)


# 测试
if __name__ == "__main__":
    test_script = """
场景1: [公司大厅]
保安: 哎，站住。林晚: 我来面试。
场景2: [会议室]
林晚: 这笔并购案的问题在于股权结构。
"""
    
    result = create_film_storyboard(test_script)
    print(json.dumps(result, ensure_ascii=False, indent=2))
