#!/usr/bin/env python3
"""
分阶段审核界面（人在回路）

审核阶段：
1. 剧本审核 - 审核剧本内容
2. 分镜审核 - 审核分镜结构
3. 关键帧审核 - 审核生成的图片
4. 视频审核 - 审核生成的视频
5. 成片审核 - 审核最终成品

每个阶段都可以：
- 通过 → 进入下一阶段
- 打回 → 填写修改意见，返回重新生成

运行：
  streamlit run web/review_streamlit.py
"""

import asyncio
import json
import os
import re
import sys
import glob
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import streamlit as st

# 配置页面
st.set_page_config(
    page_title="AI短剧审核中心", 
    layout="wide",
    page_icon="🎬"
)

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# 尝试导入（不阻塞）
try:
    from src.cozex_client import CozexClient
    from src.jimeng_client import JimengVideoClient
    from src.video_composer import CompositionConfig, VideoClip, VideoComposer
    CLIENTS_AVAILABLE = True
except ImportError:
    CLIENTS_AVAILABLE = False


# ==================== 路径配置 ====================
OUTPUT_DIR = ROOT / "output"
STORYBOARD_DIR = OUTPUT_DIR / "storyboards"
AUDIO_DIR = OUTPUT_DIR / "audio"
SUBTITLE_DIR = OUTPUT_DIR / "subtitles"
FINAL_DIR = OUTPUT_DIR / "final"

for d in [OUTPUT_DIR, STORYBOARD_DIR, AUDIO_DIR, SUBTITLE_DIR, FINAL_DIR]:
    d.mkdir(parents=True, exist_ok=True)


# ==================== 审核阶段定义 ====================
class ReviewStage:
    """审核阶段"""
    SCRIPT = "script"           # 剧本
    STORYBOARD = "storyboard"   # 分镜
    KEYFRAME = "keyframe"       # 关键帧
    VIDEO = "video"             # 视频
    FINAL = "final"             # 成片
    
    @classmethod
    def all(cls):
        return [cls.SCRIPT, cls.STORYBOARD, cls.KEYFRAME, cls.VIDEO, cls.FINAL]
    
    @classmethod
    def label(cls, stage):
        labels = {
            cls.SCRIPT: "📝 剧本审核",
            cls.STORYBOARD: "🎬 分镜审核",
            cls.KEYFRAME: "🖼️ 关键帧审核",
            cls.VIDEO: "🎥 视频审核",
            cls.FINAL: "✅ 成片审核",
        }
        return labels.get(stage, stage)
    
    @classmethod
    def next(cls, stage):
        order = cls.all()
        idx = order.index(stage) if stage in order else -1
        return order[idx + 1] if idx + 1 < len(order) else None


# ==================== 状态管理 ====================
def get_review_status(project_id: str) -> Dict:
    """获取项目审核状态"""
    status_file = OUTPUT_DIR / f"review_{project_id}.json"
    if status_file.exists():
        with open(status_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "project_id": project_id,
        "current_stage": ReviewStage.SCRIPT,
        "stages": {
            ReviewStage.SCRIPT: {"status": "pending", "data": {}, "feedback": ""},
            ReviewStage.STORYBOARD: {"status": "pending", "data": {}, "feedback": ""},
            ReviewStage.KEYFRAME: {"status": "pending", "data": {}, "feedback": ""},
            ReviewStage.VIDEO: {"status": "pending", "data": {}, "feedback": ""},
            ReviewStage.FINAL: {"status": "pending", "data": {}, "feedback": ""},
        },
        "created_at": datetime.now().isoformat(),
    }


def save_review_status(status: Dict):
    """保存审核状态"""
    status_file = OUTPUT_DIR / f"review_{status['project_id']}.json"
    with open(status_file, "w", encoding="utf-8") as f:
        json.dump(status, f, ensure_ascii=False, indent=2)


