#!/bin/bash
# ============================================================
# 思派工业 · 每日行业快讯 → 微信公众号自动发布管线
# ============================================================
# 由 LaunchAgent 每日 08:30 自动执行
#
# 流程：
# 1. 检查今日快讯是否已生成（daily_news_brief.py）
# 2. 转换为公众号HTML格式（wechat_article_builder.py）
# 3. 通过API创建草稿（push_to_wechat_mp.py --draft）
# 4. 记录发布状态
# ============================================================

set -e

NEWS_DIR="$HOME/Documents/思派工业/内容系统/每日快讯"
LEAN_DIR="$HOME/Documents/精益智能工厂/02_生产管理/每日快讯"
TODAY=$(date +%Y%m%d)
TODAY_LABEL=$(date +%Y-%m-%d)

echo "============================================"
echo "📰 思派 · 每日快讯 → 公众号自动发布管线"
echo "   日期: $TODAY_LABEL"
echo "============================================"

# Step 1: Check if today's newsletter exists
if [ -f "$NEWS_DIR/每日行业快讯_$TODAY_LABEL.md" ]; then
    echo "✅ 今日快讯已存在"
else
    echo "⏳ 今日快讯未生成，正在采集..."
    cd "$NEWS_DIR"
    python3 daily_news_brief.py --publish 2>&1 || echo "⚠️ 采集完成（有警告）"
fi

# Step 2: Copy to lean directory for wechat builder
if [ -f "$NEWS_DIR/每日行业快讯_$TODAY_LABEL.md" ]; then
    cp "$NEWS_DIR/每日行业快讯_$TODAY_LABEL.md" "$LEAN_DIR/每日快讯_$TODAY.md"
    echo "✅ 已复制到精益目录"
fi

# Step 3: Generate WeChat HTML
if [ -f "$LEAN_DIR/每日快讯_$TODAY.md" ]; then
    cd "$LEAN_DIR"
    python3 wechat_article_builder.py --today 2>&1
    echo "✅ 公众号HTML已生成"
fi

# Step 4: Create draft via API
if [ -f "$LEAN_DIR/每日快讯_${TODAY}_wechat.html" ]; then
    cd "$LEAN_DIR"
    source "$HOME/.hermes/.env"
    export WECHAT_MP_APPID
    export WECHAT_MP_APPSECRET
    export WECHAT_THUMB_MEDIA_ID
    python3 push_to_wechat_mp.py --file "每日快讯_${TODAY}_wechat.html" --draft 2>&1
    echo "✅ 公众号草稿已创建"
fi

echo "============================================"
echo "✅ 管线执行完成"
echo "============================================"
