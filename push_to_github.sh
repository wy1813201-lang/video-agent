#!/bin/bash
# GitHub 推送脚本
# 运行此脚本将代码推送到 GitHub

PROJECT_NAME="video-agent"

echo "📦 准备推送 VideoAgent 项目到 GitHub..."
echo ""

# 检查 git 是否可用
if ! command -v git &> /dev/null; then
    echo "❌ Git 未安装"
    exit 1
fi

cd /Users/you/.openclaw/workspace/ai-short-drama-automator

# 初始化 git（如果尚未初始化）
if [ ! -d .git ]; then
    echo "📌 初始化 Git 仓库..."
    git init
    git add .
    git commit -m "Initial commit: VideoAgent AI短剧自动生成器"
fi

echo ""
echo "请在 GitHub 上创建仓库: https://github.com/new"
echo "仓库名称: $PROJECT_NAME"
echo ""
echo "然后运行以下命令:"
echo ""
echo "  git remote add origin https://github.com/YOUR_USERNAME/$PROJECT_NAME.git"
echo "  git branch -M main"
echo "  git push -u origin main"
echo ""
echo "或者运行以下命令自动创建（需要 gh CLI）:"
echo "  gh repo create $PROJECT_NAME --public --source=. --push"
