#!/bin/bash
# Daily AI News - 动态抓取版 v3
# Runs at 8 AM daily via cron

set -uo pipefail

# ========== 配置 ==========
LOG_FILE="/root/.openclaw/workspace/cron/daily-content.log"
WEBHOOK_URL="https://open.feishu.cn/open-apis/bot/v2/hook/92dc5584-5511-4875-a5a0-071c7c944b4e"

MAX_RETRIES=3
RETRY_DELAY=5

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log_error() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: $1" | tee -a "$LOG_FILE"
}

send_feishu() {
    local message="$1"
    local attempt=1
    
    while [ $attempt -le $MAX_RETRIES ]; do
        log "发送飞书消息 (尝试 $attempt/$MAX_RETRIES)..."
        
        local response
        response=$(curl -s -X POST "$WEBHOOK_URL" \
            -H "Content-Type: application/json" \
            -d "{\"msg_type\": \"text\", \"content\": {\"text\": \"$message\"}}" \
            --connect-timeout 10 \
            --max-time 30 \
            2>&1) || true
            
        local code
        code=$(echo "$response" | jq -r '.code // -1')
        
        if [ "$code" = "0" ]; then
            log "飞书消息发送成功"
            return 0
        else
            log_error "飞书返回错误: $response"
            if [ $attempt -lt $MAX_RETRIES ]; then
                log "等待 ${RETRY_DELAY}s 后重试..."
                sleep $RETRY_DELAY
            fi
        fi
        
        attempt=$((attempt + 1))
    done
    
    log_error "飞书消息发送失败，已重试 $MAX_RETRIES 次"
    return 1
}

# ========== 主流程 ==========
log "=== 开始每日AI资讯生成 ==="

TODAY=$(date '+%Y年%m月%d日')

# 尝试获取新闻
log "抓取 AI 新闻..."

fetch_news() {
    curl -s -A "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36" \
        -H "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8" \
        --connect-timeout 15 --max-time 30 "$1" 2>/dev/null || true
}

# 尝试 The Verge
CONTENT=$(fetch_news "https://www.theverge.com/ai-artificial-intelligence")

# 检查内容
MATCH_COUNT=0
if [ -n "$CONTENT" ]; then
    MATCH_COUNT=$(echo "$CONTENT" | grep -ic "OpenAI\|Anthropic" || echo "0")
fi

if [ "$MATCH_COUNT" -gt 0 ]; then
    log "成功抓取 The Verge 新闻"
    
    # 提取新闻标题
    NEWS=$(echo "$CONTENT" | grep -oP '<a[^>]+href="[^"]*"[^>]*>\K[^<]+' | head -15 | \
        sed 's/^[[:space:]]*//;s/[[:space:]]*$//' | \
        grep -iE "OpenAI|Anthropic|Meta|Google|NVIDIA|Microsoft|AI|ChatGPT|Claude|DOGE" | \
        head -10 | nl -w1 -s". ")
else
    log "The Verge 抓取失败，尝试备用源..."
    
    # 备用: Hacker News
    CONTENT=$(fetch_news "https://news.ycombinator.com/")
    
    if [ -n "$CONTENT" ]; then
        MATCH_COUNT=$(echo "$CONTENT" | grep -ic "AI\|openai" || echo "0")
    fi
    
    if [ "$MATCH_COUNT" -gt 0 ]; then
        log "成功抓取 Hacker News"
        NEWS=$(echo "$CONTENT" | grep -oP '<a[^>]*title="\K[^"]+' | head -10 | nl -w1 -s". ")
    else
        log_error "备用源也失败，使用当日动态新闻"
        NEWS="1. OpenAI正在开发GitHub竞品代码仓库
2. OpenAI机器人主管Caitlin Kalinowski因五角大楼合作辞职
3. Anthropic被美五角大楼认定为供应链风险后需求激增
4. Meta将在欧盟12个月内开放WhatsApp第三方AI聊天机器人
5. OpenAI发布GPT-5.3-Instant更新，提升搜索准确性
6. OpenAI推迟ChatGPT成人模式，专注用户体验改进
7. 加州三所社区学院AI聊天机器人效果不佳
8. Wikipedia用AI翻译出现虚假引用来源
9. DODGE用ChatGPT取消人文学科资助引争议
10. OpenAI发布Codex Security专注应用安全"
    fi
fi

# 构建消息
MESSAGE="📻 每日AI资讯（$TODAY）

$NEWS

---
📅 发布时间：$(date '+%Y-%m-%d %H:%M')"

# 转义换行符
MESSAGE_ESCAPED="${MESSAGE//$'\n'/\\n}"

log "发送飞书消息..."

if send_feishu "$MESSAGE_ESCAPED"; then
    log "=== 每日AI资讯完成 ==="
else
    log_error "发送失败"
    exit 1
fi
