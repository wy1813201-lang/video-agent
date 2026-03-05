#!/usr/bin/env python3
"""
Web 人工选择器 - 提供 Web UI 界面

使用 Flask 提供一个简单的 Web 界面用于人工选择
"""

import os
import json
from typing import List, Dict, Any, Optional
from flask import Flask, render_template, request, jsonify
import threading
import webbrowser
import time

class WebHumanSelector:
    """Web 人工选择器"""

    def __init__(self, port: int = 5000):
        self.port = port
        self.app = Flask(__name__,
                        template_folder=os.path.join(os.path.dirname(__file__), '..', 'templates'),
                        static_folder=os.path.join(os.path.dirname(__file__), '..', 'static'))
        self.selected_result = None
        self.versions_data = None
        self.selection_complete = threading.Event()

        # 注册路由
        self._setup_routes()

    def _setup_routes(self):
        """设置路由"""

        @self.app.route('/')
        def index():
            """主页"""
            return render_template('selector.html')

        @self.app.route('/api/versions')
        def get_versions():
            """获取版本数据"""
            if self.versions_data:
                return jsonify(self.versions_data)
            return jsonify([])

        @self.app.route('/api/select', methods=['POST'])
        def select_version():
            """提交选择"""
            data = request.json
            self.selected_result = {
                'version_id': data.get('version_id'),
                'reason': data.get('reason'),
                'content': data.get('content')
            }
            self.selection_complete.set()
            return jsonify({'status': 'success'})

    def select_best_script(self, versions: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        让用户从多个剧本版本中选择最佳版本（Web UI）

        Args:
            versions: 版本列表，每个版本包含 version_id, params, content

        Returns:
            选中的版本字典，包含 version_id, reason, content
        """
        if not versions:
            return None

        self.versions_data = versions
        self.selected_result = None
        self.selection_complete.clear()

        # 在新线程中启动 Flask
        server_thread = threading.Thread(target=self._run_server, daemon=True)
        server_thread.start()

        # 等待服务器启动
        time.sleep(1)

        # 打开浏览器
        url = f'http://localhost:{self.port}'
        print(f"\n🌐 Web 选择界面已启动: {url}")
        print(f"   请在浏览器中选择最佳版本...")
        webbrowser.open(url)

        # 等待用户选择
        self.selection_complete.wait()

        return self.selected_result

    def _run_server(self):
        """运行 Flask 服务器"""
        self.app.run(host='0.0.0.0', port=self.port, debug=False, use_reloader=False)


# 为了兼容性，保留原来的 CLI 版本
class HumanSelector:
    """CLI 人工选择器（原版本）"""

    @staticmethod
    def select_best_script(versions: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """CLI 版本的选择"""
        if not versions:
            return None

        print("\n" + "=" * 60)
        print("🧪 实验版本选择")
        print("=" * 60)

        # 显示所有版本
        for idx, version in enumerate(versions, 1):
            print(f"\n【版本 {idx}】{version['version_id']}")
            print(f"参数: {version['params'].get('name', 'unknown')}")
            print(f"特点:")
            params = version['params']
            if params.get('conflict_timing'):
                print(f"  - 冲突时间: {params['conflict_timing']}")
            if params.get('reversal_count'):
                print(f"  - 反转次数: {params['reversal_count']}")
            if params.get('emotion_intensity'):
                print(f"  - 情绪强度: {params['emotion_intensity']}")
            if params.get('hook_style'):
                print(f"  - Hook风格: {params['hook_style']}")

            # 显示剧本预览（前200字）
            content = str(version.get('content', ''))
            preview = content[:200] + "..." if len(content) > 200 else content
            print(f"\n预览:\n{preview}\n")

        # 用户选择
        while True:
            try:
                choice = input(f"\n请选择最佳版本 (1-{len(versions)}) 或输入 0 跳过: ")
                choice_num = int(choice)

                if choice_num == 0:
                    print("跳过选择")
                    return None

                if 1 <= choice_num <= len(versions):
                    selected = versions[choice_num - 1]
                    reason = input("请说明选择理由: ").strip()

                    if not reason:
                        reason = "未提供理由"

                    return {
                        "version_id": selected['version_id'],
                        "reason": reason,
                        "content": selected['content']
                    }
                else:
                    print(f"❌ 请输入 0-{len(versions)} 之间的数字")

            except ValueError:
                print("❌ 请输入有效的数字")
            except KeyboardInterrupt:
                print("\n\n取消选择")
                return None
