#!/usr/bin/env python3
"""
AI 短剧自动生成工作流 CLI
SOP 版本：角色优先 + 关键帧驱动

用法:
  python cli.py                          # 完整 7 阶段 SOP 流程
  python cli.py --step script            # 仅生成剧本
  python cli.py --step character         # 仅构建角色母版
  python cli.py --step storyboard        # 仅生成分镜
  python cli.py --step keyframe          # 仅生成关键帧
  python cli.py --step video             # 仅生成视频（需先有关键帧）
  python cli.py --step assemble          # 仅合成视频
  python cli.py --step audit             # 仅运行质量审核
  python cli.py -c my_char.json          # 加载已有角色母版，跳过角色构建
"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

# 添加 src 到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from src.workflow_manager import WorkflowManager, Stage
from src.efficient_pipeline import EfficientPipeline


def build_config(api_config: dict, topic: str, style: str, episodes: int):
    """构建工作流配置对象"""
    return type("Config", (), {
        "topic": topic,
        "style": style,
        "episodes": episodes,
        "duration_per_episode": 60,
        "openai_api_key": (
            api_config.get("script", {}).get("openai", {}).get("api_key")
        ),
        "anthropic_api_key": (
            api_config.get("script", {}).get("custom_opus", {}).get("api_key")
        ),
    })()


def load_api_config() -> dict:
    config_path = Path(__file__).parent / "config" / "api_keys.json"
    if config_path.exists():
        with open(config_path, encoding="utf-8") as f:
            return json.load(f)
    print("⚠️  config/api_keys.json 不存在，使用空配置")
    return {}


def notify(msg: str):
    print(f"\n{'='*55}\n{msg}\n{'='*55}")


def print_efficient_summary(result: dict):
    print("\n⚡ Efficient 5.0 最小链路结果")
    print(f"  会话ID: {result.get('session_id', '')}")
    print(f"  角色数: {result.get('character_count', 0)}")
    print(f"  场景数: {result.get('storyboard_scene_count', 0)}")
    print(f"  关键帧数: {result.get('keyframe_count', 0)}")
    print(f"  视频片段数: {result.get('video_count', 0)}")
    print(f"  最终视频: {result.get('final_video', '') or '未产出'}")
    print(f"  记录文件: {result.get('record_path', '')}")


async def run_step_script(manager: WorkflowManager, config):
    """阶段 1: 仅生成剧本"""
    notify("[1/7] 正在生成剧本...")
    script = await manager.generate_script(config)
    manager.state.script = script
    print("\n📝 剧本生成完成（前 500 字）：")
    print(script[:500] + "..." if len(script) > 500 else script)
    return script


async def run_step_character(manager: WorkflowManager, config, character_file: str = ""):
    """阶段 2: 构建角色母版（或从文件加载）"""
    if character_file and Path(character_file).exists():
        notify(f"[2/7] 加载已有角色母版: {character_file}")
        from src.character_master import CharacterMaster
        master = CharacterMaster.load_from_json(character_file)
        manager.state.character_masters = [master]
        print(f"✅ 角色母版已加载: {master.name}")
    else:
        notify("[2/7] 正在构建角色母版...")
        script = manager.state.script or await run_step_script(manager, config)
        masters = await manager.build_character_masters(script, config)
        manager.state.character_masters = masters
        for m in masters:
            print(f"  👤 {m.name} ({m.character_id}) — {m.to_anchor_fragment()[:80]}...")
    return manager.state.character_masters


async def run_step_storyboard(manager: WorkflowManager, config):
    """阶段 3: 生成分镜"""
    notify("[3/7] 正在生成分镜（Film Director Agent）...")
    if not manager.state.script:
        await run_step_script(manager, config)
    if not manager.state.character_masters:
        await run_step_character(manager, config)
    storyboard = await manager.generate_storyboard(
        manager.state.script, manager.state.character_masters
    )
    manager.state.storyboard = storyboard
    scenes = storyboard.get("scenes", [])
    shots = sum(len(s.get("shots", [])) for s in scenes)
    print(f"✅ 分镜完成: {len(scenes)} 个场景，{shots} 个镜头")
    return storyboard


async def run_step_keyframe(manager: WorkflowManager, config):
    """阶段 4: 生成关键帧"""
    notify("[4/7] 正在生成关键帧...")
    if not manager.state.storyboard:
        await run_step_storyboard(manager, config)
    keyframes = await manager.generate_all_keyframes(
        manager.state.storyboard, manager.state.character_masters
    )
    manager.state.keyframes = keyframes
    manager.state.images = list(keyframes.values())
    ok = sum(1 for v in keyframes.values() if v)
    print(f"✅ 关键帧生成完成: {ok}/{len(keyframes)} 张成功")
    return keyframes


async def run_step_video(manager: WorkflowManager):
    """阶段 5: 基于关键帧生成视频（i2v 模式）"""
    notify("[5/7] 正在基于关键帧生成视频（i2v）...")
    if not manager.state.keyframes:
        print("❌ 请先运行 --step keyframe")
        return []
    videos = []
    for shot_id, img_path in manager.state.keyframes.items():
        try:
            video = await manager.generate_video(img_path)
            videos.append(video)
            print(f"  🎬 [{shot_id}] → {Path(video).name if video else '空'}")
        except ValueError as e:
            print(f"  ⛔ [{shot_id}] i2v 强制检查失败: {e}")
        except Exception as e:
            print(f"  ⚠️ [{shot_id}] 视频生成失败: {e}")
    manager.state.videos = videos
    return videos


async def run_step_assemble(manager: WorkflowManager):
    """阶段 6: 合成视频"""
    notify("[6/7] 正在合成最终视频...")
    final = await manager.assemble_videos(manager.state.videos)
    print(f"✅ 最终视频: {final}")
    return final


async def run_step_audit(manager: WorkflowManager):
    """阶段 7: 质量审核"""
    notify("[7/7] 正在进行质量审核...")
    if not manager.state.storyboard:
        print("⚠️  无分镜数据，跳过审核")
        return None
    report = await manager.run_sop_quality_audit(
        manager.state.storyboard, manager.state.character_masters
    )
    print(report.summary_text())
    return report


async def main():
    parser = argparse.ArgumentParser(
        description="AI 短剧 SOP 工作流 CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--step", "-s",
        choices=["all", "script", "character", "storyboard", "keyframe", "video", "assemble", "audit"],
        default="all",
        help="执行指定阶段（默认: all — 全流程）",
    )
    parser.add_argument(
        "--mode",
        choices=["sop", "efficient"],
        default="sop",
        help="执行模式：sop=原 7 阶段流程；efficient=5.0 最小落地链路",
    )
    parser.add_argument("--topic", "-t", default="重生千金复仇记", help="剧本主题")
    parser.add_argument("--style", default="情感", help="剧本风格")
    parser.add_argument("--episodes", "-e", type=int, default=3, help="集数")
    parser.add_argument(
        "--character-file", "-c",
        default="",
        help="已有角色母版 JSON 路径（跳过角色构建阶段）",
    )
    args = parser.parse_args()

    api_config = load_api_config()
    config = build_config(api_config, args.topic, args.style, args.episodes)
    manager = WorkflowManager(notify_callback=notify)

    notify(f"🚀 AI 短剧工作流  |  主题: {args.topic}  |  step: {args.step}  |  mode: {args.mode}")

    if args.mode == "efficient":
        if args.step != "all":
            raise SystemExit("efficient 模式当前只支持 --step all；先把最小闭环跑通，别上来就拆碎。")
        pipeline = EfficientPipeline()
        result = await pipeline.run_minimal_v5(manager, config)
        print_efficient_summary(result)
        return

    if args.step == "all":
        final = await manager.run_workflow(config)
        notify(f"🎉 完成！最终视频: {final}")

    elif args.step == "script":
        await run_step_script(manager, config)

    elif args.step == "character":
        await run_step_character(manager, config, args.character_file)

    elif args.step == "storyboard":
        await run_step_storyboard(manager, config)

    elif args.step == "keyframe":
        await run_step_keyframe(manager, config)

    elif args.step == "video":
        await run_step_video(manager)

    elif args.step == "assemble":
        await run_step_assemble(manager)

    elif args.step == "audit":
        await run_step_audit(manager)


if __name__ == "__main__":
    asyncio.run(main())