# ==================== 项目列表 ====================
def list_projects() -> List[Dict]:
    """列出所有项目"""
    projects = []
    
    # 从 drama_*.json 读取
    for f in sorted(glob.glob(str(OUTPUT_DIR / "drama_*.json")), reverse=True):
        try:
            with open(f, encoding="utf-8") as fp:
                data = json.load(fp)
            cfg = data.get("config", {})
            project_id = Path(f).stem.replace("drama_", "")
            projects.append({
                "id": project_id,
                "topic": cfg.get("topic", "未知"),
                "style": cfg.get("style", "-"),
                "episodes": cfg.get("episodes", 0),
                "created": os.path.getmtime(f),
            })
        except:
            pass
    
    return projects


def list_episodes(project_id: str) -> List[Dict]:
    """列出项目下的剧集"""
    episodes = []
    
    # 从 storyboard_flow_*.json 读取
    pattern = STORYBOARD_DIR / f"storyboard_flow_ep*.json"
    for f in sorted(glob.glob(str(pattern)), reverse=True):
        try:
            ep_num = int(re.search(r"ep(\d+)", f.name).group(1))
            episodes.append({
                "episode": ep_num,
                "storyboard_file": str(f),
            })
        except:
            pass
    
    return episodes


# ==================== 阶段审核UI ====================

def render_script_review(project_id: str, status: Dict):
    """剧本审核"""
    st.subheader("📝 剧本审核")
    
    # 加载剧本
    drama_file = OUTPUT_DIR / f"drama_{project_id}.json"
    if not drama_file.exists():
        st.warning("未找到剧本文件")
        return
    
    with open(drama_file, encoding="utf-8") as f:
        drama_data = json.load(f)
    
    # 显示剧本内容
    episodes = drama_data.get("episodes", [])
    for ep in episodes:
        with st.expander(f"第 {ep.get('episode_num', '?')} 集", expanded=True):
            script = ep.get("script", "无剧本")
            st.text_area("剧本内容", value=script, height=300, key=f"script_{ep.get('episode_num')}")
            
            # 审核意见
            stage_data = status["stages"].get(ReviewStage.SCRIPT, {})
            feedback_key = f"feedback_script_{ep.get('episode_num')}"
            feedback = st.text_area(
                "修改意见（可选）", 
                value=stage_data.get("feedback", ""),
                placeholder="如有修改意见请填写...",
                key=feedback_key
            )
    
    return feedback if 'feedback' in locals() else ""


def render_storyboard_review(project_id: str, episode: int, status: Dict):
    """分镜审核"""
    st.subheader("🎬 分镜审核")
    
    storyboard_file = STORYBOARD_DIR / f"storyboard_flow_ep{episode:02d}.json"
    if not storyboard_file.exists():
        st.warning("未找到分镜文件")
        return
    
    with open(storyboard_file, encoding="utf-8") as f:
        storyboard = json.load(f)
    
    shots = storyboard.get("shots", [])
    st.caption(f"共 {len(shots)} 个镜头")
    
    # 显示分镜列表
    for i, shot in enumerate(shots):
        with st.expander(f"镜头 {i+1}: {shot.get('shot_id', '')} - {shot.get('shot_type', '')}"):
            col1, col2 = st.columns(2)
            with col1:
                st.text_area("画面描述", value=shot.get("description", ""), height=80, key=f"sb_desc_{episode}_{i}")
            with col2:
                st.text_area("关键帧 Prompt", value=shot.get("keyframe_image_prompt", ""), height=80, key=f"sb_prompt_{episode}_{i}")
            
            # 运动提示词
            st.text_area("运动提示词", value=shot.get("motion_prompt", ""), height=60, key=f"sb_motion_{episode}_{i}")
            
            # 连续性状态
            continuity = shot.get("continuity_state", {})
            if continuity:
                with st.expander("连续性状态"):
                    for k, v in continuity.items():
                        st.text_input(k, value=v, disabled=True)
    
    # 审核意见
    stage_data = status["stages"].get(ReviewStage.STORYBOARD, {})
    feedback = st.text_area(
        "修改意见（可选）", 
        value=stage_data.get("feedback", ""),
        placeholder="如有修改意见请填写...",
        key=f"feedback_storyboard_{episode}"
    )
    
    return feedback


