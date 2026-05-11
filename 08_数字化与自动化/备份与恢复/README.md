# 🛡️ 评分师系统 · 故障恢复指南 (SOP)

> **版本：** 1.0  
> **创建日期：** 2026-05-11  
> **维护人：** Orion（总指挥）  
> **覆盖范围：** 精益智能工厂诊断系统 Phase 1（免费诊断流水线）

---

## 📋 系统架构总览

```
飞书多维表格 ←[API]→ scorer_cloud.py ←[commit+push]→ GitHub:scorer-reports → GitHub Pages
                            ↓ (cron 每30min / repository_dispatch)
                        GitHub Actions (scorer.yml)
```

**关键依赖：**
| 组件 | 位置 | 凭据/密钥 |
|------|------|-----------|
| 飞书App | 飞书开发者后台 → 思派工业评分师 | App ID + App Secret |
| 多维表格 | `VU3hbjRyuabLhAseoK3ckzOzndg` / `tblofr6TCloHk5Zb` | 包含在表格本身 |
| GitHub仓库 | [Kevinhanmin/scorer-reports](https://github.com/Kevinhanmin/scorer-reports) | GITHUB_TOKEN（自动） |
| GitHub Pages | https://kevinhanmin.github.io/scorer-reports/ | 公开 |
| GitHub Secrets | `FEISHU_APP_ID`, `FEISHU_APP_SECRET`, `BITABLE_APP_TOKEN`, `TABLE_ID`, `FOUNDER_OPEN_ID`, `REPO_URL` | GH中设置 |

**工作流文件：** `.github/workflows/scorer.yml`

---

## 🚨 故障场景恢复流程

### 场景1: GitHub Actions 运行失败

**现象：** 飞书问卷有提交，但报告未生成；或 Action 运行日志显示红色 ❌

**恢复步骤：**

1. **检查问题原因**
   ```
   打开 https://github.com/Kevinhanmin/scorer-reports/actions
   点击最新的失败运行 → 查看日志
   ```

2. **常见原因与解决：**
   
   | 错误类型 | 原因 | 解决方案 |
   |---------|------|----------|
   | `Token失败` 或 `API failed` | 飞书App Secret过期/错误 | 在GitHub Secrets中更新 `FEISHU_APP_ID` 和 `FEISHU_APP_SECRET` |
   | `缺少环境变量: ...` | Secrets未正确设置 | 检查仓库 Settings → Secrets and variables → Actions |
   | 超时 | 网络问题 | 手动触发重新运行（点右上角 "Re-run all jobs"） |
   | `git push` 失败 | 仓库权限问题 | 检查 `GITHUB_TOKEN` 是否有 `contents: write` 权限 |

3. **手动触发重试**
   ```bash
   # 方式1: 在GitHub Actions页面点击 "Re-run all jobs"
   # 方式2: 通过API
   curl -X POST \
     -H "Authorization: Bearer <GH_TOKEN>" \
     -H "Accept: application/vnd.github.v3+json" \
     https://api.github.com/repos/Kevinhanmin/scorer-reports/actions/workflows/scorer.yml/dispatches \
     -d '{"ref":"main"}'
   ```

4. **本地执行（紧急绕过Actions）**
   ```bash
   cd /path/to/scorer-reports
   export FEISHU_APP_ID="xxx"
   export FEISHU_APP_SECRET="xxx"
   export BITABLE_APP_TOKEN="VU3hbjRyuabLhAseoK3ckzOzndg"
   export TABLE_ID="tblofr6TCloHk5Zb"
   python3 scorer_cloud.py
   git add reports/ && git commit -m "📊 紧急手动报告" && git push
   ```

---

### 场景2: 飞书多维表格被误改/删除

**恢复步骤：**

1. **检查飞书多维表格回收站**
   ```
   飞书 → 多维表格空间 → ... → 回收站
   找到被删除的表 → 恢复
   ```

2. **从本地备份恢复**
   ```bash
   # 找到最近的备份
   ls -lt ~/Documents/精益智能工厂/08_数字化与自动化/备份与恢复/feishu_exports/*/records_*.json | head -5
   
   # 使用备份数据重新导入
   # 注意：需要手动通过飞书导入功能（多维表格 → 导入 → JSON/CSV）
   ```

3. **重建字段结构**
   ```bash
   # 备份中的字段定义文件
   ls -lt ~/Documents/精益智能工厂/08_数字化与自动化/备份与恢复/feishu_exports/*/fields_*.json | head -3
   ```
   对照字段定义文件，在飞书多维表格中重建字段。

4. **更新Graphic AI/自动化后重新连接**
   重建后，检查飞书自动化（webhook → GitHub）是否仍然有效。

---

### 场景3: GitHub仓库被误删/损坏

**恢复步骤：**

1. **从本地备份恢复**
   ```bash
   # 检查本地备份是否存在
   ls -la ~/scorer-reports-backup/
   
   # 创建一个新的空仓库（在GitHub新建 repo 同名）
   
   # 从本地备份推送到新仓库
   cd ~/scorer-reports-backup
   git remote set-url origin https://github.com/Kevinhanmin/scorer-reports.git
   git push --all --force
   git push --tags --force
   ```

2. **重新启用GitHub Pages**
   ```
   仓库 → Settings → Pages
   选择 "Deploy from a branch" → main → / (root)
   保存
   ```

3. **设置GitHub Secrets**
   重新设置以下 Secrets（在仓库 Settings → Secrets and variables → Actions）：
   - `FEISHU_APP_ID`
   - `FEISHU_APP_SECRET`
   - `BITABLE_APP_TOKEN` → `VU3hbjRyuabLhAseoK3ckzOzndg`
   - `TABLE_ID` → `tblofr6TCloHk5Zb`
   - `FOUNDER_OPEN_ID` → `ou_654b4ab922a747e21af74eaa4884a914`
   - `REPO_URL` → `https://github.com/Kevinhanmin/scorer-reports`

4. **验证工作流**
   手动触发一次 Action 确认正常。

---

### 场景4: GitHub Actions 配置丢失（scorer.yml被删）

**恢复步骤：**

1. **从本地备份恢复工作流文件**
   ```bash
   # 从备份中复制
   cp ~/Documents/精益智能工厂/08_数字化与自动化/备份与恢复/workflow_backup/scorer.yml \
      ~/scorer-reports-backup/.github/workflows/scorer.yml
   
   # 或从scorer版本目录（工作流配置内嵌在仓库中）
   git -C ~/scorer-reports-backup show HEAD:.github/workflows/scorer.yml
   ```

2. **如无备份，直接使用以下内容重建**
   ```yaml
   # .github/workflows/scorer.yml 标准内容：
   name: 评分师云端报告生成

   on:
     repository_dispatch:
       types: [feishu-new-record]
     schedule:
       - cron: '*/30 * * * *'
     workflow_dispatch:

   permissions:
     contents: write

   jobs:
     score-and-report:
       runs-on: ubuntu-latest
       steps:
         - uses: actions/checkout@v4
           with:
             token: ${{ secrets.GITHUB_TOKEN }}
         - uses: actions/setup-python@v5
           with:
             python-version: '3.11'
         - name: 运行评分师
           env:
             FEISHU_APP_ID: ${{ secrets.FEISHU_APP_ID }}
             FEISHU_APP_SECRET: ${{ secrets.FEISHU_APP_SECRET }}
             BITABLE_APP_TOKEN: ${{ secrets.BITABLE_APP_TOKEN }}
             TABLE_ID: ${{ secrets.TABLE_ID }}
             FOUNDER_OPEN_ID: ${{ secrets.FOUNDER_OPEN_ID }}
             REPO_URL: ${{ secrets.REPO_URL }}
           run: python scorer_cloud.py || echo "⚠️ 评分运行有警告"
         - name: 提交报告到仓库
           run: |
             git config user.name "评分师机器人"
             git config user.email "scorer@bot.com"
             git add reports/
             if git diff --staged --quiet; then
               echo "没有新报告"
             else
               git commit -m "📊 自动诊断报告 $(date +'%Y-%m-%d %H:%M')"
               git push
             fi
         - name: 发送飞书通知
           env:
             FEISHU_APP_ID: ${{ secrets.FEISHU_APP_ID }}
             FEISHU_APP_SECRET: ${{ secrets.FEISHU_APP_SECRET }}
             FOUNDER_OPEN_ID: ${{ secrets.FOUNDER_OPEN_ID }}
           run: |
             sleep 30
             python scorer_cloud.py --notify || echo "⚠️ 通知发送有警告"
   ```

3. **提交并推送**
   ```bash
   cd ~/scorer-reports-backup/.github/workflows
   git add scorer.yml
   git commit -m "🔄 恢复工作流配置"
   git push
   ```

---

### 场景5: GitHub Pages 无法访问

**现象：** 报告链接返回 404 或 GitHub Pages 显示 404

**恢复步骤：**

1. **检查Pages设置**
   ```
   仓库 → Settings → Pages
   确认 Source 为 "Deploy from a branch" → main → / (root)
   确认没有选错分支或目录
   ```

2. **检查GitHub Actions部署状态**
   ```
   仓库 → Actions
   查看最新运行是否成功
   Pages需要Action运行成功才更新
   ```

3. **强制触发生成**
   ```
   仓库 → Actions → 评分师云端报告生成 → Run workflow → Run
   ```

4. **检查 index.html 是否在根目录**
   确认仓库根目录下有 `index.html` 文件。

---

### 场景6: 本地文件丢失（scorer_cloud.py 被误删）

**恢复步骤：**

1. **从版本历史恢复**
   ```bash
   # 列出可用版本
   ~/Documents/精益智能工厂/08_数字化与自动化/备份与恢复/manage_scorer_version.sh --list
   
   # 恢复最新版本
   ~/Documents/精益智能工厂/08_数字化与自动化/备份与恢复/manage_scorer_version.sh --restore 1
   ```

2. **从GitHub下载**
   ```bash
   curl -o ~/scorer_cloud.py \
     https://raw.githubusercontent.com/Kevinhanmin/scorer-reports/main/scorer_cloud.py
   ```

3. **从本地备份仓库恢复**
   ```bash
   cp ~/scorer-reports-backup/scorer_cloud.py ~/scorer_cloud.py
   ```

---

## ⏰ 定期维护检查清单

建议 **每周一上午** 快速检查以下项目：

| 检查项 | 如何检查 | 正常标准 |
|--------|---------|----------|
| ✅ GitHub Actions状态 | 仓库 Actions 标签页 | 最近一次运行绿色 ✅ |
| ✅ GitHub Pages | 访问 https://kevinhanmin.github.io/scorer-reports/ | 页面正常加载，显示最近报告 |
| ✅ 本地备份仓库 | `ls -la ~/scorer-reports-backup/` | 目录存在，内有 `.git` |
| ✅ 飞书App Token | 飞书开发者后台 | App Secret 未过期 |
| ✅ 磁盘空间 | `df -h ~` | 剩余 > 5GB |
| ✅ 报告数量 | `find ~/scorer-reports-backup/reports/ -name '*.html' \| wc -l` | 数量正常增长 |

---

## 🔄 备份策略总览

| 备份项目 | 频率 | 保留策略 | 工具 |
|----------|------|----------|------|
| GitHub仓库本地镜像 | 每日 | 保留30个版本标签 | `backup_repo.sh` |
| scorer_cloud.py 版本 | 每日/变更时 | 保留20个版本 | `manage_scorer_version.sh` |
| 飞书数据导出 | 每周 | 保留30天 | `export_feishu_data.py` |
| 工作流配置文件 | 随Git仓库自动备份 | 永久（Git历史） | — |

**定时任务配置（crontab）：**
```bash
# 每天9:00 GitHub仓库备份
0 9 * * * /Users/hanmin/Documents/精益智能工厂/08_数字化与自动化/备份与恢复/backup_repo.sh --cron >> /tmp/repo_backup.log 2>&1

# 每天10:00 scorer版本同步
0 10 * * * /Users/hanmin/Documents/精益智能工厂/08_数字化与自动化/备份与恢复/manage_scorer_version.sh >> /tmp/scorer_version.log 2>&1

# 每周一15:00 飞书数据导出 + 全量备份
0 15 * * 1 /Users/hanmin/Documents/精益智能工厂/08_数字化与自动化/备份与恢复/backup_all.sh --skip-feishu >> /tmp/backup_all.log 2>&1
```

---

## 📁 备份文件清单

```
08_数字化与自动化/备份与恢复/
├── backup_repo.sh              # GitHub仓库本地备份
├── manage_scorer_version.sh    # scorer_cloud.py 版本管理器
├── export_feishu_data.py       # 飞书多维表格数据导出
├── backup_all.sh               # 全量备份编排脚本
├── README.md                   # 本文件（故障恢复指南）
├── backup_report.md            # 每次备份生成的报告（自动覆盖）
├── scorer_versions/            # scorer.py 版本历史
│   ├── scorer_cloud_20260511_135132.py
│   └── scorer_evolution_20260511_135132.py
└── feishu_exports/             # 飞书数据导出
    └── YYYYMMDD/
        ├── fields_*.json       # 字段定义
        ├── records_*.json      # 完整数据（JSON）
        ├── records_*.csv       # 评分摘要（CSV）
        └── manifest_*.json     # 导出清单
```

---

## 📎 关键参考链接

| 项目 | 链接 |
|------|------|
| GitHub仓库 | https://github.com/Kevinhanmin/scorer-reports |
| GitHub Pages | https://kevinhanmin.github.io/scorer-reports/ |
| GitHub Actions | https://github.com/Kevinhanmin/scorer-reports/actions |
| 飞书开发者后台 | https://open.feishu.cn/app |
| 飞书多维表格 | https://bytedance.feishu.cn/base/VU3hbjRyuabLhAseoK3ckzOzndg |
| 本地备份根目录 | `~/Documents/精益智能工厂/08_数字化与自动化/备份与恢复/` |
| GitHub镜像 | `~/scorer-reports-backup/` |
| 本地scorer | `~/scorer_cloud.py` |
| 本地进化版 | `~/scorer_evolution.py` |

---

> **最后更新：** 2026-05-11  
> **下次维护检查：** 建议每周一  
> **问题反馈：** 联系创始人 Kevin（飞书 open_id: ou_654b4ab922a747e21af74eaa4884a914）
