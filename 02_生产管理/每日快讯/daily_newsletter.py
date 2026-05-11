#!/usr/bin/env python3
"""
思派工业 · 每日行业快讯 CLI 生成器
==================================
工作流：内容师 Manual OR Cron Auto

用法：
  python3 daily_newsletter.py --template   # 生成空白模板（给内容师手动填充）
  python3 daily_newsletter.py --json       # 输出JSON信息（供Agent使用）

输出文件：~/Documents/精益智能工厂/02_生产管理/每日快讯/每日快讯_YYYYMMDD.md
"""

import argparse
import json
import os
from datetime import datetime

OUTPUT_DIR = os.path.expanduser(
    "~/Documents/精益智能工厂/02_生产管理/每日快讯"
)
WEEKDAY_CN = ["一", "二", "三", "四", "五", "六", "日"]

SECTIONS_CONFIG = {
    "政策动态": {
        "icon": "🏛️",
        "desc": "制造业政策动态（技改补贴、数字化转型扶持、绿色制造等）",
        "fields": ["标题", "要点", "影响", "来源"],
    },
    "行业案例": {
        "icon": "🏭",
        "desc": "精益生产/智能工厂落地案例（客户故事、行业标杆）",
        "fields": ["企业", "做法", "结果", "启示"],
    },
    "工具方法": {
        "icon": "🛠️",
        "desc": "精益工具/OEE/TPM/SMED/VSM等方法论实战分享",
        "fields": ["工具名称", "适用场景", "核心要点", "实施步骤"],
    },
    "趋势洞察": {
        "icon": "📊",
        "desc": "行业趋势分析、市场数据、技术发展方向",
        "fields": ["趋势", "数据支撑", "影响分析"],
    },
}


def generate_template(target_date=None):
    """生成空白模板文件"""
    date_obj = (
        datetime.strptime(target_date, "%Y-%m-%d")
        if target_date
        else datetime.now()
    )
    date_str = date_obj.strftime("%Y年%m月%d日")
    weekday = WEEKDAY_CN[date_obj.weekday()]
    filename = f"每日快讯_{date_obj.strftime('%Y%m%d')}.md"
    filepath = os.path.join(OUTPUT_DIR, filename)

    lines = [
        "---",
        "tags: [每日快讯, 新闻, 行业动态]",
        f"date: {date_str}",
        f"weekday: {weekday}",
        "status: 待审核",
        "---",
        "",
        f"# 📰 精益智能工厂 · 每日行业快讯",
        "",
        f"**{date_str} · 星期{weekday}**",
        "",
        "> 聚焦制造业前沿动态，为工厂管理者提供每日资讯精选",
        "",
        "---",
        "",
    ]

    for name, cfg in SECTIONS_CONFIG.items():
        lines.extend([
            f"## {cfg['icon']} {name}",
            "",
            f"> {cfg['desc']}",
            "",
            "### [请输入标题]",
        ])
        for f in cfg["fields"]:
            lines.append(f"- **{f}**：")
        lines.extend(["", "### [可选第二条]"])
        for f in cfg["fields"]:
            lines.append(f"- **{f}**：")
        lines.extend(["", "---", ""])

    lines.extend([
        "## 💡 老K点评",
        "",
        "> *（待补充）*",
        "",
        "---",
        "",
        "## 📌 今日互动",
        "",
        "**您对今天的内容有什么看法？欢迎留言讨论👇**",
        "",
        "---",
        "",
        "*本快讯由思派工业智能研究中心 · 内容师自动收集生成*",
        "*审核人：诊断师*",
        "*发布平台：公众号/视频号*",
        "",
    ])

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return filepath


def main():
    parser = argparse.ArgumentParser(description="思派工业 · 每日行业快讯生成器")
    parser.add_argument("--date", type=str, default=None, help="目标日期 (YYYY-MM-DD)")
    parser.add_argument("--template", action="store_true", help="生成空白模板")
    parser.add_argument("--json", action="store_true", help="输出JSON信息")
    args = parser.parse_args()

    if args.json:
        date_obj = (
            datetime.strptime(args.date, "%Y-%m-%d")
            if args.date
            else datetime.now()
        )
        print(json.dumps({
            "action": "生成每日快讯模板",
            "date": date_obj.strftime("%Y-%m-%d"),
            "weekday": f"星期{WEEKDAY_CN[date_obj.weekday()]}",
            "sections": list(SECTIONS_CONFIG.keys()),
            "review_needed": True,
            "reviewer": "诊断师",
            "publish_platforms": ["公众号", "视频号"],
            "status": "待审核",
            "output_dir": OUTPUT_DIR,
        }, ensure_ascii=False, indent=2))
        return

    filepath = generate_template(args.date)
    print(f"✅ 模板已生成: {filepath}")


if __name__ == "__main__":
    main()