def render_keyframe_review(project_id: str, episode: int, status: Dict):
    """关键帧审核"""
    st.subheader("🖼️ 关键帧审核")
    
    storyboard_file = STORYBOARD_DIR / f"storyboard_flow_ep{episode:02d}.json"
    if not storyboard_file.exists():
        st.warning("未找到分镜文件")
        return
    
    with open(storyboard_file, encoding="utf-8") as f:
        storyboard = json.load(f)
    
    shots = storyboard.get("shots", [])
    st.caption(f"共 {len(shots)} 个镜头")
    
    # 网格显示
    cols_per_row = st.slider("每行显示", 1, 4, 2)
    
    # 重新排列
    rows = [shots[i:i+cols_per_row] for i in range(0, len(shots), cols_per_row)]
    
    feedback_parts = []
    
    for row in rows:
        cols = st.columns(cols_per_row)
        for col, shot in zip(cols, row):
            with col:
                shot_id = shot.get("shot_id", "")
                shot_type = shot.get("shot_type", "")
                
                # 关键帧图片
                img_path = shot.get("keyframe_image_path", "")
                img_url = shot.get("keyframe_image_url", "")
                
                st.markdown(f"**{shot_id}** ({shot_type})")
                
                if img_path and os.path.exists(img_path):
                    st.image(img_path, use_container_width=True)
                elif img_url:
                    st.image(img_url, use_container_width=True)
                else:
                    st.info("暂无图片")
                
                # Prompt 显示/编辑
                prompt = shot.get("keyframe_image_prompt", "")
                new_prompt = st.text_area(
                    "Image Prompt", 
                    value=prompt, 
                    height=100,
                    key=f"kf_prompt_{episode}_{shot_id}"
                )
                
                # 标记是否需要重绘
                if new_prompt != prompt:
                    st.warning("⚠️ Prompt 已修改，需要重新生成")
                    feedback_parts.append(f"{shot_id} 需要重新生成")
                
                # 质量评价
                quality = st.selectbox(
                    "质量评价",
                    ["待评价", "✅ 优秀", "👍 良好", "👌 一般", "❌ 需重绘"],
                    key=f"kf_quality_{episode}_{shot_id}"
                )
    
    # 审核意见
    stage_data = status["stages"].get(ReviewStage.KEYFRAME, {})
    feedback = st.text_area(
        "修改意见", 
        value=stage_data.get("feedback", ""),
        placeholder="如有修改意见请填写...",
        key=f"feedback_keyframe_{episode}"
    )
    
    return feedback


