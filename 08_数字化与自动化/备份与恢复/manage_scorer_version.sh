#!/bin/bash
# ====================================================
# scorer_cloud.py 版本管理器
# ====================================================
# 功能：
#   - 将本地scorer_cloud.py同步备份到备份目录
#   - 自动创建带时间戳的版本副本
#   - 保留最近20个版本，自动清理旧版本
#   - 对比本地与云端（GitHub）版本的差异
#
# 使用方式：
#   ./manage_scorer_version.sh                   # 同步本地scorer_cloud.py到版本仓库
#   ./manage_scorer_version.sh --list            # 列出所有版本
#   ./manage_scorer_version.sh --diff-local      # 比较本地与云端最新版
#   ./manage_scorer_version.sh --restore <版本号> # 恢复指定版本
#   ./manage_scorer_version.sh --clean           # 手动清理旧版本
#   ./manage_scorer_version.sh --setup-cron      # 添加crontab定时同步（每日一次）
# ====================================================

set -euo pipefail

LOCAL_SCORER="$HOME/scorer_cloud.py"
LOCAL_EVOLUTION="$HOME/scorer_evolution.py"
VERSION_DIR="$HOME/Documents/精益智能工厂/08_数字化与自动化/备份与恢复/scorer_versions"
RETENTION_COUNT=20
LOG_FILE="/tmp/scorer_version.log"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; CYAN='\033[0;36m'; NC='\033[0m'

mkdir -p "$VERSION_DIR"

log() { echo -e "${GREEN}[$(date '+%H:%M:%S')] $1${NC}" | tee -a "$LOG_FILE"; }
warn() { echo -e "${YELLOW}[$(date '+%H:%M:%S')] ⚠️  $1${NC}" | tee -a "$LOG_FILE"; }
err()  { echo -e "${RED}[$(date '+%H:%M:%S')] ❌ $1${NC}"; exit 1; }

# === 同步本地scorer版本 ===
sync_local() {
    if [ ! -f "$LOCAL_SCORER" ]; then
        warn "本地 $LOCAL_SCORER 不存在，跳过"
        return
    fi

    local ts
    ts=$(date '+%Y%m%d_%H%M%S')
    local hash
    hash=$(md5 -q "$LOCAL_SCORER" 2>/dev/null || md5sum "$LOCAL_SCORER" | cut -d' ' -f1)

    # 检查是否与最后一个版本相同
    local latest
    latest=$(ls -t "$VERSION_DIR"/scorer_cloud_*.py 2>/dev/null | head -1) || true
    local should_save=true
    if [ -n "$latest" ] && [ -f "$latest" ]; then
        local latest_hash
        latest_hash=$(md5 -q "$latest" 2>/dev/null || md5sum "$latest" | cut -d' ' -f1) || latest_hash=""
        if [ -n "$latest_hash" ] && [ "$hash" = "$latest_hash" ]; then
            should_save=false
            log "本地scorer_cloud.py无变化，跳过"
        fi
    fi
    if [ "$should_save" = true ]; then
        cp "$LOCAL_SCORER" "$VERSION_DIR/scorer_cloud_${ts}.py"
        log "✅ 已保存版本: scorer_cloud_${ts}.py (hash=$hash)"
    fi

    # 同步进化版
    if [ -f "$LOCAL_EVOLUTION" ]; then
        local evo_hash
        evo_hash=$(md5 -q "$LOCAL_EVOLUTION" 2>/dev/null || md5sum "$LOCAL_EVOLUTION" | cut -d' ' -f1)
        local evo_latest
        evo_latest=$(ls -t "$VERSION_DIR"/scorer_evolution_*.py 2>/dev/null | head -1) || true
        local should_save_evo=true
        if [ -n "$evo_latest" ] && [ -f "$evo_latest" ]; then
            local latest_evo_hash
            latest_evo_hash=$(md5 -q "$evo_latest" 2>/dev/null || md5sum "$evo_latest" | cut -d' ' -f1) || latest_evo_hash=""
            if [ -n "$latest_evo_hash" ] && [ "$evo_hash" = "$latest_evo_hash" ]; then
                should_save_evo=false
                log "本地scorer_evolution.py无变化，跳过"
            fi
        fi
        if [ "$should_save_evo" = true ]; then
            cp "$LOCAL_EVOLUTION" "$VERSION_DIR/scorer_evolution_${ts}.py"
            log "✅ 已保存进化版: scorer_evolution_${ts}.py (hash=$evo_hash)"
        fi
    fi

    # 清理旧版本
    clean_old
}

# === 列出所有版本 ===
list_versions() {
    echo -e "\n${CYAN}📋 scorer_cloud.py 版本历史${NC}"
    echo "────────────────────────────────────────────"
    local count=0
    local files
    files=$(ls -t "$VERSION_DIR"/scorer_cloud_*.py 2>/dev/null)
    if [ -z "$files" ]; then
        echo "  没有保存的版本"
    else
        local i=1
        for f in $files; do
            local name
            name=$(basename "$f")
            local size
            size=$(wc -c < "$f" | tr -d ' ')
            local lines
            lines=$(wc -l < "$f" | tr -d ' ')
            printf "  %2d. %s  (%d bytes, %d 行)\n" "$i" "$name" "$size" "$lines"
            i=$((i+1))
        done
    fi

    echo -e "\n${CYAN}📋 scorer_evolution.py 版本历史${NC}"
    echo "────────────────────────────────────────────"
    files=$(ls -t "$VERSION_DIR"/scorer_evolution_*.py 2>/dev/null)
    if [ -z "$files" ]; then
        echo "  没有保存的版本"
    else
        local i=1
        for f in $files; do
            local name
            name=$(basename "$f")
            local size
            size=$(wc -c < "$f" | tr -d ' ')
            printf "  %2d. %s  (%d bytes)\n" "$i" "$name" "$size"
            i=$((i+1))
        done
    fi
}

