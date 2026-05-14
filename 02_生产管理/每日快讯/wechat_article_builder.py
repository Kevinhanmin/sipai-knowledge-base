#!/usr/bin/env python3
"""
思派工业 · 微信图文转换器
==========================
将每日行业快讯从 Markdown 格式转换为微信公众号图文素材格式。

用法：
  python3 wechat_article_builder.py --input 每日快讯_20260511.md     # 转换指定文件
  python3 wechat_article_builder.py --today                          # 转换今日快讯
  python3 wechat_article_builder.py --input 每日快讯_20260511.md --html  # 仅输出HTML预览
"""

import argparse
import os
import re
import sys
from datetime import datetime

OUTPUT_DIR = os.path.expanduser("~/Documents/精益智能工厂/02_生产管理/每日快讯")
WEEKDAY_CN = ["一", "二", "三", "四", "五", "六", "日"]


def read_markdown(filepath: str) -> tuple[dict, str]:
    """读取markdown快讯，返回 (yaml_frontmatter, body_content)"""
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # 解析 YAML frontmatter
    frontmatter = {}
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            yaml_text = parts[1].strip()
            for line in yaml_text.split("\n"):
                line = line.strip()
                if ":" in line:
                    k, v = line.split(":", 1)
                    frontmatter[k.strip()] = v.strip().strip('"').strip("'")
            body = parts[2].strip()
        else:
            body = content
    else:
        body = content

    return frontmatter, body


def convert_to_wechat_html(body: str) -> str:
    """将快讯正文转换为微信公众号兼容的HTML"""
    
    # 提取日期
    date_match = re.search(r'\*\*(\d{4}年\d{2}月\d{2}日).*?\*\*', body)
    date_str = date_match.group(1) if date_match else datetime.now().strftime("%Y年%m月%d日")

    # 提取 sections
    sections = []
    current_section = {"title": "", "icon": "", "items": []}
    
    for line in body.split("\n"):
        line_stripped = line.strip()
        
        # 检测 section 标题 (##)
        if line_stripped.startswith("## ") and any(icon in line_stripped for icon in ["🏛️", "🏭", "🛠️", "📊", "💡", "📌"]):
            if current_section["items"] or current_section["title"]:
                sections.append(current_section)
            icon_match = re.match(r'##\s*([^\s]+)\s+(.+)$', line_stripped)
            current_section = {
                "title": icon_match.group(2) if icon_match else line_stripped.replace("## ", ""),
                "icon": icon_match.group(1) if icon_match else "📌",
                "items": [],
            }
            continue
        
        # 检测子标题 (###)
        if line_stripped.startswith("### ") and current_section["title"]:
            sub_title = line_stripped.replace("### ", "").strip()
            current_section["items"].append({"sub_title": sub_title, "lines": []})
            continue
        
        # 普通内容
        if current_section["items"]:
            current_section["items"][-1]["lines"].append(line.rstrip())

    # 添加最后一个 section
    if current_section["title"]:
        sections.append(current_section)

    # 提取老K点评
    laoke_comment = ""
    for sec in sections:
        if "老K点评" in sec["title"]:
            for item in sec["items"]:
                for l in item["lines"]:
                    stripped = l.strip()
                    if stripped.startswith(">"):
                        laoke_comment += stripped.lstrip("> ").strip() + "\n"
            break

    # 构建HTML
    html_parts = [
        '<!DOCTYPE html>',
        '<html><head><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">',
        '<title>精益智能工厂 · 每日行业快讯</title>',
        '<style>',
        'body{font-family:-apple-system, "Microsoft YaHei", sans-serif;max-width:680px;margin:0 auto;padding:20px 16px;color:#333;line-height:1.8;font-size:16px}',
        '.header{text-align:center;padding:20px 0 10px;border-bottom:2px solid #2563eb;margin-bottom:20px}',
        '.header h1{font-size:22px;color:#2563eb;margin:0 0 8px}',
        '.header .date{color:#666;font-size:14px}',
        '.section-title{font-size:18px;font-weight:700;color:#1e293b;margin:24px 0 12px;padding:8px 12px;background:#f0f7ff;border-radius:6px;border-left:4px solid #2563eb}',
        '.item-title{font-size:16px;font-weight:700;color:#1e293b;margin:14px 0 6px;padding:6px 0}',
        '.item{background:#fafafa;border-radius:8px;padding:12px 14px;margin:8px 0 14px;border:1px solid #eee}',
        '.field-label{color:#2563eb;font-weight:600;font-size:14px}',
        '.field-content{color:#333;font-size:14px;line-height:1.6}',
        '.laoke{background:linear-gradient(135deg,#f0f9ff,#fef3c7);border-radius:10px;padding:18px 20px;margin:24px 0;border-left:6px solid #f59e0b;font-style:italic;font-size:15px;color:#333}',
        '.laoke-label{font-weight:700;color:#d97706;font-size:16px;margin-bottom:8px}',
        '.footer{text-align:center;color:#999;font-size:12px;padding:20px 0;border-top:1px solid #eee;margin-top:20px}',
        '.emoji-icon{font-size:22px}',
        'br{margin:4px 0}',
        '</style></head><body>',
    ]

    # Header
    html_parts.append(f'<div class="header">')
    html_parts.append(f'<h1>精益智能工厂 · 每日行业快讯</h1>')
    html_parts.append(f'<div class="date">{date_str}</div>')
    html_parts.append('</div>')

    # Sections
    for sec in sections:
        title = sec["title"]
        icon = sec["icon"]
        
        if "老K点评" in title:
            continue  # 单独处理
        if "今日互动" in title:
            continue  # 跳过互动部分（公众号不需要）

        html_parts.append(f'<div class="section-title">{icon} {title}</div>')

        for item in sec["items"]:
            sub_title = item.get("sub_title", "")
            lines = item.get("lines", [])
            
            if sub_title:
                html_parts.append(f'<div class="item-title">{sub_title}</div>')
            
            html_parts.append('<div class="item">')
            for line in lines:
                stripped = line.strip()
                if not stripped or stripped.startswith("---") or stripped.startswith(">"):
                    continue
                # 转换 Markdown 加粗为 HTML 加粗
                html_line = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', stripped)
                if "**" in html_line or "：" in html_line[:8]:
                    # 这是带标签的行
                    html_parts.append(f'<div><span class="field-label">{html_line.split("：")[0]}：</span>{html_line.split("：", 1)[1] if "：" in html_line else ""}</div>')
                else:
                    html_parts.append(f'<div class="field-content">{html_line}</div>')
            html_parts.append('</div>')

    # 老K点评
    if laoke_comment:
        html_parts.append('<div class="laoke">')
        html_parts.append('<div class="laoke-label">💡 老K点评</div>')
        for line in laoke_comment.split("\n"):
            if line.strip():
                html_parts.append(f'<p style="margin:4px 0">{line.strip()}</p>')
        html_parts.append('</div>')

    # Footer
    html_parts.append('<div class="footer">')
    html_parts.append('<p>📌 思派工业技术 · 精益智能工厂实战派</p>')
    html_parts.append('<p>视频号：思派精益智能工厂领航员 | 抖音：老K谈精益</p>')
    html_parts.append('</div>')
    
    # Diagnosis CTA
    html_parts.append('<div style="margin:30px auto 20px;max-width:400px;text-align:center;padding:16px 20px;background:linear-gradient(135deg,#1a365d,#2563eb);border-radius:12px">')
    html_parts.append('<p style="color:#fff;font-size:15px;margin:0 0 10px;font-weight:600">🏭 免费工厂诊断</p>')
    html_parts.append('<p style="color:rgba(255,255,255,0.85);font-size:13px;margin:0 0 12px">3分钟完成问卷，获取您的诊断报告</p>')
    html_parts.append('<a href="https://ycntwzzv6rec.feishu.cn/share/base/form/shrcnIRICP6tOoaUCIliPhiMm3c" style="display:inline-block;background:#fff;color:#1a365d;padding:8px 24px;border-radius:20px;text-decoration:none;font-size:14px;font-weight:600">立即开始免费诊断 →</a>')
    html_parts.append('</div>')
    
    html_parts.append('</body></html>')

    return "\n".join(html_parts)