def render_video_review(project_id: str, episode: int, status: Dict):
    """视频审核"""
    st.subheader("🎥 视频审核")
    
    storyboard_file = STORYBOARD_DIR / f"storyboard_flow_ep{episode:02d}.json"
    if not storyboard_file.exists():
        st.warning("未找到分镜文件")
        return
    
    with open(storyboard_file, encoding="utf-8") as f:
        storyboard = json.load(f)
    
    shots = storyboard.get("shots", [])
    
    # 查找已有视频
    videos = []
    for shot in shots:
        video_path = shot.get("video_path", "")
        if video_path and os.path.exists(video_path):
            videos.append({
                "shot_id": shot.get("shot_id"),
                "path": video_path,
                "method": shot.get("video_method", "unknown"),
                "quality": shot.get("video_quality_score", 0),
            })
    
    st.caption(f"共 {len(videos)} 个视频片段")
    
    # 显示视频
    for video in videos:
        with st.expander(f"视频: {video['shot_id']} ({video['method']})"):
            st.video(video["path"])
            st.caption(f"质量分数: {video['quality']:.2f}")
            
            # 质量评价
            quality = st.selectbox(
                "质量评价",
                ["待评价", "✅ 优秀", "👍 良好", "👌 一般", "❌ 需重绘"],
                key=f"vid_quality_{episode}_{video['shot_id']}"
            )
    
    # ==================== 智能剪辑功能 ====================
    st.markdown("---")
    st.markdown("### ✂️ 智能剪辑分析")
    
    # 选择要分析的视频
    all_videos = []
    for shot in shots:
        path = shot.get("video_path", "")
        if path and os.path.exists(path):
            all_videos.append((shot.get("shot_id"), path))
    
    if not all_videos:
        st.info("暂无视频可供分析")
    else:
        # 视频选择
        video_options = [f"{sid}: {os.path.basename(p)}" for sid, p in all_videos]
        selected_video_idx = st.selectbox("选择视频进行剪辑分析", range(len(video_options)), format_func=lambda x: video_options[x])
        selected_shot_id, selected_video_path = all_videos[selected_video_idx]
        
        # 分析按钮
        col1, col2 = st.columns([1, 3])
        
        with col1:
            if st.button("🔍 分析剪辑点", type="primary"):
                with st.spinner("分析中..."):
                    # 导入智能剪辑模块
                    try:
                        import sys
                        sys.path.insert(0, str(ROOT))
                        from src.smart_video_clipper import SmartVideoClipper
                        
                        clipper = SmartVideoClipper(output_dir=str(OUTPUT_DIR / "clips"))
                        
                        # 同步转异步
                        import asyncio
                        result = asyncio.run(clipper.analyze_video(selected_video_path))
                        
                        # 保存分析结果
                        analysis_file = OUTPUT_DIR / "clips" / f"analysis_{episode}_{selected_shot_id}.json"
                        with open(analysis_file, "w", encoding="utf-8") as f:
                            json.dump({
                                "video_path": result.video_path,
                                "duration": result.duration,
                                "resolution": result.resolution,
                                "fps": result.fps,
                                "scenes": [
                                    {
                                        "start": s.start_time,
                                        "end": s.end_time,
                                        "duration": s.duration,
                                        "type": s.scene_type,
                                        "importance": s.importance
                                    } for s in result.scenes
                                ],
                                "edit_points": [
                                    {
                                        "time": ep.time,
                                        "type": ep.type,
                                        "reason": ep.reason
                                    } for ep in result.edit_points
                                ],
                                "summary": result.summary
                            }, f, ensure_ascii=False, indent=2)
                        
                        st.session_state["clip_analysis"] = result
                        st.success("分析完成！")
                        
                    except Exception as e:
                        st.error(f"分析失败: {e}")
        
        # 显示分析结果
        if "clip_analysis" in st.session_state:
            result = st.session_state["clip_analysis"]
            
            with col2:
                st.info(f"⏱️ 时长: {result.duration:.1f}s | 📐 {result.resolution} | 🎬 {result.fps}fps")
            
            # 场景列表
            if result.scenes:
                st.markdown("#### 🎬 场景片段")
                for i, scene in enumerate(result.scenes):
                    col1, col2, col3 = st.columns([1, 2, 1])
                    with col1:
                        st.caption(f"场景 {i+1}")
                    with col2:
                        st.caption(f"{scene.start_time:.1f}s → {scene.end_time:.1f}s ({scene.duration:.1f}s)")
                    with col3:
                        st.caption(f"类型: {scene.scene_type}")
            
            # 剪辑点
            if result.edit_points:
                st.markdown("#### ✂️ 剪辑点")
                for ep in result.edit_points:
                    icon = {"cut": "✂️", "dissolve": "🌫️", "fade": "🔗"}.get(ep.type, "📍")
                    st.markdown(f"- **{icon} {ep.time:.2f}s** - {ep.type} ({ep.reason})")
            
            # 建议
            if result.summary:
                st.success(f"💡 {result.summary}")
            
            # 导出 EDL
            try:
                from src.smart_video_clipper import SmartVideoClipper
                clipper = SmartVideoClipper(output_dir=str(OUTPUT_DIR / "clips"))
                edl_path = clipper.export_edl(result.edit_points, str(OUTPUT_DIR / "clips" / f"edit_{episode}.edl"))
                st.download_button("📥 导出 EDL", open(edl_path, "rb"), file_name=f"edit_{episode}.edl")
            except:
                pass
    
    # 合成视频
    composed_files = list(FINAL_DIR.glob(f"episode_{episode:02d}*.mp4"))
    if composed_files:
        st.markdown("---")
        st.markdown("### 合成视频")
        for f in composed_files:
            st.video(str(f))
    
    # 审核意见
    stage_data = status["stages"].get(ReviewStage.VIDEO, {})
    feedback = st.text_area(
        "修改意见", 
        value=stage_data.get("feedback", ""),
        placeholder="如有修改意见请填写...",
        key=f"feedback_video_{episode}"
    )
    
    return feedback


