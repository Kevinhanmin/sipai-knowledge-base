#!/usr/bin/env python3
"""
思派工业 · 每日行业快讯 CLI 生成器
==================================
轻量版 — 不依赖外部搜索API，使用 Hermes Agent 的 web_search 能力。

两种模式：
  1. 内容师手动生成：python3 daily_newsletter.py --interactive
  2. 自动生成（需配置）：python3 daily_newsletter.py --auto

运行后：
  - 生成一个 Markdown 文件到 ../每日快讯/ 目录
  - 文件命名：每日快讯_YYYYMMDD.md
  - 带 YAML frontmatter，status=待审核
"""

import argparse
import os
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

DEFAULT_OUTPUT_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "每日快讯"
)
WEEKDAY_CN = ["一", "二", "三", "四", "五", "六", "日"]

# 快讯标准化模板（4大板块）
SECTIONS = {
    "政策动态": {
        "icon": "🏛️",
        "placeholder": "制造业政策动态（技改补贴、数字化转型扶持、绿色制造等）",
        "fields": ["标题", "要点", "影响", "来源"],
    },
    "行业案例": {
        "icon": "🏭",
        "placeholder": "精益生产/智能工厂落地案例（客户故事、行业标杆）",
        "fields": ["企业", "做法", "结果", "启示"],
    },
    "工具方法": {
        "icon": "🛠️",
        "placeholder": "精益工具/OEE/TPM/SMED/VSM等方法论实战分享",
        "fields": ["工具名称", "适用场景", "核心要点", "实施步骍"],
    },
    "趋势洞察": {
        "icon": "📊",
        "placeholder": "行业趋势分析、市场数据、技术发展方向",
        "fields": ["趋势", "数据支撑", "影响分析"],
    },
}


def generate_template(output_dir, target_date=None):
    """生成空白模板文件"""
    if target_date:
        date_obj = datetime.strptime(target_date, "%Y-%m-%d")
    else:
        date_obj = datetime.now()

    date_str = date_obj.strftime("%Y年%m月%d日")
    weekday = WEEKDAY_CN[date_obj.weekday()]
    filename = f"每日快讯_{date_obj.strftime('%Y%m%d')}.md"
    filepath = os.path.join(output_dir, filename)

    lines = []
    lines.append("---")
    lines.append(f"tags: [每日快讯, 新闻, 行业动态]")
    lines.append(f"date: {date_str}")
    lines.append(f"weekday: {weekday}")
    lines.append("status: 待审核")
    lines.append("---")
    lines.append("")
    lines.append(f"# 📰 精益智能工厂 · 每日行业快讯")
    lines.append("")
    lines.append(f"**{date_str} · 星期{weekday}**")
    lines.append("")
    lines.append("> 聚焦制造业前沿动态，为工厂管理者提供每日资讯精选")
    lines.append("")
    lines.append("---")
    lines.append("")

    for section_name, section_info in SECTIONS.items():
        icon = section_info["icon"]
        lines.append(f"## {icon} {section_name}")
        lines.append("")
        lines.append(f"> {section_info['placeholder']}")
        lines.append("")

        fields = section_info["fields"]
        lines.append("### [请输入标题]")
        for field in fields:
            lines.append(f"- **{field}**：")
        lines.append("")
        lines.append("### [可选第二条]")
        for field in fields:
            lines.append(f"- **{field}**：")
        lines.append("")
        lines.append("---")
        lines.append("")

    # 老K点评
    lines.append("## 💡 老K点评")
    lines.append("")
    lines.append("> *（待补充）*")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 📌 今日互动")
    lines.append("")
    lines.append("**您对今天的内容有什么看法？欢迎留言讨论👇**")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("*本快讯由思派工业智能研究中心 · 内容师自动收集生成*")
    lines.append("*审核人：诊断师*")
    lines.append("*发布平台：公众号/视频号*")
    lines.append("")

    content = "\n".join(lines)

    os.makedirs(output_dir, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

    return filepath


def generate_json_output(target_date=None):
    """生成JSON格式的输出（给内容师使用）"""
    if target_date:
        date_obj = datetime.strptime(target_date, "%Y-%m-%d")
    else:
        date_obj = datetime.now()

    date_str = date_obj.strftime("%Y-%m-%d")
    weekday = WEEKDAY_CN[date_obj.weekday()]

    output = {
        "action": "生成每日快讯",
        "date": date_str,
        "weekday": f"星期{weekday}",
        "template": True,
        "sections": list(SECTIONS.keys()),
        "review_needed": True,
        "reviewer": "诊断师",
        "publish_platforms": ["公众号", "视频号"],
        "status": "待审核",
    }
    return json.dumps(output, ensure_ascii=False, indent=2)


def main():
    parser = argparse.ArgumentParser(
        description="思派工业 · 每日行业快讯生成器"
    )
    parser.add_argument(
        "--date",
        type=str,
        default=None,
        help="目标日期 (YYYY-MM-DD)，默认今天",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=DEFAULT_OUTPUT_DIR,
        help=f"输出目录 (默认: {DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument(
        "--template",
        action="store_true",
        help="仅生成空白模板（不填充内容）",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="输出JSON格式信息（供内容师使用）",
    )
    args = parser.parse_args()

    if args.json:
        print(generate_json_output(args.date))
        return

    filepath = generate_template(args.output_dir, args.date)
    print(f"✅ 模板已生成: {filepath}")


if __name__ == "__main__":
    main()