# === 对比本地vs云端（备份仓库） ===
diff_with_cloud() {
    echo -e "\n${CYAN}🔍 本地 vs 云端 (GitHub) 对比${NC}"
    echo "────────────────────────────────────────────"

    local cloud_scorer="$HOME/scorer-reports-backup/scorer_cloud.py"
    if [ ! -f "$cloud_scorer" ]; then
        warn "云端备份文件不存在，请先运行 backup_repo.sh"
        return
    fi

    if [ ! -f "$LOCAL_SCORER" ]; then
        warn "本地 $LOCAL_SCORER 不存在"
        return
    fi

    local local_hash
    local_hash=$(md5 -q "$LOCAL_SCORER" 2>/dev/null || md5sum "$LOCAL_SCORER" | cut -d' ' -f1)
    local cloud_hash
    cloud_hash=$(md5 -q "$cloud_scorer" 2>/dev/null || md5sum "$cloud_scorer" | cut -d' ' -f1)

    if [ "$local_hash" = "$cloud_hash" ]; then
        echo -e "${GREEN}  ✅ 完全一致${NC}"
        echo "     本地: $LOCAL_SCORER"
        echo "     云端: $cloud_scorer"
    else
        echo -e "${YELLOW}  ⚠️ 版本不一致！${NC}"
        echo "     本地: $LOCAL_SCORER (hash=$local_hash)"
        echo "     云端: $cloud_scorer (hash=$cloud_hash)"
        echo ""
        echo "  差异对比:"
        diff "$LOCAL_SCORER" "$cloud_scorer" | head -60
    fi
}

# === 恢复指定版本 ===
restore_version() {
    local target="$1"
    local version_file
    version_file=$(ls -t "$VERSION_DIR"/scorer_cloud_*.py 2>/dev/null | sed -n "${target}p")
    if [ -z "$version_file" ]; then
        err "未找到版本 #$target，使用 --list 查看可用版本"
    fi

    echo -e "${YELLOW}⚠️  即将恢复 $(basename "$version_file") 到 $LOCAL_SCORER${NC}"
    echo "  当前文件将被覆盖"
    read -r -p "  确认？(y/N): " confirm
    if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
        echo "已取消"
        exit 0
    fi

    # 备份当前版本
    local backup_name="scorer_cloud_BEFORE_RESTORE_$(date '+%Y%m%d_%H%M%S').py"
    cp "$LOCAL_SCORER" "$VERSION_DIR/$backup_name"
    log "💾 已备份当前版本为 $backup_name"

    # 恢复
    cp "$version_file" "$LOCAL_SCORER"
    log "✅ 已恢复 #$target: $(basename "$version_file")"
}

# === 清理旧版本 ===
clean_old() {
    local kept=0
    for f in $(ls -t "$VERSION_DIR"/scorer_cloud_*.py 2>/dev/null); do
        kept=$((kept+1))
        if [ "$kept" -gt "$RETENTION_COUNT" ]; then
            rm -f "$f"
            log "🧹 删除旧版本: $(basename "$f")"
        fi
    done
    kept=0
    for f in $(ls -t "$VERSION_DIR"/scorer_evolution_*.py 2>/dev/null); do
        kept=$((kept+1))
        if [ "$kept" -gt "$RETENTION_COUNT" ]; then
            rm -f "$f"
            log "🧹 删除旧版本: $(basename "$f")"
        fi
    done
}

# === 设置定时同步 ===
setup_cron() {
    local cron_job="0 10 * * * $HOME/Documents/精益智能工厂/08_数字化与自动化/备份与恢复/manage_scorer_version.sh >> /tmp/scorer_version.log 2>&1"
    if crontab -l 2>/dev/null | grep -q "manage_scorer_version"; then
        warn "crontab中已有该条目"
        crontab -l 2>/dev/null | grep "manage_scorer_version"
    else
        (crontab -l 2>/dev/null; echo "$cron_job") | crontab -
        log "✅ 已添加crontab: 每天10:00自动同步scorer版本"
    fi
}

# === 主入口 ===
case "${1:-}" in
    --list|-l)
        list_versions
        ;;
    --diff-local|-d)
        diff_with_cloud
        ;;
    --restore|-r)
        [ -z "${2:-}" ] && err "请指定版本号（--list查看）"
        restore_version "$2"
        ;;
    --clean|-c)
        clean_old
        log "🧹 清理完成"
        ;;
    --setup-cron)
        setup_cron
        ;;
    --help|-h)
        echo "用法: $0 [选项]"
        echo "  (无参数)       同步本地scorer版本到版本库"
        echo "  --list, -l     列出所有版本"
        echo "  --diff-local   对比本地与云端版本"
        echo "  --restore N    恢复第N个版本"
        echo "  --clean        手动清理旧版本"
        echo "  --setup-cron   添加crontab定时同步"
        echo "  --help         显示此帮助"
        exit 0
        ;;
    *)
        sync_local
        ;;
esac
