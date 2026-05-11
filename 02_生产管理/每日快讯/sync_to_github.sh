#!/bin/bash
# 思派知识库 → GitHub同步脚本
# 用法: 先设置 GitHub Token，然后运行本脚本
#
# Step 1: 获取 GitHub Token
#   访问 https://github.com/settings/tokens
#   点击 "Generate new token (classic)"
#   选择 repo 权限
#   复制生成的 token
#
# Step 2: 设置 Token（只需一次）
#   export GITHUB_TOKEN=ghp_你的token
#   bash sync_to_github.sh
#
# 之后每次更新知识库，运行:
#   bash sync_to_github.sh

set -e

VAULT="$HOME/Documents/精益智能工厂"
REPO_NAME="sipai-knowledge-base"
GITHUB_USER="Kevinhanmin"

if [ -z "$GITHUB_TOKEN" ]; then
    echo "❌ 请先设置 GITHUB_TOKEN 环境变量"
    echo "   例如: export GITHUB_TOKEN=ghp_你的token"
    echo ""
    echo "   获取方式: https://github.com/settings/tokens"
    exit 1
fi

echo "📤 思派知识库 → GitHub同步"
echo "=========================="
echo ""

# 1. 创建 GitHub 仓库（如果不存在）
echo "📦 检查仓库状态..."
REPO_URL="https://api.github.com/repos/${GITHUB_USER}/${REPO_NAME}"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -H "Authorization: token $GITHUB_TOKEN" "$REPO_URL" 2>/dev/null || echo "000")

if [ "$HTTP_CODE" = "404" ] || [ "$HTTP_CODE" = "000" ]; then
    echo "   🔄 创建新仓库: ${GITHUB_USER}/${REPO_NAME}"
    curl -s -X POST -H "Authorization: token $GITHUB_TOKEN" \
        -H "Content-Type: application/json" \
        -d "{\"name\":\"$REPO_NAME\",\"description\":\"思派精益智能工厂 · 知识文库\",\"private\":false,\"auto_init\":false}" \
        "https://api.github.com/user/repos" > /dev/null
    echo "   ✅ 仓库已创建"
else
    echo "   ✅ 仓库已存在"
fi

# 2. 配置 git remote
echo "🔗 配置远程仓库..."
cd "$VAULT"
git remote remove origin 2>/dev/null || true
git remote add origin "https://${GITHUB_USER}:${GITHUB_TOKEN}@github.com/${GITHUB_USER}/${REPO_NAME}.git"
echo "   ✅ 远程仓库已配置"

# 3. 添加 .gitignore for Obsidian
if [ ! -f ".gitignore" ]; then
    cat > .gitignore << 'GITIGNORE'
# Obsidian
.obsidian/workspace
.obsidian/workspace.json
.obsidian/cache
.obsidian/graph.json
.obsidian/plugins/*/data.json

# OS
.DS_Store
Thumbs.db

# IDE
.idea/
.vscode/
*.swp
*.swo

# Temp
*~
._*
GITIGNORE
    echo "   ✅ .gitignore 已创建"
fi

# 4. Push
echo "📤 推送到 GitHub..."
git add -A
git commit --allow-empty -m "🔄 知识库同步 $(date '+%Y-%m-%d %H:%M')"
git push -u origin main --force 2>/dev/null || git push -u origin main

echo ""
echo "✅ 同步完成！"
echo "📁 仓库地址: https://github.com/${GITHUB_USER}/${REPO_NAME}"
echo ""
echo "📌 在另一台电脑上同步:"
echo "   git clone https://github.com/${GITHUB_USER}/${REPO_NAME}.git"
echo "   然后用 Obsidian → 打开本地仓库 → 选择该文件夹"
echo ""
echo "📌 后续更新只需运行:"
echo "   cd ~/Documents/精益智能工厂 && git push"