def render_final_review(project_id: str, episode: int, status: Dict):
    """成片审核"""
    st.subheader("✅ 成片审核")
    
    # 查找最终视频
    final_files = list(FINAL_DIR.glob(f"episode_{episode:02d}*.mp4"))
    
    if not final_files:
        # 也检查 output 目录
        final_files = list(OUTPUT_DIR.glob(f"episode_{episode:02d}*.mp4"))
    
    if not final_files:
        st.warning("未找到最终视频")
        return
    
    # 显示最终视频
    for f in final_files:
        st.video(str(f))
        
        # 文件信息
        size_mb = os.path.getsize(f) / 1024 / 1024
        st.caption(f"文件大小: {size_mb:.1f} MB")
    
    # 配音
    audio_files = list(AUDIO_DIR.glob(f"ep{episode:02d}*voiceover*.mp3"))
    if audio_files:
        st.markdown("### 🎤 配音")
        for audio in audio_files:
            st.audio(str(audio))
    
    # 字幕
    subtitle_files = list(SUBTITLE_DIR.glob(f"ep{episode:02d}*.srt"))
    if subtitle_files:
        st.markdown("### 📝 字幕")
        for sub in subtitle_files:
            with open(sub, encoding="utf-8") as f:
                content = f.read()
            st.text_area("字幕内容", value=content, height=200, disabled=True)
    
    # 审核意见
    stage_data = status["stages"].get(ReviewStage.FINAL, {})
    feedback = st.text_area(
        "修改意见", 
        value=stage_data.get("feedback", ""),
        placeholder="如有修改意见请填写...",
        key=f"feedback_final_{episode}"
    )
    
    return feedback


