#!/bin/bash
# 每日行业快讯推送脚本
# 审核通过后调用：本脚本将快讯内容通过飞书发送给创始人
#
# 用法:
#   ./push_newsletter_to_wechat.sh              # 推送今日快讯
#   ./push_newsletter_to_wechat.sh 2026-05-12   # 推送指定日期快讯

DATE="${1:-$(date +%Y%m%d)}"

# 尝试多种日期格式
if [ "$DATE" = "$(date +%Y%m%d)" ]; then
    FILE_DATE=$(date +%Y%m%d)
elif [[ "$DATE" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]]; then
    FILE_DATE=$(echo "$DATE" | tr -d '-')
elif [[ "$DATE" =~ ^[0-9]{8}$ ]]; then
    FILE_DATE="$DATE"
else
    echo "❌ 日期格式错误，支持: YYYYMMDD 或 YYYY-MM-DD"
    exit 1
fi

FILE="$HOME/Documents/精益智能工厂/02_生产管理/每日快讯/每日快讯_${FILE_DATE}.md"

if [ ! -f "$FILE" ]; then
    echo "❌ 快讯文件不存在: $FILE"
    exit 1
fi

echo "📤 推送快讯: $FILE"
python3 "$HOME/Documents/精益智能工厂/02_生产管理/每日快讯/daily_newsletter_full.py" --notify --file "$FILE"
