#!/usr/bin/env python3
"""
生成统一审查界面的静态预览
"""

preview_html = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI短剧 - 内容审查预览</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }

        .container {
            max-width: 1600px;
            margin: 0 auto;
        }

        .header {
            text-align: center;
            color: white;
            margin-bottom: 30px;
        }

        .header h1 {
            font-size: 2.5em;
            margin-bottom: 10px;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }

        .header .subtitle {
            font-size: 1.2em;
            opacity: 0.9;
        }

        .demo-note {
            background: #fff3cd;
            border: 2px solid #ffc107;
            color: #856404;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 30px;
            text-align: center;
            font-size: 1.1em;
        }

        .tabs {
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
            background: rgba(255,255,255,0.1);
            padding: 10px;
            border-radius: 10px;
        }

        .tab {
            flex: 1;
            padding: 15px;
            background: rgba(255,255,255,0.2);
            color: white;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-size: 1em;
            font-weight: 600;
            transition: all 0.3s;
        }

        .tab:hover {
            background: rgba(255,255,255,0.3);
        }

        .tab.active {
            background: white;
            color: #667eea;
        }

        .content-section {
            display: none;
            background: white;
            border-radius: 15px;
            padding: 30px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            margin-bottom: 20px;
        }

        .content-section.active {
            display: block;
        }

        .section-title {
            font-size: 1.8em;
            color: #333;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 3px solid #667eea;
        }

        .characters-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }

        .character-card {
            background: #f8f9fa;
            border-radius: 10px;
            padding: 20px;
            border: 2px solid #e0e0e0;
            transition: all 0.3s;
        }

        .character-card:hover {
            border-color: #667eea;
            box-shadow: 0 5px 15px rgba(102, 126, 234, 0.2);
        }

        .character-image {
            width: 100%;
            height: 300px;
            background: linear-gradient(135deg, #e0e0e0 0%, #f5f5f5 100%);
            border-radius: 8px;
            margin-bottom: 15px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 3em;
        }

        .character-name {
            font-size: 1.3em;
            font-weight: bold;
            color: #333;
            margin-bottom: 10px;
        }

        .character-desc {
            color: #666;
            line-height: 1.6;
            font-size: 0.95em;
        }

        .videos-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }

        .video-card {
            background: #f8f9fa;
            border-radius: 10px;
            padding: 15px;
            border: 2px solid #e0e0e0;
        }

        .video-preview {
            width: 100%;
            height: 200px;
            border-radius: 8px;
            margin-bottom: 10px;
            background: #000;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-size: 2em;
        }

        .video-info {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
        }

        .video-id {
            font-weight: 600;
            color: #333;
        }

        .video-status {
            padding: 5px 12px;
            border-radius: 15px;
            font-size: 0.85em;
            font-weight: 600;
        }

        .status-completed {
            background: #4caf50;
            color: white;
        }

        .final-video-container {
            text-align: center;
            margin-bottom: 20px;
        }

        .final-video {
            width: 100%;
            max-width: 800px;
            height: 450px;
            border-radius: 10px;
            box-shadow: 0 5px 20px rgba(0,0,0,0.3);
            background: #000;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-size: 3em;
            margin: 0 auto;
        }

        .video-metadata {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-top: 20px;
            padding: 20px;
            background: #f8f9fa;
            border-radius: 10px;
        }

        .metadata-item {
            text-align: center;
        }

        .metadata-label {
            font-size: 0.9em;
            color: #666;
            margin-bottom: 5px;
        }

        .metadata-value {
            font-size: 1.3em;
            font-weight: bold;
            color: #333;
        }

        .feedback-section {
            background: white;
            border-radius: 15px;
            padding: 30px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
        }

        .feedback-title {
            font-size: 1.5em;
            color: #333;
            margin-bottom: 15px;
        }

        .feedback-input {
            width: 100%;
            padding: 15px;
            border: 2px solid #e0e0e0;
            border-radius: 10px;
            font-size: 1em;
            font-family: inherit;
            resize: vertical;
            min-height: 100px;
            transition: border-color 0.3s;
        }

        .feedback-input:focus {
            outline: none;
            border-color: #667eea;
        }

        .button-group {
            display: flex;
            gap: 15px;
            margin-top: 20px;
        }

        .btn {
            flex: 1;
            padding: 15px 30px;
            border: none;
            border-radius: 10px;
            font-size: 1.1em;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s;
        }

        .btn-approve {
            background: linear-gradient(135deg, #4caf50 0%, #45a049 100%);
            color: white;
        }

        .btn-approve:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(76, 175, 80, 0.4);
        }

        .btn-reject {
            background: linear-gradient(135deg, #f44336 0%, #e53935 100%);
            color: white;
        }

        .btn-reject:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(244, 67, 54, 0.4);
        }

        .badge {
            display: inline-block;
            padding: 5px 12px;
            border-radius: 15px;
            font-size: 0.85em;
            font-weight: 600;
            margin-left: 10px;
        }

        .badge-character {
            background: #e3f2fd;
            color: #1976d2;
        }

        .badge-video {
            background: #fff3e0;
            color: #f57c00;
        }

        .badge-final {
            background: #f3e5f5;
            color: #7b1fa2;
        }

        .badge-script {
            background: #e8f5e9;
            color: #2e7d32;
        }

        /* 剧本审查样式 */
        .script-container {
            background: #f8f9fa;
            border-radius: 10px;
            padding: 25px;
            margin-bottom: 20px;
        }

        .script-content {
            background: white;
            padding: 20px;
            border-radius: 8px;
            border-left: 4px solid #667eea;
            white-space: pre-wrap;
            font-family: "Courier New", monospace;
            font-size: 0.95em;
            line-height: 1.8;
            color: #333;
            max-height: 500px;
            overflow-y: auto;
        }

        .score-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-top: 20px;
        }

        .score-item {
            background: white;
            padding: 20px;
            border-radius: 10px;
            text-align: center;
            border: 2px solid #e0e0e0;
        }

        .score-item.good {
            border-color: #4caf50;
            background: #f1f8f4;
        }

        .score-item.warning {
            border-color: #ff9800;
            background: #fff8f0;
        }

        .score-item.bad {
            border-color: #f44336;
            background: #fef5f5;
        }

        .score-label {
            font-size: 0.9em;
            color: #666;
            margin-bottom: 10px;
        }

        .score-value {
            font-size: 2em;
            font-weight: bold;
            color: #333;
        }

        .score-status {
            margin-top: 5px;
            font-size: 0.85em;
            font-weight: 600;
        }

        .score-status.pass {
            color: #4caf50;
        }

        .score-status.fail {
            color: #f44336;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎬 AI短剧内容审查</h1>
            <p class="subtitle">完整内容审查</p>
        </div>

        <div class="demo-note">
            📌 这是界面预览 - 展示统一审查系统的样子
        </div>

        <div class="tabs">
            <button class="tab active" onclick="switchTab('script')">
                📝 剧本审查 <span class="badge badge-script">1</span>
            </button>
            <button class="tab" onclick="switchTab('characters')">
                👥 人物母版 <span class="badge badge-character">3</span>
            </button>
            <button class="tab" onclick="switchTab('videos')">
                🎥 视频片段 <span class="badge badge-video">3</span>
            </button>
            <button class="tab" onclick="switchTab('final')">
                ✨ 最终视频 <span class="badge badge-final">1</span>
            </button>
        </div>

        <!-- 剧本审查 -->
        <div id="script-section" class="content-section active">
            <h2 class="section-title">📝 剧本审查</h2>
            <div class="script-container">
                <div class="script-content">第1集：重生归来

场景1: [清晨·卧室]
女主: （震惊）这是...十年前？我重生了？
旁白: 当她再次睁开眼，时间回到了那个改变命运的早晨...

场景2: [客厅·冲突]
妈妈: 起来了？快来吃早餐。
女主: （泪流满面）妈...妈妈...(上一世，妈妈已经...)
妈妈: 怎么了？傻孩子。

场景3: [学校·反转]
同学: 听说今天有新同学转来...
男主: （出场）大家好，我是...
女主: （内心）是他！就是这个人，上一世害我家破人亡！

场景4: [结尾·钩子]
女主: （内心）既然重生了，这一世我一定要保护好家人，让他付出代价！
字幕: 敬请期待下一集</div>
                <div class="score-grid">
                    <div class="score-item warning">
                        <div class="score-label">总分</div>
                        <div class="score-value">7.5</div>
                        <div class="score-status fail">✗ 未达标</div>
                    </div>
                    <div class="score-item warning">
                        <div class="score-label">Hook吸引力</div>
                        <div class="score-value">8.0</div>
                        <div class="score-status fail">✗ 未达标</div>
                    </div>
                    <div class="score-item warning">
                        <div class="score-label">剧情结构</div>
                        <div class="score-value">7.5</div>
                        <div class="score-status fail">✗ 未达标</div>
                    </div>
                    <div class="score-item warning">
                        <div class="score-label">情绪节奏</div>
                        <div class="score-value">7.0</div>
                        <div class="score-status fail">✗ 未达标</div>
                    </div>
                </div>
            </div>
        </div>

        <!-- 人物母版 -->
        <div id="characters-section" class="content-section active">
            <h2 class="section-title">👥 人物母版审查</h2>
            <div class="characters-grid">
                <div class="character-card">
                    <div class="character-image">👩‍💼</div>
                    <div class="character-name">女主 - 苏念</div>
                    <div class="character-desc">25岁，职场精英，坚毅果敢，重生后决心改变命运</div>
                </div>
                <div class="character-card">
                    <div class="character-image">👨‍💼</div>
                    <div class="character-name">男主 - 陆沉</div>
                    <div class="character-desc">28岁，商业巨头，外表冷酷内心温柔，上一世的关键人物</div>
                </div>
                <div class="character-card">
                    <div class="character-image">👩</div>
                    <div class="character-name">女配 - 林婉儿</div>
                    <div class="character-desc">24岁，女主闺蜜，善良单纯，关键时刻的助力</div>
                </div>
            </div>
        </div>

        <!-- 视频片段 -->
        <div id="videos-section" class="content-section">
            <h2 class="section-title">🎥 视频片段审查</h2>
            <div class="videos-grid">
                <div class="video-card">
                    <div class="video-preview">🎬</div>
                    <div class="video-info">
                        <span class="video-id">场景1 - 镜头1</span>
                        <span class="video-status status-completed">已完成</span>
                    </div>
                </div>
                <div class="video-card">
                    <div class="video-preview">🎬</div>
                    <div class="video-info">
                        <span class="video-id">场景1 - 镜头2</span>
                        <span class="video-status status-completed">已完成</span>
                    </div>
                </div>
                <div class="video-card">
                    <div class="video-preview">🎬</div>
                    <div class="video-info">
                        <span class="video-id">场景1 - 镜头3</span>
                        <span class="video-status status-completed">已完成</span>
                    </div>
                </div>
            </div>
        </div>

        <!-- 最终视频 -->
        <div id="final-section" class="content-section">
            <h2 class="section-title">✨ 最终视频审查</h2>
            <div class="final-video-container">
                <div class="final-video">🎥</div>
                <div class="video-metadata">
                    <div class="metadata-item">
                        <div class="metadata-label">时长</div>
                        <div class="metadata-value">60秒</div>
                    </div>
                    <div class="metadata-item">
                        <div class="metadata-label">分辨率</div>
                        <div class="metadata-value">1080x1920</div>
                    </div>
                    <div class="metadata-item">
                        <div class="metadata-label">文件大小</div>
                        <div class="metadata-value">15.2 MB</div>
                    </div>
                    <div class="metadata-item">
                        <div class="metadata-label">帧率</div>
                        <div class="metadata-value">30 fps</div>
                    </div>
                </div>
            </div>
        </div>

        <!-- 反馈区域 -->
        <div class="feedback-section">
            <h3 class="feedback-title">📝 审查反馈</h3>
            <textarea
                id="feedbackInput"
                class="feedback-input"
                placeholder="请输入审查意见（可选）&#10;例如：&#10;- 人物形象符合预期&#10;- 第3个镜头需要调整&#10;- 整体效果良好"
            ></textarea>
            <div class="button-group">
                <button class="btn btn-reject" onclick="submitDemo('rejected')">
                    ❌ 不通过
                </button>
                <button class="btn btn-approve" onclick="submitDemo('approved')">
                    ✅ 通过
                </button>
            </div>
        </div>
    </div>

    <script>
        function switchTab(tab) {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            event.target.classList.add('active');

            document.querySelectorAll('.content-section').forEach(s => s.classList.remove('active'));
            document.getElementById(`${tab}-section`).classList.add('active');
        }

        function submitDemo(status) {
            const feedback = document.getElementById('feedbackInput').value.trim();
            const statusText = status === 'approved' ? '通过' : '不通过';

            alert(`✓ 审查已提交！\\n\\n状态: ${statusText}\\n反馈: ${feedback || '无'}\\n\\n在真实系统中，这个结果会被提交并继续流程。`);
        }
    </script>
</body>
</html>
"""

# 保存预览文件
output_path = "/Users/you/.openclaw/workspace/ai-short-drama-automator/unified_review_preview.html"
with open(output_path, 'w', encoding='utf-8') as f:
    f.write(preview_html)

print("=" * 60)
print("统一审查界面预览已生成")
print("=" * 60)
print(f"\n✓ 预览文件: {output_path}")
print(f"\n📌 打开方式:")
print(f"   1. 在浏览器中打开: file://{output_path}")
print(f"   2. 或运行: open {output_path}")
print(f"\n💡 这是一个静态预览，展示界面的样子")
print(f"   真实使用时会连接到后端服务器并显示实际内容")