# ==================== 主界面 ====================
def main():
    st.title("🎬 AI短剧审核中心")
    st.markdown("---")
    
    # 侧边栏：项目选择
    with st.sidebar:
        st.header("项目选择")
        
        projects = list_projects()
        if not projects:
            st.warning("暂无项目，请先生成短剧")
            return
        
        project_options = [f"{p['topic']} ({p['episodes']}集)" for p in projects]
        selected_idx = st.selectbox("选择项目", range(len(project_options)), format_func=lambda x: project_options[x])
        
        selected_project = projects[selected_idx]
        project_id = selected_project["id"]
        
        st.divider()
        
        # 剧集选择
        episodes = list_episodes(project_id)
        if not episodes:
            st.warning("暂无剧集")
            return
        
        episode_options = [f"第 {ep['episode']} 集" for ep in episodes]
        ep_idx = st.selectbox("选择剧集", range(len(episode_options)), format_func=lambda x: episode_options[x])
        selected_episode = episodes[ep_idx]["episode"]
        
        st.divider()
        
        # 审核状态
        st.header("审核状态")
        status = get_review_status(project_id)
        
        # 显示各阶段状态
        for stage in ReviewStage.all():
            stage_info = status["stages"].get(stage, {})
            stage_status = stage_info.get("status", "pending")
            label = ReviewStage.label(stage)
            
            if stage_status == "approved":
                st.success(f"✅ {label}")
            elif stage_status == "rejected":
                st.error(f"❌ {label}")
            elif stage_status == "in_progress":
                st.warning(f"🔄 {label}")
            else:
                st.info(f"⏳ {label}")
        
        # 当前阶段
        current = status.get("current_stage", ReviewStage.SCRIPT)
        st.divider()
        st.markdown(f"**当前阶段:** {ReviewStage.label(current)}")
    
    # 主内容区
    st.header(f"审核: {selected_project['topic']} - 第 {selected_episode} 集")
    
    # 阶段选择器
    tab_names = [ReviewStage.label(s) for s in ReviewStage.all()]
    tabs = st.tabs(tab_names)
    
    # 当前阶段
    current_stage = status.get("current_stage", ReviewStage.SCRIPT)
    current_idx = ReviewStage.all().index(current_stage) if current_stage in ReviewStage.all() else 0
    
    # 渲染各阶段
    for i, (tab, stage) in enumerate(zip(tabs, ReviewStage.all())):
        with tab:
            # 根据阶段渲染不同内容
            if stage == ReviewStage.SCRIPT:
                feedback = render_script_review(project_id, status)
            elif stage == ReviewStage.STORYBOARD:
                feedback = render_storyboard_review(project_id, selected_episode, status)
            elif stage == ReviewStage.KEYFRAME:
                feedback = render_keyframe_review(project_id, selected_episode, status)
            elif stage == ReviewStage.VIDEO:
                feedback = render_video_review(project_id, selected_episode, status)
            elif stage == ReviewStage.FINAL:
                feedback = render_final_review(project_id, selected_episode, status)
    
    st.markdown("---")
    
    # 审核操作区
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        st.info("💡 选择阶段后，点击下方按钮进行审核")
    
    with col2:
        if st.button("❌ 打回修改", type="secondary", use_container_width=True):
            # 保存反馈
            stage_data = status["stages"].get(current_stage, {})
            stage_data["status"] = "rejected"
            stage_data["feedback"] = feedback if 'feedback' in locals() else ""
            stage_data["rejected_at"] = datetime.now().isoformat()
            status["stages"][current_stage] = stage_data
            
            # 更新状态文件（供主流程读取）
            review_status_file = STORYBOARD_DIR / f"review_status_ep{selected_episode:02d}.json"
            with open(review_status_file, "w", encoding="utf-8") as f:
                json.dump({
                    "status": "rejected",
                    "stage": current_stage,
                    "feedback": stage_data["feedback"],
                    "rejected_at": datetime.now().isoformat()
                }, f, ensure_ascii=False, indent=2)
            
            save_review_status(status)
            st.warning(f"已打回修改，请填写反馈意见")
            st.rerun()
    
    with col3:
        if st.button("✅ 通过审核", type="primary", use_container_width=True):
            # 保存状态
            stage_data = status["stages"].get(current_stage, {})
            stage_data["status"] = "approved"
            stage_data["approved_at"] = datetime.now().isoformat()
            status["stages"][current_stage] = stage_data
            
            # 推进到下一阶段
            next_stage = ReviewStage.next(current_stage)
            if next_stage:
                status["current_stage"] = next_stage
                status["stages"][next_stage]["status"] = "in_progress"
            
            # 更新状态文件（供主流程读取）
            review_status_file = STORYBOARD_DIR / f"review_status_ep{selected_episode:02d}.json"
            with open(review_status_file, "w", encoding="utf-8") as f:
                json.dump({
                    "status": "approved",
                    "stage": current_stage,
                    "approved_at": datetime.now().isoformat()
                }, f, ensure_ascii=False, indent=2)
            
            save_review_status(status)
            st.success(f"已通过审核，进入下一阶段")
            st.rerun()


if __name__ == "__main__":
    main()
