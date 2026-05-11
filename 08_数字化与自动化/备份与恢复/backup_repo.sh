#!/bin/bash
# ====================================================
# scorer-reports GitHub仓库 本地备份脚本
# ====================================================
# 功能：定期将GitHub仓库clone/pull到本地，保留最近30个版本tag
# 使用方式：
#   ./backup_repo.sh                          # 执行一次备份
#   ./backup_repo.sh --cron                   # 定时模式（配合crontab）
#   ./backup_repo.sh --force                  # 强制完整clone（遇到问题时用）
#
# 配合crontab每天执行一次：
#   crontab -e
#   0 9 * * * /Users/hanmin/Documents/精益智能工厂/08_数字化与自动化/备份与恢复/backup_repo.sh --cron >> /tmp/repo_backup.log 2>&1
#
# 注意：中国大陆访问GitHub可能较慢，建议设置git代理
#   git config --global http.proxy http://127.0.0.1:7890
#   git config --global https.proxy http://127.0.0.1:7890
# ====================================================

set -euo pipefail

# === 配置 ===
GITHUB_REPO="https://github.com/Kevinhanmin/scorer-reports.git"
BACKUP_DIR="$HOME/scorer-reports-backup"
RETENTION_TAGS=30          # 保留最近的N个版本tag
LOG_FILE="/tmp/repo_backup.log"
TIMEOUT_SECONDS=120        # Git操作超时（秒）

# === 颜色 ===
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

log() {
    local msg="[$(date '+%Y-%m-%d %H:%M:%S')] $1"
    echo -e "${GREEN}${msg}${NC}" | tee -a "$LOG_FILE"
}

warn() {
    local msg="[$(date '+%Y-%m-%d %H:%M:%S')] ⚠️  $1"
    echo -e "${YELLOW}${msg}${NC}" | tee -a "$LOG_FILE"
}

err() {
    local msg="[$(date '+%Y-%m-%d %H:%M:%S')] ❌ $1"
    echo -e "${RED}${msg}${NC}" | tee -a "$LOG_FILE"
    exit 1
}

# === 克隆/拉取仓库 ===
clone_or_pull() {
    if [ -d "$BACKUP_DIR/.git" ]; then
        log "仓库已存在，执行 git pull..."
        cd "$BACKUP_DIR"
        git fetch --tags --prune 2>&1 | tee -a "$LOG_FILE" || warn "fetch失败，尝试重新clone..."
        git reset --hard origin/main 2>&1 | tee -a "$LOG_FILE" || return 1
        log "✅ git pull 完成"
    else
        log "首次备份，执行 git clone..."
        mkdir -p "$BACKUP_DIR"
        git clone --tags "$GITHUB_REPO" "$BACKUP_DIR" 2>&1 | tee -a "$LOG_FILE" || return 1
        log "✅ git clone 完成"
    fi
    return 0
}

# === 创建版本标签 ===
create_backup_tag() {
    cd "$BACKUP_DIR"
    local tag_name="backup-$(date '+%Y%m%d-%H%M%S')"
    git tag -f "$tag_name" HEAD 2>&1 | tee -a "$LOG_FILE"
    log "✅ 创建备份标签: $tag_name"

    # 删除旧标签（只保留最新的RETENTION_TAGS个）
    local latest_tags
    latest_tags=$(git tag -l 'backup-*' --sort=-creatordate | head -n "$RETENTION_TAGS")
    local all_backup_tags
    all_backup_tags=$(git tag -l 'backup-*' --sort=-creatordate)

    local removed=0
    for tag in $all_backup_tags; do
        if ! echo "$latest_tags" | grep -q "^$tag$"; then
            git tag -d "$tag" 2>&1 | tee -a "$LOG_FILE"
            removed=$((removed + 1))
        fi
    done
    if [ "$removed" -gt 0 ]; then
        log "🧹 清理了 $removed 个旧标签"
    fi
}

# === 统计备份信息 ===
show_stats() {
    cd "$BACKUP_DIR"
    local report_count
    report_count=$(find reports/ -name '*.html' 2>/dev/null | wc -l | tr -d ' ')
    local last_commit
    last_commit=$(git log -1 --format='%h %s (%ai)' 2>/dev/null)
    local disk_usage
    disk_usage=$(du -sh "$BACKUP_DIR" 2>/dev/null | cut -f1)

    log "📊 备份统计:"
    log "  报告文件: $report_count 个"
    log "  最后提交: $last_commit"
    log "  磁盘占用: $disk_usage"
    log "  备份位置: $BACKUP_DIR"
}

# === 对比本地scorer_cloud.py与备份版本 ===
check_local_diff() {
    if [ -f "$HOME/scorer_cloud.py" ] && [ -f "$BACKUP_DIR/scorer_cloud.py" ]; then
        if diff -q "$HOME/scorer_cloud.py" "$BACKUP_DIR/scorer_cloud.py" > /dev/null 2>&1; then
            log "✅ 本地scorer_cloud.py与云端版本一致"
        else
            warn "本地scorer_cloud.py与云端版本不一致！"
            warn "  本地: $HOME/scorer_cloud.py"
            warn "  云端: $BACKUP_DIR/scorer_cloud.py"
        fi
    fi
}

# === 主要流程 ===
main() {
    log "========================================"
    log "🚀 scorer-reports 本地备份开始"
    log "========================================"

    # 检查网络（尝试ping GitHub）
    if ! ping -c 1 -W 3 github.com > /dev/null 2>&1; then
        err "无法访问GitHub（ping不通），请检查网络连接"
    fi

    # 尝试clone/pull（失败时重试一次）
    if ! clone_or_pull; then
        warn "首次尝试失败，5秒后重试..."
        sleep 5
        if [ -d "$BACKUP_DIR/.git" ]; then
            rm -rf "$BACKUP_DIR"
        fi
        clone_or_pull || err "Git操作失败，请检查网络或认证"
    fi

    # 创建备份标签
    create_backup_tag

    # 统计信息
    show_stats

    # 检查本地文件一致性
    check_local_diff

    log "========================================"
    log "✅ 备份完成"
    log "========================================"
}

# === 入口 ===
case "${1:-}" in
    --cron)
        # cron模式下不输出颜色
        GREEN=''; YELLOW=''; RED=''; NC=''
        main
        ;;
    --force)
        log "强制模式：删除现有备份仓库并重新clone..."
        rm -rf "$BACKUP_DIR"
        main
        ;;
    --help|-h)
        echo "用法: $0 [选项]"
        echo "  (无参数)   执行一次备份"
        echo "  --cron     cron定时模式（无颜色输出）"
        echo "  --force    强制重新clone"
        echo "  --help     显示此帮助"
        exit 0
        ;;
    *)
        main
        ;;
esac
