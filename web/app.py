"""
AI短剧自动化 - Web 界面
Flask-based, 无需 Docker
运行: python web/app.py
"""

import sys
import os
import json
import glob
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, render_template, request, jsonify, redirect, url_for

app = Flask(__name__, template_folder="templates")

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "output")
ASSET_DB = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "assets", "library.json")
API_KEYS = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "api_keys.json")


def load_projects():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    files = sorted(glob.glob(os.path.join(OUTPUT_DIR, "drama_*.json")), reverse=True)
    projects = []
    for f in files:
        try:
            with open(f, encoding="utf-8") as fp:
                data = json.load(fp)
            cfg = data.get("config", {})
            projects.append({
                "filename": os.path.basename(f),
                "topic": cfg.get("topic", "未知"),
                "style": cfg.get("style", "-"),
                "episodes": cfg.get("episodes", 0),
                "created": os.path.getmtime(f),
                "created_str": datetime.fromtimestamp(os.path.getmtime(f)).strftime("%Y-%m-%d %H:%M"),
            })
        except Exception:
            pass
    return projects


def load_assets():
    if not os.path.exists(ASSET_DB):
        return []
    with open(ASSET_DB, encoding="utf-8") as f:
        raw = json.load(f)
    return list(raw.values())


def load_project_detail(filename):
    path = os.path.join(OUTPUT_DIR, filename)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    projects = load_projects()
    return render_template("index.html", projects=projects)


@app.route("/project/<filename>")
def project_detail(filename):
    data = load_project_detail(filename)
    if not data:
        return "项目不存在", 404
    return render_template("project.html", data=data, filename=filename)


@app.route("/generate", methods=["GET", "POST"])
def generate():
    if request.method == "POST":
        topic = request.form.get("topic", "").strip()
        style = request.form.get("style", "现代")
        episodes = int(request.form.get("episodes", 3))
        if not topic:
            return render_template("generate.html", error="请输入主题", styles=_styles())

        # 启动生成任务（后台子进程）
        import subprocess
        cmd = [
            sys.executable,
            os.path.join(os.path.dirname(os.path.dirname(__file__)), "main.py"),
            "generate",
            "--topic", topic,
            "--style", style,
            "--episodes", str(episodes),
            "--auto-approve",
        ]
        subprocess.Popen(cmd, cwd=os.path.dirname(os.path.dirname(__file__)))
        return render_template("generate.html",
                               success=f"已启动生成任务: 《{topic}》({style}, {episodes}集)",
                               styles=_styles())

    return render_template("generate.html", styles=_styles())


@app.route("/assets")
def assets():
    all_assets = load_assets()
    category = request.args.get("category", "")
    keyword = request.args.get("q", "")

    if category:
        all_assets = [a for a in all_assets if a.get("category") == category]
    if keyword:
        kw = keyword.lower()
        all_assets = [
            a for a in all_assets
            if kw in a.get("name", "").lower()
            or kw in a.get("description", "").lower()
            or any(kw in t.lower() for t in a.get("tags", []))
        ]

    categories = ["character", "scene", "prop", "music", "effect", "other"]
    return render_template("assets.html", assets=all_assets,
                           categories=categories, current_category=category,
                           keyword=keyword)


# ── API endpoints ─────────────────────────────────────────────────────────────

@app.route("/api/projects")
def api_projects():
    return jsonify(load_projects())


@app.route("/api/assets")
def api_assets():
    return jsonify(load_assets())


@app.route("/api/styles")
def api_styles():
    try:
        from src.style_system import STYLE_TEMPLATES
        return jsonify({k: v.name for k, v in STYLE_TEMPLATES.items()})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/status")
def api_status():
    projects = load_projects()
    assets = load_assets()
    return jsonify({
        "projects": len(projects),
        "assets": len(assets),
        "output_dir": OUTPUT_DIR,
    })


def _styles():
    try:
        from src.style_system import STYLE_TEMPLATES
        return list(STYLE_TEMPLATES.keys())
    except Exception:
        return ["古装", "现代", "科幻", "甜宠", "虐恋", "悬疑", "搞笑"]


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7860))
    print(f"🎬 AI短剧自动化 Web 界面")
    print(f"   http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=True)
