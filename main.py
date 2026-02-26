#!/usr/bin/env python3
"""
AI Short Drama Automator v2.0
自动化生成AI短剧 - 从剧本到成片全流程
"""

import os
import json
import asyncio
import argparse
from datetime import datetime
from typing import Optional, List
from dataclasses import dataclass, asdict

import yaml

# 核心模块
try:
    from src.script_generator import ScriptGenerator
except ImportError:
    ScriptGenerator = None

try:
    from src.prompt_builder import PromptBuilder
except ImportError:
    PromptBuilder = None

try:
    from src.storyboard_manager import StoryboardManager, Storyboard
except ImportError:
    StoryboardManager = None

try:
    from src.asset_manager import AssetManager, AssetType
except ImportError:
    AssetManager = None

try:
    from src.video_composer import VideoComposer, CompositionConfig, VideoClip, TransitionType
except ImportError:
    VideoComposer = None

try:
    from src.video_assembler import VideoAssembler
except ImportError:
    VideoAssembler = None


def load_config(config_path: str = "config.yaml") -> dict:
    if os.path.exists(config_path):
        with open(config_path, encoding="utf-8") as f:
            return yaml.safe_load(f)
    return {}


def load_api_config(path: str = "config/api_keys.json") -> dict:
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {}


@dataclass
class DramaConfig:
    topic: str
    style: str = "情感"
    episodes: int = 3
    duration_per_episode: int = 60
    language: str = "zh"
    output_dir: str = "output"
    resolution: str = "1080x1920"
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    replicate_api_key: Optional[str] = None


