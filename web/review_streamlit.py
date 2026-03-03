#!/usr/bin/env python3
"""Streamlit 审核界面（人在回路）

能力：
1. 加载 storyboard_flow_*.json
2. 网格查看关键帧
3. 修改 prompt 并单帧重绘
4. 保存审核结果
5. 一键发车：按审核后的关键帧生成视频并合成

运行：
  streamlit run web/review_streamlit.py
"""

import asyncio
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.cozex_client import CozexClient  # noqa: E402
from src.jimeng_client import JimengVideoClient  # noqa: E402
from src.video_composer import CompositionConfig, VideoClip, VideoComposer  # noqa: E402


STORYBOARD_DIR = ROOT / "output" / "storyboards"
DEFAULT_SIZE = "1536x2560"


def list_storyboard_files() -> List[Path]:
    STORYBOARD_DIR.mkdir(parents=True, exist_ok=True)
    files = sorted(STORYBOARD_DIR.glob("storyboard_flow_ep*.json"), reverse=True)
    return files


def load_json(path: Path) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data: Dict[str, Any]) -> None:
    tmp = str(path) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def run_async(coro):
    return asyncio.run(coro)


def extract_episode_num(path: Path) -> str:
    m = re.search(r"ep(\d+)", path.name)
    return m.group(1) if m else "00"


def ensure_clients():
    if "cozex_client" not in st.session_state:
        st.session_state.cozex_client = CozexClient()
    if "jimeng_client" not in st.session_state:
        st.session_state.jimeng_client = JimengVideoClient()


def redraw_shot(flow_data: Dict[str, Any], shot_idx: int, size: str) -> Optional[str]:
    ensure_clients()
    shot = flow_data["shots"][shot_idx]
    prompt = shot.get("keyframe_image_prompt", "").strip()
    if not prompt:
        return "Prompt 为空，无法重绘"

    try:
        result = st.session_state.cozex_client.generate_image(prompt=prompt, size=size)
    except Exception as e:
        return f"重绘失败: {e}"

    saved_path = result.get("saved_path")
    if saved_path:
        shot["keyframe_image_path"] = saved_path

    data_items = result.get("data") or []
    if data_items and isinstance(data_items[0], dict):
        image_url = data_items[0].get("url")
        if image_url:
            shot["keyframe_image_url"] = image_url

    return None


def launch_generation(flow_path: Path, flow_data: Dict[str, Any]) -> Optional[str]:
    ensure_clients()
    video_paths: List[str] = []

    for idx, shot in enumerate(flow_data.get("shots", []), start=1):
        # 已有可用视频则跳过
        existing = shot.get("video_path")
        if existing and os.path.exists(existing):
            video_paths.append(existing)
            continue

        image_url = shot.get("keyframe_image_url")
        if not image_url:
            st.warning(f"{shot.get('shot_id', idx)} 缺少 keyframe_image_url，跳过")
            continue

        prompt = shot.get("motion_prompt") or shot.get("video_prompt") or ""
        try:
            result = run_async(
                st.session_state.jimeng_client.image_to_video(
                    image_url=image_url,
                    prompt=prompt,
                    aspect_ratio="9:16",
                )
            )
        except Exception as e:
            st.error(f"{shot.get('shot_id', idx)} 生成视频失败: {e}")
            continue

        video_path = result.get("video_path")
        if video_path:
            shot["video_path"] = video_path
            shot["video_task_id"] = result.get("task_id", "")
            video_paths.append(video_path)

    if not video_paths:
        return None

    output_dir = ROOT / "output" / "review"
    output_dir.mkdir(parents=True, exist_ok=True)
    episode_num = extract_episode_num(flow_path)
    final_path = output_dir / f"episode_{episode_num}_review_final.mp4"

    composer = VideoComposer(
        CompositionConfig(
            output_path=str(final_path),
            resolution="1080x1920",
            fps=30,
        )
    )

    clips = [VideoClip(path=p) for p in video_paths if p and os.path.exists(p)]
    if not clips:
        return None

    return composer.compose(clips)


def main():
    st.set_page_config(page_title="VideoAgent 审核台", layout="wide")
    st.title("VideoAgent 审核界面（Streamlit）")

    files = list_storyboard_files()
    if not files:
        st.warning("未找到分镜文件：output/storyboards/storyboard_flow_ep*.json")
        st.stop()

    options = [str(p) for p in files]
    selected = st.selectbox("选择分镜文件", options)
    flow_path = Path(selected)

    try:
        flow_data = load_json(flow_path)
    except Exception as e:
        st.error(f"读取失败: {e}")
        st.stop()

    if "shots" not in flow_data or not isinstance(flow_data["shots"], list):
        st.error("分镜文件格式不正确，缺少 shots")
        st.stop()

    st.caption(f"共 {len(flow_data['shots'])} 个镜头")

    with st.sidebar:
        st.header("操作")
        cols_per_row = st.slider("每行卡片数", min_value=1, max_value=4, value=2)
        image_size = st.text_input("重绘尺寸", value=DEFAULT_SIZE)

        if st.button("保存审核结果"):
            save_json(flow_path, flow_data)
            st.success(f"已保存：{flow_path}")

        if st.button("一键发车（生成视频并合成）"):
            with st.spinner("正在生成视频与合成，请稍候..."):
                final_path = launch_generation(flow_path, flow_data)
                save_json(flow_path, flow_data)
            if final_path:
                st.success(f"完成：{final_path}")
                st.video(str(final_path))
            else:
                st.error("未生成可合成视频，请检查 keyframe_image_url / API 配置")

    # 网格渲染（按行）
    shots = flow_data["shots"]
    for row_start in range(0, len(shots), cols_per_row):
        row_cols = st.columns(cols_per_row)
        for local_idx in range(cols_per_row):
            idx = row_start + local_idx
            if idx >= len(shots):
                break
            shot = shots[idx]
            with row_cols[local_idx]:
                st.markdown(f"**{shot.get('shot_id', f'shot-{idx+1}')} · {shot.get('shot_type', '')}**")
                image_path = shot.get("keyframe_image_path")
                if image_path and os.path.exists(image_path):
                    st.image(image_path, use_container_width=True)
                else:
                    st.info("暂无关键帧图片")

                key = f"prompt_{idx}"
                default_prompt = shot.get("keyframe_image_prompt", "")
                new_prompt = st.text_area("Image Prompt", value=default_prompt, key=key, height=120)
                if new_prompt != default_prompt:
                    shot["keyframe_image_prompt"] = new_prompt

                if st.button("重绘本帧", key=f"redraw_{idx}"):
                    err = redraw_shot(flow_data, idx, image_size)
                    if err:
                        st.error(err)
                    else:
                        st.success("重绘完成")
                        st.rerun()


if __name__ == "__main__":
    main()
