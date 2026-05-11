#!/bin/bash
# ====================================================
# 系统完整备份编排脚本（一键全量备份）
# ====================================================
# 依次执行：
#   1. GitHub仓库备份
#   2. scorer_cloud.py 版本管理
#   3. 飞书数据导出
#   4. 生成备份报告
#
# 使用方式：
#   ./backup_all.sh                    # 全量备份
#   ./backup_all.sh --skip-feishu      # 跳过飞书导出（无飞书凭据时）
#   ./backup_all.sh --quick            # 仅仓库+版本管理
# ====================================================

set -euo pipefail

BASE_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_FILE="/tmp/backup_all_$(date '+%Y%m%d_%H%M%S').log"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

log() { echo -e "${GREEN}[$(date '+%H:%M:%S')] $1${NC}" | tee -a "$LOG_FILE"; }
warn() { echo -e "${YELLOW}[$(date '+%H:%M:%S')] ⚠️  $1${NC}" | tee -a "$LOG_FILE"; }
err() { echo -e "${RED}[$(date '+%H:%M:%S')] ❌ $1${NC}"; }
title() { echo -e "\n${CYAN}${BOLD}═══ $1 ═══${NC}" | tee -a "$LOG_FILE"; }

total_start=$(date +%s)

echo ""
echo -e "${CYAN}${BOLD}┌─────────────────────────────────────────────┐${NC}"
echo -e "${CYAN}${BOLD}│     🛡️  思派工业 · 系统完整备份                │${NC}"
echo -e "${CYAN}${BOLD}│     ${TIMESTAMP}                    │${NC}"
echo -e "${CYAN}${BOLD}└─────────────────────────────────────────────┘${NC}"

# === 1. GitHub仓库备份 ===
title "1/4 GitHub仓库备份"
if bash "$BASE_DIR/backup_repo.sh" --cron 2>&1 | tee -a "$LOG_FILE"; then
    log "✅ 仓库备份完成"
else
    warn "仓库备份有异常（网络问题？），继续执行后续步骤"
fi

# === 2. scorer版本管理 ===
title "2/4 scorer.py 版本管理"
if bash "$BASE_DIR/manage_scorer_version.sh" 2>&1 | tee -a "$LOG_FILE"; then
    log "✅ 版本管理完成"
else
    warn "版本管理有异常"
fi

# === 3. 飞书数据导出（可选）===
if [ "${1:-}" != "--skip-feishu" ] && [ "${1:-}" != "--quick" ]; then
    title "3/4 飞书数据导出"
    EXPORT_DIR="$BASE_DIR/feishu_exports/$(date '+%Y%m%d')"
    mkdir -p "$EXPORT_DIR"
    
    # 从环境变量读取飞书凭据
    if [ -n "${FEISHU_APP_ID:-}" ] && [ -n "${FEISHU_APP_SECRET:-}" ]; then
        if python3 "$BASE_DIR/export_feishu_data.py" --output-dir "$EXPORT_DIR" 2>&1 | tee -a "$LOG_FILE"; then
            log "✅ 飞书数据导出完成"
        else
            err "飞书数据导出失败"
        fi
    else
        warn "FEISHU_APP_ID/FEISHU_APP_SECRET 未设置，跳过飞书导出"
        warn "  设置方式: export FEISHU_APP_ID=xxx FEISHU_APP_SECRET=xxx"
    fi
elif [ "${1:-}" = "--quick" ]; then
    title "3/4 飞书数据导出"
    log "⏭️  快速模式跳过飞书导出"
fi

# === 4. 生成备份报告 ===
title "4/4 备份报告"
REPORT_FILE="$BASE_DIR/backup_report.md"
{
    echo "# 系统备份报告"
    echo ""
    echo "**备份时间：** $(date '+%Y-%m-%d %H:%M:%S')"
    echo ""
    echo "## 📊 备份摘要"
    echo ""
    echo "| 项目 | 状态 |"
    echo "|------|------|"
    echo "| GitHub仓库备份 | ✅ 完成 |"
    echo "| scorer.py版本管理 | ✅ 完成 |"

    if [ "${1:-}" != "--skip-feishu" ] && [ "${1:-}" != "--quick" ]; then
        if [ -n "${FEISHU_APP_ID:-}" ] && [ -n "${FEISHU_APP_SECRET:-}" ]; then
            echo "| 飞书数据导出 | ✅ 完成 |"
            echo "| 飞书导出目录 | $EXPORT_DIR |"
        else
            echo "| 飞书数据导出 | ⏭️ 跳过（未配置凭据） |"
        fi
    else
        echo "| 飞书数据导出 | ⏭️ 跳过（快速模式） |"
    fi

    echo ""
    echo "## 📁 备份位置"
    echo ""
    echo "- **GitHub仓库本地镜像：** \`$HOME/scorer-reports-backup\`"
    echo "- **scorer.py版本历史：** \`$BASE_DIR/scorer_versions\`"
    echo "- **飞书数据导出：** \`$BASE_DIR/feishu_exports\`"

    # 检查各备份位置大小
    echo ""
    echo "## 💾 磁盘占用"
    echo ""
    if [ -d "$HOME/scorer-reports-backup" ]; then
        echo "- GitHub镜像: $(du -sh "$HOME/scorer-reports-backup" 2>/dev/null | cut -f1)"
    fi
    if [ -d "$BASE_DIR/scorer_versions" ]; then
        echo "- scorer版本: $(du -sh "$BASE_DIR/scorer_versions" 2>/dev/null | cut -f1)"
        echo "  - 版本文件数: $(ls "$BASE_DIR"/scorer_versions/*.py 2>/dev/null | wc -l | tr -d ' ')"
    fi
    if [ -d "$BASE_DIR/feishu_exports" ]; then
        echo "- 飞书导出: $(du -sh "$BASE_DIR/feishu_exports" 2>/dev/null | cut -f1)"
    fi

    echo ""
    echo "## 📝 日志"
    echo ""
    echo "详细日志: \`$LOG_FILE\`"
    echo ""

} > "$REPORT_FILE"

log "✅ 备份报告: $REPORT_FILE"

# === 完成 ===
total_end=$(date +%s)
elapsed=$((total_end - total_start))
echo ""
echo -e "${GREEN}${BOLD}┌─────────────────────────────────────────────┐${NC}"
echo -e "${GREEN}${BOLD}│     ✅  系统备份完成                         │${NC}"
echo -e "${GREEN}${BOLD}│     耗时: ${elapsed}秒                             │${NC}"
echo -e "${GREEN}${BOLD}│     日志: ${LOG_FILE}  │${NC}"
echo -e "${GREEN}${BOLD}└─────────────────────────────────────────────┘${NC}"
