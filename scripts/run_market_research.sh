#!/bin/bash
# 市场调研定时任务包装脚本
# 每 24 小时由 cron 自动执行

PROJECT_DIR="$HOME/.openclaw/workspace/ai-short-drama-automator"
LOG_DIR="$PROJECT_DIR/output/market_research/logs"
mkdir -p "$LOG_DIR"

TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LOG_FILE="$LOG_DIR/research_${TIMESTAMP}.log"

echo "[$(date)] 开始市场调研..." >> "$LOG_FILE"

# 确保 PATH 包含 openclaw 和 python3
export PATH="/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:$HOME/.npm-global/bin:$PATH"

cd "$PROJECT_DIR" || exit 1

python3 scripts/gemini_automation.py >> "$LOG_FILE" 2>&1
EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo "[$(date)] 调研完成 ✓" >> "$LOG_FILE"
else
    echo "[$(date)] 调研失败，退出码: $EXIT_CODE" >> "$LOG_FILE"
fi

# 只保留最近 7 天的日志
find "$LOG_DIR" -name "*.log" -mtime +7 -delete

exit $EXIT_CODE