class ShortDramaAutomator:
    """AI短剧自动生成器 v2.0"""

    def __init__(self, drama_config: DramaConfig, app_config: dict = None):
        self.config = drama_config
        self.app_config = app_config or {}
        self.episodes_data = []

        os.makedirs(drama_config.output_dir, exist_ok=True)

        api_config = load_api_config()
        storage_cfg = self.app_config.get("storage", {})
        video_cfg = self.app_config.get("video", {})
        storyboard_cfg = self.app_config.get("storyboard", {})

        # 初始化模块
        self.script_gen = ScriptGenerator(drama_config, api_config) if ScriptGenerator else None
        self.prompt_builder = PromptBuilder(drama_config) if PromptBuilder else None

        self.storyboard_mgr = (
            StoryboardManager(storage_cfg.get("storyboards_dir", "output/storyboards"))
            if StoryboardManager else None
        )
        self.asset_mgr = (
            AssetManager(storage_cfg.get("dir", "data/storage"))
            if AssetManager else None
        )

        transition = TransitionType(video_cfg.get("transition", "fade")) if VideoComposer else None
        self.composer = None
        if VideoComposer:
            comp_cfg = CompositionConfig(
                output_path=os.path.join(drama_config.output_dir, "final.mp4"),
                resolution=drama_config.resolution,
                fps=self.app_config.get("output", {}).get("fps", 30),
                bgm_volume=video_cfg.get("bgm_volume", 0.3),
                voiceover_volume=video_cfg.get("voiceover_volume", 1.0),
            )
            try:
                self.composer = VideoComposer(comp_cfg)
            except RuntimeError as e:
                print(f"⚠️  {e}")

        self._auto_approve = storyboard_cfg.get("auto_approve", False)
        self._scene_duration = storyboard_cfg.get("default_scene_duration", 3.0)

    async def run(self) -> str:
        print(f"\n🎬 AI短剧自动生成器 v2.0")
        print(f"   主题: {self.config.topic} | 风格: {self.config.style} | 集数: {self.config.episodes}")
        print("=" * 60)

        all_boards = []

        for ep in range(1, self.config.episodes + 1):
            print(f"\n📝 第 {ep} 集")

            # 1. 生成剧本
            if self.script_gen:
                script = await self.script_gen.generate_episode(
                    topic=self.config.topic,
                    episode_num=ep,
                    total_episodes=self.config.episodes
                )
            else:
                script = self._placeholder_script(ep)
            print(f"   ✓ 剧本生成完成 ({len(script)} 字)")

            # 2. 生成分镜
            board = None
            if self.storyboard_mgr:
                board = self.storyboard_mgr.generate_from_script(
                    script, episode_num=ep, drama_title=self.config.topic
                )
                if self._auto_approve:
                    self.storyboard_mgr.approve_all(board)
                board_path = self.storyboard_mgr.save(board)
                all_boards.append(board)
                print(f"   ✓ 分镜生成: {len(board.scenes)} 个场景 → {board_path}")
                print(f"   {self.storyboard_mgr.summary(board)}")

            # 3. 生成图片提示词
            if self.prompt_builder:
                prompts = self.prompt_builder.generate_scene_prompts(script)
            else:
                prompts = self._placeholder_prompts(script)
            print(f"   ✓ 图片提示词: {len(prompts)} 个")

            self.episodes_data.append({
                "episode_num": ep,
                "script": script,
                "image_prompts": prompts,
                "storyboard_id": board.storyboard_id if board else None,
            })

        # 4. 保存结果
        output_file = self._save_results()
        print(f"\n💾 结果已保存: {output_file}")

        # 5. 素材统计
        if self.asset_mgr:
            stats = self.asset_mgr.stats()
            print(f"📦 素材库: {stats['total']} 个素材 ({stats['total_size_mb']} MB)")

        print(f"\n✅ 完成! 共 {len(self.episodes_data)} 集")
        return output_file

    def compose_video(self, video_paths: List[str], bgm_path: str = None,
                      voiceover_path: str = None) -> Optional[str]:
        """合成最终视频"""
        if not self.composer:
            print("⚠️  VideoComposer 不可用（FFmpeg 未安装）")
            return None

        if bgm_path:
            self.composer.config.bgm_path = bgm_path
        if voiceover_path:
            self.composer.config.voiceover_path = voiceover_path

        clips = [VideoClip(path=p) for p in video_paths]
        return self.composer.compose(clips)

    def images_to_video(self, image_paths: List[str], duration_each: float = 3.0,
                        output_path: str = None) -> Optional[str]:
        """图片序列转视频"""
        if not self.composer:
            print("⚠️  VideoComposer 不可用")
            return None
        return self.composer.images_to_video(image_paths, duration_each, output_path)

    def _placeholder_script(self, ep: int) -> str:
        return f"""第{ep}集

场景1: [开场]
对话: 主人公醒来，发现自己在一个陌生的房间...

场景2: [发展]
对话: 这时，门突然打开了...

场景3: [高潮]
对话: 原来一切都是命中注定！

场景4: [结尾]
对话: 敬请期待下一集！
"""

    def _placeholder_prompts(self, script: str) -> List[str]:
        scenes = script.split("场景")
        return [
            f"cinematic scene {i}, dramatic lighting, high quality, 8k, vertical 9:16"
            for i in range(1, len(scenes))
        ]

    def _save_results(self) -> str:
        path = os.path.join(
            self.config.output_dir,
            f"drama_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        with open(path, "w", encoding="utf-8") as f:
            json.dump({
                "config": asdict(self.config),
                "episodes": self.episodes_data,
            }, f, ensure_ascii=False, indent=2)
        return path


# ── CLI ──────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="AI Short Drama Automator - 一句话生成完整短剧",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python main.py generate --topic "重生千金复仇记" --style 情感 --episodes 5
  python main.py storyboard --script script.txt --episode 1
  python main.py compose --videos clip1.mp4 clip2.mp4 --bgm music.mp3
  python main.py assets --list
  python main.py assets --import photo.jpg --tags "角色,主角" --category characters
        """
    )
    sub = p.add_subparsers(dest="command")

    # generate
    gen = sub.add_parser("generate", help="生成短剧剧本和分镜")
    gen.add_argument("--topic", required=True, help="短剧主题")
    gen.add_argument("--style", default="情感", choices=["情感", "悬疑", "搞笑", "科幻"], help="风格")
    gen.add_argument("--episodes", type=int, default=3, help="集数")
    gen.add_argument("--output", default="output", help="输出目录")
    gen.add_argument("--config", default="config.yaml", help="配置文件路径")
    gen.add_argument("--auto-approve", action="store_true", help="自动审批所有分镜")

    # storyboard
    sb = sub.add_parser("storyboard", help="从剧本生成分镜")
    sb.add_argument("--script", required=True, help="剧本文件路径")
    sb.add_argument("--episode", type=int, default=1, help="集数")
    sb.add_argument("--title", default="", help="剧名")
    sb.add_argument("--approve-all", action="store_true", help="生成后自动审批")

    # compose
    comp = sub.add_parser("compose", help="合成视频")
    comp.add_argument("--videos", nargs="+", required=True, help="视频片段路径列表")
    comp.add_argument("--bgm", help="背景音乐路径")
    comp.add_argument("--voiceover", help="配音文件路径")
    comp.add_argument("--output", default="output/final.mp4", help="输出路径")
    comp.add_argument("--transition", default="fade",
                      choices=["none", "fade", "dissolve", "slideleft", "slideright", "wipe"])

    # images2video
    i2v = sub.add_parser("images2video", help="图片序列转视频")
    i2v.add_argument("--images", nargs="+", required=True, help="图片路径列表")
    i2v.add_argument("--duration", type=float, default=3.0, help="每张图片时长(秒)")
    i2v.add_argument("--output", default="output/slideshow.mp4", help="输出路径")

    # assets
    ast = sub.add_parser("assets", help="素材库管理")
    ast.add_argument("--list", action="store_true", help="列出所有素材")
    ast.add_argument("--import", dest="import_file", help="导入素材文件")
    ast.add_argument("--tags", default="", help="标签（逗号分隔）")
    ast.add_argument("--category", default="uncategorized", help="分类")
    ast.add_argument("--stats", action="store_true", help="显示素材统计")

    return p


async def cmd_generate(args, app_config: dict):
    app_config.setdefault("storyboard", {})["auto_approve"] = args.auto_approve

    api_config = load_api_config()
    anthropic_key = api_config.get("script", {}).get("custom_opus", {}).get("api_key")

    config = DramaConfig(
        topic=args.topic,
        style=args.style,
        episodes=args.episodes,
        output_dir=args.output,
        anthropic_api_key=anthropic_key,
    )
    automator = ShortDramaAutomator(config, app_config)
    await automator.run()


def cmd_storyboard(args):
    if not StoryboardManager:
        print("❌ StoryboardManager 不可用")
        return
    with open(args.script, encoding="utf-8") as f:
        script = f.read()
    mgr = StoryboardManager()
    board = mgr.generate_from_script(script, episode_num=args.episode, drama_title=args.title)
    if args.approve_all:
        mgr.approve_all(board)
    path = mgr.save(board)
    print(mgr.summary(board))
    print(f"💾 分镜已保存: {path}")


def cmd_compose(args):
    if not VideoComposer:
        print("❌ VideoComposer 不可用")
        return
    cfg = CompositionConfig(
        output_path=args.output,
        bgm_path=args.bgm,
        voiceover_path=args.voiceover,
    )
    composer = VideoComposer(cfg)
    clips = [VideoClip(path=p, transition=TransitionType(args.transition)) for p in args.videos]
    result = composer.compose(clips)
    print(f"🎬 视频已合成: {result}")


def cmd_images2video(args):
    if not VideoComposer:
        print("❌ VideoComposer 不可用")
        return
    cfg = CompositionConfig(output_path=args.output)
    composer = VideoComposer(cfg)
    result = composer.images_to_video(args.images, args.duration, args.output)
    print(f"🎬 幻灯片视频: {result}")


def cmd_assets(args):
    if not AssetManager:
        print("❌ AssetManager 不可用")
        return
    mgr = AssetManager()
    if args.stats:
        print(json.dumps(mgr.stats(), ensure_ascii=False, indent=2))
    elif args.list:
        assets = mgr.list_all()
        if not assets:
            print("素材库为空")
        for a in assets:
            print(f"[{a.asset_id}] {a.asset_type.value:6s} {a.name:30s} tags={a.tags} cat={a.category}")
    elif args.import_file:
        tags = [t.strip() for t in args.tags.split(",") if t.strip()]
        asset = mgr.import_file(args.import_file, tags=tags, category=args.category)
        print(f"✅ 已导入: [{asset.asset_id}] {asset.name}")


def main():
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        # 无参数时运行默认示例
        app_config = load_config()
        config = DramaConfig(topic="重生千金复仇记", style="情感", episodes=3)
        automator = ShortDramaAutomator(config, app_config)
        asyncio.run(automator.run())
        return

    app_config = load_config(getattr(args, "config", "config.yaml"))

    if args.command == "generate":
        asyncio.run(cmd_generate(args, app_config))
    elif args.command == "storyboard":
        cmd_storyboard(args)
    elif args.command == "compose":
        cmd_compose(args)
    elif args.command == "images2video":
        cmd_images2video(args)
    elif args.command == "assets":
        cmd_assets(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
