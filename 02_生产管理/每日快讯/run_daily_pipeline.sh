#!/bin/bash
# 思派工业 · 每日行业快讯 + 知识库更新 组合脚本
# 由 LaunchAgent 每天 08:00 自动执行
#
# Step 1: 生成当日快讯模板 + 通知创始人
# Step 2: 爬取行业资讯，存入知识库

DIR="$HOME/Documents/精益智能工厂/02_生产管理/每日快讯"
LOG="/tmp/daily_sipai_kb.log"

echo "===== 思派工业 · 每日自动化 =====" > "$LOG"
echo "开始时间: $(date)" >> "$LOG"
echo "" >> "$LOG"

# Step 1: 每日行业快讯模板生成
echo "--- Step 1: 每日快讯模板 ---" >> "$LOG"
cd "$DIR" && /usr/bin/python3 daily_newsletter_full.py >> "$LOG" 2>&1
echo "" >> "$LOG"

# Step 2: 知识库爬虫（写入新笔记）
echo "--- Step 2: 知识库爬虫 ---" >> "$LOG"
cd "$DIR" && /usr/bin/python3 daily_industry_crawler.py --email-founder >> "$LOG" 2>&1
echo "" >> "$LOG"

# Step 3: 推送到 GitHub（同步到用户本机Obsidian）
echo "--- Step 3: GitHub同步 ---" >> "$LOG"
cd "$HOME/Documents/精益智能工厂" && \
  git add -A && \
  git commit --allow-empty -m "🔄 每日自动同步 $(date '+%Y-%m-%d %H:%M')" && \
  git push >> "$LOG" 2>&1
echo "" >> "$LOG"

# 完成
echo "完成时间: $(date)" >> "$LOG"
echo "==========================" >> "$LOG"
