#!/usr/bin/env python3
"""
Storyboard Flow - 两步分镜生成流程管理器

流程：
  剧本 → 分镜拆分 → STEP1: Keyframe Image Prompt → 生成关键帧图片
                   → STEP2: Video Prompt → 视频生成
"""

import json
import os
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any, Callable

try:
    from .film_director_agent import FilmDirectorAgent
except ImportError:
    from film_director_agent import FilmDirectorAgent


@dataclass
class StoryboardShot:
    """单个分镜的完整数据"""
    shot_id: str
    scene_id: str
    scene_location: str
    shot_type: str
    description: str
    # STEP 1
    keyframe_image_prompt: str
    keyframe_image_path: Optional[str] = None   # 生成后填入
    keyframe_image_url: Optional[str] = None
    # STEP 2
    video_prompt: str = ""
    video_path: Optional[str] = None            # 生成后填入
    video_task_id: Optional[str] = None
    continuity_from_shot_id: str = ""
    continuity_state: Dict[str, str] = field(default_factory=dict)


@dataclass
class StoryboardFlow:
    """完整分镜流程状态"""
    shots: List[StoryboardShot] = field(default_factory=list)
    director_intent: Dict[str, Any] = field(default_factory=dict)
    characters: Dict[str, Any] = field(default_factory=dict)


class StoryboardFlowManager:
    """
    两步分镜流程管理器

    用法：
        mgr = StoryboardFlowManager(script)
        flow = mgr.build()                        # 生成所有分镜 + 两步 prompt
        mgr.generate_keyframes(flow, image_fn)    # STEP1: 批量生成关键帧图片
        mgr.generate_videos(flow, video_fn)       # STEP2: 批量生成视频
    """

    def __init__(self, script: str, use_gemini: bool = False):
        self.script = script
        self.use_gemini = use_gemini

    def build(self) -> StoryboardFlow:
        """解析剧本，生成所有分镜及两步 prompt"""
        agent = FilmDirectorAgent(self.script)
        raw = agent.run(use_gemini=self.use_gemini)

        flow = StoryboardFlow(
            director_intent=raw.get("director_intent", {}),
            characters=raw.get("characters", {}),
        )

        for item in raw.get("film_storyboard", []):
            shot = StoryboardShot(
                shot_id=item["shot_id"],
                scene_id=item["scene_id"],
                scene_location=item["scene_location"],
                shot_type=item["shot_type"],
                description=item["description"],
                keyframe_image_prompt=item["keyframe_image_prompt"],
                keyframe_image_path=item.get("keyframe_image_path"),
                keyframe_image_url=item.get("keyframe_image_url"),
                video_prompt=item["video_prompt"],
                video_path=item.get("video_path"),
                video_task_id=item.get("video_task_id"),
                continuity_from_shot_id=item.get("continuity_from_shot_id", ""),
                continuity_state=item.get("continuity_state", {}),
            )
            flow.shots.append(shot)

        return flow

    def generate_keyframes(
        self,
        flow: StoryboardFlow,
        image_fn: Callable[[str, str], str],
        output_dir: str = "output/keyframes",
    ) -> None:
        """
        STEP 1: 为每个分镜生成关键帧图片

        Args:
            flow: StoryboardFlow 对象
            image_fn: fn(shot_id, keyframe_image_prompt) -> image_path
            output_dir: 图片输出目录
        """
        os.makedirs(output_dir, exist_ok=True)
        for shot in flow.shots:
            print(f"[STEP1] Generating keyframe: {shot.shot_id}")
            print(f"  Prompt: {shot.keyframe_image_prompt}")
            try:
                path = image_fn(shot.shot_id, shot.keyframe_image_prompt)
                shot.keyframe_image_path = path
                print(f"  → {path}")
            except Exception as e:
                print(f"  ✗ Failed: {e}")

    def generate_videos(
        self,
        flow: StoryboardFlow,
        video_fn: Callable[[str, str, str], str],
        output_dir: str = "output/videos",
    ) -> None:
        """
        STEP 2: 使用关键帧图片 + video_prompt 生成视频

        Args:
            flow: StoryboardFlow 对象
            video_fn: fn(shot_id, keyframe_image_path, video_prompt) -> video_path
            output_dir: 视频输出目录
        """
        os.makedirs(output_dir, exist_ok=True)
        for shot in flow.shots:
            if not shot.keyframe_image_path:
                print(f"[STEP2] Skip {shot.shot_id}: no keyframe image")
                continue
            print(f"[STEP2] Generating video: {shot.shot_id}")
            print(f"  Image: {shot.keyframe_image_path}")
            print(f"  Prompt: {shot.video_prompt}")
            try:
                path = video_fn(shot.shot_id, shot.keyframe_image_path, shot.video_prompt)
                shot.video_path = path
                print(f"  → {path}")
            except Exception as e:
                print(f"  ✗ Failed: {e}")

    def to_json(self, flow: StoryboardFlow) -> str:
        return json.dumps(asdict(flow), ensure_ascii=False, indent=2)

    def save(self, flow: StoryboardFlow, path: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.to_json(flow))
        print(f"Saved: {path}")


# ---------------------------------------------------------------------------
# CLI / quick test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    test_script = """
场景1: [公司大厅]
保安: 哎，站住！你要去哪？
林晚: 我来面试。
保安: 没有预约不让进。

场景2: [会议室]
林晚: 这笔并购案的问题在于股权结构，三个月内必然崩盘。
陈总: （震惊）你怎么知道？
"""

    mgr = StoryboardFlowManager(test_script, use_gemini=False)
    flow = mgr.build()

    print(f"\n=== 分镜总数: {len(flow.shots)} ===\n")
    for shot in flow.shots:
        print(f"[{shot.shot_id}] {shot.shot_type} @ {shot.scene_location}")
        print(f"  STEP1 Image : {shot.keyframe_image_prompt}")
        print(f"  STEP2 Video : {shot.video_prompt}")
        print()

    # 模拟 STEP1 + STEP2（不实际调用 API）
    def mock_image_fn(shot_id: str, prompt: str) -> str:
        return f"output/keyframes/{shot_id}.png"

    def mock_video_fn(shot_id: str, image_path: str, prompt: str) -> str:
        return f"output/videos/{shot_id}.mp4"

    mgr.generate_keyframes(flow, mock_image_fn)
    mgr.generate_videos(flow, mock_video_fn)

    out = "output/storyboard_flow_test.json"
    os.makedirs("output", exist_ok=True)
    mgr.save(flow, out)
