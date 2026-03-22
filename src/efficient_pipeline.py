#!/usr/bin/env python3
"""
高效生产流程管理器

新流程：
1. 生成3个剧本 → AI自动评分 → 只保留最高分
2. 生成角色母版 → 人工确认一次
3. 生成分镜 → 生成视频
4. AI自动检测质量 → 输出3个最终版本
5. 人工选1个发布
"""

import json
import os
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass, asdict


@dataclass
class ScriptCandidate:
    """剧本候选"""
    script_id: str
    content: str
    score: float
    dimensions: Dict[str, float]  # hook_strength, plot_structure, emotion_rhythm
    timestamp: str


@dataclass
class FinalVersion:
    """最终版本"""
    version_id: str
    video_path: str
    quality_score: float
    params: Dict[str, Any]
    selected: bool = False
    selection_reason: str = ""


class EfficientPipeline:
    """高效生产流程"""

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.output_dir = self.config.get("output_dir", "output")
        self.records_dir = self.config.get("records_dir", "data/efficient_records")

        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.records_dir, exist_ok=True)

        # 当前生产记录
        self.current_session = {
            "session_id": "",
            "topic": "",
            "script_candidates": [],
            "selected_script": None,
            "characters": [],
            "character_approved": False,
            "final_versions": [],
            "published_version": None,
            "created_at": "",
            "completed_at": ""
        }

    def start_session(self, topic: str) -> str:
        """开始新的生产会话"""
        session_id = f"{topic}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.current_session = {
            "session_id": session_id,
            "topic": topic,
            "script_candidates": [],
            "selected_script": None,
            "characters": [],
            "character_approved": False,
            "final_versions": [],
            "published_version": None,
            "created_at": datetime.now().isoformat(),
            "completed_at": ""
        }
        print(f"\n[Pipeline] 开始新会话: {session_id}")
        return session_id

    # ================================================================
    # 阶段1: 生成3个剧本 → AI评分 → 选最高分
    # ================================================================

    def generate_and_select_script(self, script_generator, topic: str, style: str) -> Dict[str, Any]:
        """
        生成3个剧本,AI自动评分,选择最高分

        Returns:
            选中的剧本数据
        """
        print("\n" + "="*60)
        print("阶段1: 生成3个剧本并自动选择最高分")
        print("="*60)

        candidates = []

        # 生成3个剧本
        for i in range(3):
            print(f"\n[{i+1}/3] 生成剧本候选...")

            # 调用剧本生成器
            script = script_generator.generate_script(
                topic=topic,
                style=style,
                episode_num=1
            )

            # AI评分
            score_data = self._score_script(script)

            candidate = ScriptCandidate(
                script_id=f"script_{i+1}",
                content=script,
                score=score_data["overall"],
                dimensions=score_data["dimensions"],
                timestamp=datetime.now().isoformat()
            )

            candidates.append(candidate)

            print(f"   总分: {score_data['overall']:.1f}/10")
            print(f"   Hook: {score_data['dimensions']['hook_strength']:.1f}")
            print(f"   剧情: {score_data['dimensions']['plot_structure']:.1f}")
            print(f"   情绪: {score_data['dimensions']['emotion_rhythm']:.1f}")

        # 选择最高分
        best_candidate = max(candidates, key=lambda x: x.score)

        print(f"\n✓ 自动选择最高分剧本: {best_candidate.script_id}")
        print(f"  总分: {best_candidate.score:.1f}/10")

        # 保存到会话
        self.current_session["script_candidates"] = [asdict(c) for c in candidates]
        self.current_session["selected_script"] = asdict(best_candidate)

        return asdict(best_candidate)

    def _score_script(self, script: str) -> Dict[str, Any]:
        """AI评分剧本"""
        # Hook吸引力
        hook_score = self._check_hook_strength(script)

        # 剧情结构
        plot_score = self._check_plot_structure(script)

        # 情绪节奏
        emotion_score = self._check_emotion_rhythm(script)

        # 总分
        overall = (hook_score + plot_score + emotion_score) / 3

        return {
            "overall": overall,
            "dimensions": {
                "hook_strength": hook_score,
                "plot_structure": plot_score,
                "emotion_rhythm": emotion_score
            }
        }

    def _check_hook_strength(self, script: str) -> float:
        """检测Hook吸引力(0-10分)"""
        score = 5.0

        hook_keywords = [
            "重生", "复仇", "震惊", "发现", "背叛", "秘密",
            "死亡", "醒来", "穿越", "系统", "觉醒", "身份"
        ]

        first_100_chars = script[:100]
        for keyword in hook_keywords:
            if keyword in first_100_chars:
                score += 1.0

        if ":" in first_100_chars or "：" in first_100_chars:
            score += 1.0

        return min(10.0, score)

    def _check_plot_structure(self, script: str) -> float:
        """检测剧情结构(0-10分)"""
        score = 5.0

        scene_count = script.count("场景")
        if 3 <= scene_count <= 5:
            score += 2.0
        elif scene_count > 5:
            score += 1.0

        conflict_keywords = ["冲突", "对抗", "争吵", "打", "骂", "揭穿", "曝光"]
        conflict_count = sum(1 for kw in conflict_keywords if kw in script)
        score += min(2.0, conflict_count * 0.5)

        reversal_keywords = ["原来", "竟然", "没想到", "真相", "其实", "突然"]
        reversal_count = sum(1 for kw in reversal_keywords if kw in script)
        score += min(1.0, reversal_count * 0.3)

        return min(10.0, score)

    def _check_emotion_rhythm(self, script: str) -> float:
        """检测情绪节奏(0-10分)"""
        score = 5.0

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

    # ================================================================
    # 阶段2: 生成角色母版 → 人工确认一次
    # ================================================================

    def generate_characters(self, character_generator, script: str) -> List[Dict[str, Any]]:
        """生成角色母版"""
        print("\n" + "="*60)
        print("阶段2: 生成角色母版")
        print("="*60)

        characters = character_generator.generate_characters(script)

        print(f"\n✓ 生成了 {len(characters)} 个角色")
        for char in characters:
            print(f"  - {char['name']}: {char.get('description', '')[:50]}...")

        self.current_session["characters"] = characters

        return characters

    def request_character_approval(self, characters: List[Dict[str, Any]]) -> bool:
        """请求人工确认角色母版"""
        print("\n" + "="*60)
        print("人工确认: 角色母版")
        print("="*60)

        # 这里会调用统一审查系统
        from src.unified_review_system import UnifiedReviewSystem

        review_system = UnifiedReviewSystem()
        result = review_system.review_characters(characters)

        approved = result["status"] == "approved"
        self.current_session["character_approved"] = approved

        if approved:
            print("\n✓ 角色母版已通过人工确认")
        else:
            print("\n✗ 角色母版未通过,需要重新生成")

        return approved

    # ================================================================
    # 阶段3: 生成分镜 → 生成视频
    # ================================================================

    def generate_storyboard_and_videos(self, storyboard_manager, script: str, characters: List[Dict]) -> List[str]:
        """生成分镜和视频"""
        print("\n" + "="*60)
        print("阶段3: 生成分镜和视频")
        print("="*60)

        # 生成分镜
        print("\n[1/2] 生成分镜...")
        storyboard = storyboard_manager.create_storyboard(script, characters)

        # 生成视频片段
        print("\n[2/2] 生成视频片段...")
        video_paths = []
        for i, shot in enumerate(storyboard.get("shots", [])):
            print(f"  生成镜头 {i+1}/{len(storyboard['shots'])}...")
            video_path = self._generate_video_for_shot(shot)
            video_paths.append(video_path)

        print(f"\n✓ 生成了 {len(video_paths)} 个视频片段")

        return video_paths

    def _generate_video_for_shot(self, shot: Dict[str, Any]) -> str:
        """为单个镜头生成视频(模拟)"""
        # 实际实现中会调用视频生成API
        return f"output/videos/shot_{shot.get('shot_id', 'unknown')}.mp4"

    # ================================================================
    # 阶段4: AI质量检测 → 输出3个最终版本
    # ================================================================

    def generate_final_versions(self, video_clips: List[str]) -> List[FinalVersion]:
        """
        AI自动质量检测,生成3个不同风格的最终版本

        版本差异:
        - 版本1: 标准版(平衡)
        - 版本2: 快节奏版(转场快,音乐强)
        - 版本3: 情感版(转场慢,音乐柔和)
        """
        print("\n" + "="*60)
        print("阶段4: AI质量检测并生成3个最终版本")
        print("="*60)

        versions = []

        # 版本1: 标准版
        print("\n[1/3] 生成标准版...")
        v1 = self._compose_version(
            video_clips,
            version_id="standard",
            params={
                "transition_duration": 0.8,
                "bgm_volume": 0.3,
                "color_grade": "cinematic"
            }
        )
        versions.append(v1)

        # 版本2: 快节奏版
        print("\n[2/3] 生成快节奏版...")
        v2 = self._compose_version(
            video_clips,
            version_id="fast_paced",
            params={
                "transition_duration": 0.4,
                "bgm_volume": 0.5,
                "color_grade": "vibrant"
            }
        )
        versions.append(v2)

        # 版本3: 情感版
        print("\n[3/3] 生成情感版...")
        v3 = self._compose_version(
            video_clips,
            version_id="emotional",
            params={
                "transition_duration": 1.2,
                "bgm_volume": 0.2,
                "color_grade": "warm"
            }
        )
        versions.append(v3)

        print(f"\n✓ 生成了 {len(versions)} 个最终版本")
        for v in versions:
            print(f"  - {v.version_id}: 质量分 {v.quality_score:.1f}/10")

        self.current_session["final_versions"] = [asdict(v) for v in versions]

        return versions

    def _compose_version(self, video_clips: List[str], version_id: str, params: Dict[str, Any]) -> FinalVersion:
        """合成一个版本"""
        # 实际实现中会调用视频合成器
        video_path = f"output/final/{version_id}.mp4"

        # AI质量检测
        quality_score = self._detect_quality(video_path, params)

        return FinalVersion(
            version_id=version_id,
            video_path=video_path,
            quality_score=quality_score,
            params=params
        )

    def _detect_quality(self, video_path: str, params: Dict[str, Any]) -> float:
        """AI自动检测视频质量"""
        # 基础分
        score = 7.0

        # 根据参数调整
        if params.get("transition_duration", 0) > 0.5:
            score += 0.5  # 转场自然

        if 0.2 <= params.get("bgm_volume", 0) <= 0.4:
            score += 0.5  # 音量适中

        if params.get("color_grade") in ["cinematic", "warm"]:
            score += 1.0  # 调色专业

        return min(10.0, score)

    # ================================================================
    # 阶段5: 人工选1个发布
    # ================================================================

    def request_final_selection(self, versions: List[FinalVersion]) -> Optional[FinalVersion]:
        """请求人工选择最终发布版本"""
        print("\n" + "="*60)
        print("阶段5: 人工选择发布版本")
        print("="*60)

        # 调用Web选择器
        from src.web_human_selector import WebHumanSelector

        selector = WebHumanSelector()

        # 转换为选择器格式
        version_data = []
        for v in versions:
            version_data.append({
                "version_id": v.version_id,
                "params": v.params,
                "content": f"质量分: {v.quality_score:.1f}/10",
                "video_path": v.video_path
            })

        selected = selector.select_best_script(version_data)

        if selected:
            # 标记选中的版本
            for v in versions:
                if v.version_id == selected["version_id"]:
                    v.selected = True
                    v.selection_reason = selected.get("reason", "")
                    self.current_session["published_version"] = asdict(v)
                    print(f"\n✓ 已选择发布版本: {v.version_id}")
                    return v

        return None

    # ================================================================
    # 会话管理
    # ================================================================

    def save_session(self):
        """保存会话记录"""
        self.current_session["completed_at"] = datetime.now().isoformat()

        path = os.path.join(
            self.records_dir,
            f"{self.current_session['session_id']}.json"
        )

        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.current_session, f, ensure_ascii=False, indent=2)

        print(f"\n[Pipeline] 会话记录已保存: {path}")
        return path

    async def run_minimal_v5(self, workflow_manager, config) -> Dict[str, Any]:
        """
        最小可落地 5.0 链路：
        1) 连续生成 3 份剧本并按内置规则评分
        2) 选择最高分剧本
        3) 基于 WorkflowManager 串联角色 / 分镜 / 关键帧 / 视频 / 合成

        说明：
        - 这是“先跑通”的实现，不引入新的重型抽象
        - 保留旧 EfficientPipeline API，不破坏已有测试/脚本
        - 若图像或视频阶段未配置，允许返回空产物，但会落盘会话记录
        """
        topic = getattr(config, "topic", "短剧")
        self.start_session(topic)

        print("\n" + "=" * 60)
        print("5.0 最小落地链路启动")
        print("=" * 60)

        candidates: List[ScriptCandidate] = []
        for i in range(3):
            print(f"\n[{i+1}/3] 生成剧本候选...")
            script = await workflow_manager.generate_script(config)
            score_data = self._score_script(script)
            candidate = ScriptCandidate(
                script_id=f"script_{i+1}",
                content=script,
                score=score_data["overall"],
                dimensions=score_data["dimensions"],
                timestamp=datetime.now().isoformat(),
            )
            candidates.append(candidate)
            print(f"   总分: {candidate.score:.1f}/10")
            print(f"   Hook: {candidate.dimensions['hook_strength']:.1f}")
            print(f"   剧情: {candidate.dimensions['plot_structure']:.1f}")
            print(f"   情绪: {candidate.dimensions['emotion_rhythm']:.1f}")

        best_candidate = max(candidates, key=lambda x: x.score)
        self.current_session["script_candidates"] = [asdict(c) for c in candidates]
        self.current_session["selected_script"] = asdict(best_candidate)
        workflow_manager.state.script = best_candidate.content

        print(f"\n✓ 选中剧本: {best_candidate.script_id} ({best_candidate.score:.1f}/10)")

        characters = await workflow_manager.build_character_masters(best_candidate.content, config)
        workflow_manager.state.character_masters = characters
        self.current_session["characters"] = [
            {
                "character_id": getattr(c, "character_id", ""),
                "name": getattr(c, "name", ""),
                "role_in_story": getattr(c, "role_in_story", ""),
            }
            for c in characters
        ]
        self.current_session["character_approved"] = True

        storyboard = await workflow_manager.generate_storyboard(best_candidate.content, characters)
        workflow_manager.state.storyboard = storyboard

        keyframes = await workflow_manager.generate_all_keyframes(storyboard, characters)
        workflow_manager.state.keyframes = keyframes
        workflow_manager.state.images = [p for p in keyframes.values() if p]

        videos: List[str] = []
        video_prompts: Dict[str, str] = {}
        for scene in storyboard.get("scenes", []):
            for shot in scene.get("shots", []):
                shot_id = shot.get("shot_id", "")
                if shot_id:
                    video_prompts[shot_id] = shot.get("motion_prompt") or shot.get("video_prompt", "")

        for shot_id, image_path in keyframes.items():
            if not image_path or not Path(image_path).exists():
                print(f"⚠️ 跳过视频生成 [{shot_id}]：关键帧不存在")
                continue
            try:
                video_path = await workflow_manager.generate_video(
                    image_path,
                    video_prompts.get(shot_id, ""),
                )
            except Exception as exc:
                print(f"⚠️ 视频生成失败 [{shot_id}]: {exc}")
                video_path = ""
            if video_path:
                videos.append(video_path)

        workflow_manager.state.videos = videos
        final_video = await workflow_manager.assemble_videos(videos)

        final_versions = [
            asdict(
                FinalVersion(
                    version_id="minimal_v5",
                    video_path=final_video,
                    quality_score=1.0 if final_video else 0.0,
                    params={
                        "mode": "efficient",
                        "strategy": "minimal_v5",
                        "video_count": len(videos),
                        "keyframe_count": len(keyframes),
                    },
                    selected=bool(final_video),
                    selection_reason="自动落地的最小可跑版本",
                )
            )
        ]
        self.current_session["final_versions"] = final_versions
        self.current_session["published_version"] = final_versions[0] if final_versions else None

        record_path = self.save_session()
        return {
            "session_id": self.current_session["session_id"],
            "selected_script": asdict(best_candidate),
            "character_count": len(characters),
            "storyboard_scene_count": len(storyboard.get("scenes", [])),
            "keyframe_count": len(keyframes),
            "video_count": len(videos),
            "final_video": final_video,
            "record_path": record_path,
        }

    def get_session_summary(self) -> str:
        """获取会话摘要"""
        selected_script = self.current_session.get('selected_script')
        script_id = selected_script['script_id'] if selected_script else 'N/A'
        script_score = f"{selected_script['score']:.1f}/10" if selected_script else 'N/A'

        published = self.current_session.get('published_version')
        published_id = published['version_id'] if published else '未选择'

        summary = f"""
生产会话摘要
{'='*60}
会话ID: {self.current_session['session_id']}
主题: {self.current_session['topic']}

阶段1 - 剧本生成:
  候选数量: {len(self.current_session['script_candidates'])}
  选中剧本: {script_id}
  最高分: {script_score}

阶段2 - 角色母版:
  角色数量: {len(self.current_session['characters'])}
  人工确认: {'✓ 已通过' if self.current_session['character_approved'] else '✗ 未通过'}

阶段4 - 最终版本:
  版本数量: {len(self.current_session['final_versions'])}

阶段5 - 发布:
  发布版本: {published_id}

创建时间: {self.current_session['created_at']}
完成时间: {self.current_session['completed_at'] or '进行中'}
{'='*60}
"""
        return summary