def build_draft_json(html_content: str, title: str, digest: str) -> dict:
    """构建公众号图文素材JSON"""
    return {
        "title": title,
        "thumb_media_id": "",  # 需要用户上传封面图后提供
        "author": "老K",
        "digest": digest[:120] if len(digest) > 120 else digest,
        "show_cover_pic": 0,
        "need_open_comment": 1,
        "only_fans_can_comment": 0,
        "content": html_content,
    }


def extract_digest(body: str) -> str:
    """从正文提取摘要（前120字）"""
    # 去除 markdown 标记
    text = re.sub(r'[#*>_\-|\[\](){}]', '', body)
    text = re.sub(r'\*\*', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text[:120]


def main():
    parser = argparse.ArgumentParser(description="快讯 → 公众号图文转换器")
    parser.add_argument("--input", type=str, default=None, help="快讯文件路径")
    parser.add_argument("--today", action="store_true", help="使用今日快讯")
    parser.add_argument("--html", action="store_true", help="仅输出HTML到终端")
    parser.add_argument("--output", type=str, default=None, help="输出HTML文件路径")
    args = parser.parse_args()

    # 确定输入文件
    filepath = None
    if args.today:
        today = datetime.now().strftime("%Y%m%d")
        filepath = os.path.join(OUTPUT_DIR, f"每日快讯_{today}.md")
    elif args.input:
        if os.path.exists(args.input):
            filepath = args.input
        else:
            filepath = os.path.join(OUTPUT_DIR, args.input)

    if not filepath or not os.path.exists(filepath):
        print(f"❌ 快讯文件未找到。用法: python3 {sys.argv[0]} --today 或 --input <file>")
        sys.exit(1)

    print(f"📖 读取: {filepath}")

    frontmatter, body = read_markdown(filepath)
    html = convert_to_wechat_html(body)

    # 提取标题
    date_str = frontmatter.get("date", datetime.now().strftime("%Y年%m月%d日"))
    weekday = frontmatter.get("weekday", "")
    title = f"每日行业快讯 {date_str}"

    # 提取摘要
    digest = extract_digest(body)

    if args.html:
        print(html)
        return

    # 输出文件
    if args.output:
        out_path = args.output
    else:
        basename = os.path.splitext(os.path.basename(filepath))[0]
        out_path = os.path.join(OUTPUT_DIR, f"{basename}_wechat.html")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"✅ 公众号HTML已生成: {out_path}")
    print(f"📝 标题: {title}")
    print(f"📋 摘要: {digest[:60]}...")
    print()
    print("ℹ️ 发布到公众号的下一步：")
    print("  1. 登录公众号后台 → 素材管理 → 新建图文")
    print("  2. 将上述HTML内容粘贴到正文（切换到HTML编辑模式）")
    print("  3. 设置封面图（建议: 900×500px）")
    print("  4. 点击预览 → 扫码确认排版")
    print("  5. 保存 → 定时发布或立即发布")
    print()
    print("📌 如需**自动发布**，请提供公众号 AppID 和 AppSecret，我将配置自动推送管线。")


if __name__ == "__main__":
    main()
