#!/usr/bin/env python3
"""
统一审查系统 - Web UI

提供一个统一的 Web 界面用于审查：
1. 人物母版（角色一致性）
2. 视频生成进度
3. 最终视频效果

特点：
- 自动弹出浏览器
- 审查完成后自动关闭
- 实时更新状态
"""

import os
import json
import base64
from typing import List, Dict, Any, Optional
from flask import Flask, render_template, request, jsonify, send_file
import threading
import webbrowser
import time
from datetime import datetime

class UnifiedReviewSystem:
    """统一审查系统"""

    def __init__(self, port: int = 5001):
        self.port = port
        self.app = Flask(__name__,
                        template_folder=os.path.join(os.path.dirname(__file__), '..', 'templates'),
                        static_folder=os.path.join(os.path.dirname(__file__), '..', 'static'))

        # 审查数据
        self.review_data = {
            'type': None,  # 'script' / 'character' / 'video_progress' / 'final_video' / 'all'
            'script': None,
            'script_score': None,
            'characters': [],
            'videos': [],
            'final_video_path': None,
            'status': 'pending'  # pending / approved / rejected
        }

        self.review_complete = threading.Event()
        self.review_result = None

        # 注册路由
        self._setup_routes()

    def _setup_routes(self):
        """设置路由"""

        @self.app.route('/')
        def index():
            """主页"""
            return render_template('unified_review.html')

        @self.app.route('/api/review_data')
        def get_review_data():
            """获取审查数据"""
            return jsonify(self.review_data)

        @self.app.route('/api/submit_review', methods=['POST'])
        def submit_review():
            """提交审查结果"""
            data = request.json
            self.review_result = {
                'status': data.get('status'),  # approved / rejected
                'feedback': data.get('feedback', ''),
                'timestamp': datetime.now().isoformat()
            }
            self.review_complete.set()
            return jsonify({'status': 'success'})

        @self.app.route('/api/video/<path:filename>')
        def serve_video(filename):
            """提供视频文件"""
            return send_file(filename, mimetype='video/mp4')

        @self.app.route('/api/image/<path:filename>')
        def serve_image(filename):
            """提供图片文件"""
            return send_file(filename, mimetype='image/png')

    def review_script(self, script: str, score: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        审查剧本

        Args:
            script: 剧本内容
            score: Meta Director 的评分结果

        Returns:
            审查结果
        """
        self.review_data = {
            'type': 'script',
            'script': script,
            'script_score': score,
            'characters': [],
            'videos': [],
            'final_video_path': None,
            'status': 'pending'
        }

        return self._start_review("剧本审查")

    def review_characters(self, characters: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        审查人物母版

        Args:
            characters: 角色列表，每个包含 name, image_path, description

        Returns:
            审查结果 {status: 'approved'/'rejected', feedback: '...'}
        """
        self.review_data = {
            'type': 'character',
            'script': None,
            'script_score': None,
            'characters': characters,
            'videos': [],
            'final_video_path': None,
            'status': 'pending'
        }

        return self._start_review("人物母版审查")

    def review_video_progress(self, videos: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        审查视频生成进度

        Args:
            videos: 视频列表，每个包含 shot_id, video_path, thumbnail_path, status

        Returns:
            审查结果
        """
        self.review_data = {
            'type': 'video_progress',
            'script': None,
            'script_score': None,
            'characters': [],
            'videos': videos,
            'final_video_path': None,
            'status': 'pending'
        }

        return self._start_review("视频生成进度审查")

    def review_final_video(self, video_path: str, metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        审查最终视频效果

        Args:
            video_path: 最终视频路径
            metadata: 视频元数据（时长、分辨率等）

        Returns:
            审查结果
        """
        self.review_data = {
            'type': 'final_video',
            'script': None,
            'script_score': None,
            'characters': [],
            'videos': [],
            'final_video_path': video_path,
            'metadata': metadata or {},
            'status': 'pending'
        }

        return self._start_review("最终视频审查")

    def review_all(self, script: str = None, script_score: Dict = None,
                   characters: List[Dict] = None, videos: List[Dict] = None,
                   final_video: str = None) -> Dict[str, Any]:
        """
        统一审查所有内容

        Args:
            script: 剧本内容
            script_score: 剧本评分
            characters: 角色列表
            videos: 视频片段列表
            final_video: 最终视频路径

        Returns:
            审查结果
        """
        self.review_data = {
            'type': 'all',
            'script': script,
            'script_score': script_score,
            'characters': characters or [],
            'videos': videos or [],
            'final_video_path': final_video,
            'status': 'pending'
        }

        return self._start_review("完整内容审查")

    def _start_review(self, title: str) -> Dict[str, Any]:
        """启动审查流程"""
        self.review_complete.clear()
        self.review_result = None

        # 在新线程中启动 Flask
        server_thread = threading.Thread(target=self._run_server, daemon=True)
        server_thread.start()

        # 等待服务器启动
        time.sleep(1)

        # 打开浏览器
        url = f'http://localhost:{self.port}'
        print(f"\n🌐 {title}界面已启动: {url}")
        print(f"   请在浏览器中审查内容...")
        webbrowser.open(url)

        # 等待审查完成
        self.review_complete.wait()

        print(f"\n✓ 审查完成: {self.review_result['status']}")
        if self.review_result.get('feedback'):
            print(f"   反馈: {self.review_result['feedback']}")

        return self.review_result

    def _run_server(self):
        """运行 Flask 服务器"""
        self.app.run(host='0.0.0.0', port=self.port, debug=False, use_reloader=False)


# 集成到 Meta Director
class MetaDirectorWithReview:
    """带审查功能的 Meta Director"""

    def __init__(self, config: Dict[str, Any] = None):
        from src.meta_director import MetaDirector
        self.meta_director = MetaDirector(config)
        self.review_system = UnifiedReviewSystem()
        self.enable_web_review = config.get('enable_web_review', True) if config else True

    def review_script(self, script: str, score: Dict = None) -> bool:
        """审查剧本"""
        if not self.enable_web_review:
            return True

        result = self.review_system.review_script(script, score)
        return result['status'] == 'approved'

    def review_characters(self, characters: List[Dict]) -> bool:
        """审查人物母版"""
        if not self.enable_web_review:
            return True

        result = self.review_system.review_characters(characters)
        return result['status'] == 'approved'

    def review_videos(self, videos: List[Dict]) -> bool:
        """审查视频片段"""
        if not self.enable_web_review:
            return True

        result = self.review_system.review_video_progress(videos)
        return result['status'] == 'approved'

    def review_final_video(self, video_path: str, metadata: Dict = None) -> bool:
        """审查最终视频"""
        if not self.enable_web_review:
            return True

        result = self.review_system.review_final_video(video_path, metadata)
        return result['status'] == 'approved'

    def review_all(self, script: str = None, script_score: Dict = None,
                   characters: List[Dict] = None, videos: List[Dict] = None,
                   final_video: str = None) -> bool:
        """统一审查所有内容"""
        if not self.enable_web_review:
            return True

        result = self.review_system.review_all(script, script_score, characters, videos, final_video)
        return result['status'] == 'approved'
