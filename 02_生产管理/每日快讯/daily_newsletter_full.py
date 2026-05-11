#!/usr/bin/env python3
"""
思派工业 · 每日行业快讯完整自动化管线
===========================================
全自动执行：收集资讯 → 填充模板 → 通知创始人

用法：
  python3 daily_newsletter_full.py          # 生成今日快讯（自动搜索+填充+通知）
  python3 daily_newsletter_full.py --notify # 仅发送飞书通知（审核通过后调用）
  python3 daily_newsletter_full.py --date 2026-05-12 --dry-run  # 预览
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime

OUTPUT_DIR = os.path.expanduser("~/Documents/精益智能工厂/02_生产管理/每日快讯")
WEEKDAY_CN = ["一", "二", "三", "四", "五", "六", "日"]

# 飞书配置
_HERMES_ENV = os.path.expanduser("~/.hermes/.env")
if os.path.exists(_HERMES_ENV):
    with open(_HERMES_ENV) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ[k.strip()] = v.strip()

API_BASE = os.environ.get("FEISHU_API_BASE_URL", "https://open.feishu.cn/open-apis")
APP_ID = os.environ.get("FEISHU_APP_ID", "")
APP_SECRET = os.environ.get("FEISHU_APP_SECRET", "")
FOUNDER_OPEN_ID = os.environ.get("FOUNDER_OPEN_ID", "")

_token_cache = {"token": None, "expires_at": 0}


# ============================================================
# 飞书消息发送
# ============================================================

def _get_tenant_token() -> str:
    now = time.time()
    if _token_cache["token"] and now < _token_cache["expires_at"] - 60:
        return _token_cache["token"]
    url = f"{API_BASE}/auth/v3/tenant_access_token/internal"
    body = json.dumps({"app_id": APP_ID, "app_secret": APP_SECRET}).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    if data.get("code") != 0:
        raise RuntimeError(f"获取飞书 Token 失败: {data.get('msg', '未知错误')}")
    _token_cache["token"] = data["tenant_access_token"]
    _token_cache["expires_at"] = now + data["expire"]
    return _token_cache["token"]


def _api_post(path: str, body: dict) -> dict:
    token = _get_tenant_token()
    url = f"{API_BASE}{path}"
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url, data=data,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8") if e.fp else ""
        return {"code": e.code, "error": str(e), "body": err_body}


def send_feishu_notification(message_text: str, title: str = "📰 每日行业快讯"):
    """发送飞书消息给创始人"""
    if not FOUNDER_OPEN_ID:
        print("⚠️ 未配置 FOUNDER_OPEN_ID，无法发送飞书通知")
        return False

    # 构建消息卡片
    card = {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": title},
            "template": "blue",
        },
        "elements": [
            {"tag": "markdown", "content": message_text},
        ],
    }

    body = {
        "receive_id": FOUNDER_OPEN_ID,
        "msg_type": "interactive",
        "content": json.dumps(card),
    }

    result = _api_post("/im/v1/messages?receive_id_type=open_id", body)
    if result.get("code") == 0:
        print("✅ 飞书通知发送成功")
        return True
    else:
        print(f"❌ 飞书通知发送失败: {result.get('msg', '未知错误')}")
        print(f"   详情: {json.dumps(result, ensure_ascii=False)[:300]}")
        return False


# ============================================================
# 模板生成
# ============================================================

def generate_blank_template(date_str: str) -> str:
    """生成空白模板，返回文件路径"""
    date_obj = datetime.strptime(date_str, "%Y-%m-%d")
    date_cn = date_obj.strftime("%Y年%m月%d日")
    weekday = WEEKDAY_CN[date_obj.weekday()]
    filename = f"每日快讯_{date_obj.strftime('%Y%m%d')}.md"
    filepath = os.path.join(OUTPUT_DIR, filename)

    if os.path.exists(filepath):
        return filepath  # 已存在，不覆盖

    lines = [
        "---",
        "tags: [每日快讯, 新闻, 行业动态]",
        f"date: {date_cn}",
        f"weekday: {weekday}",
        "status: 待审核",
        "---",
        "",
        f"# 📰 精益智能工厂 · 每日行业快讯",
        "",
        f"**{date_cn} · 星期{weekday}**",
        "",
        "> 聚焦制造业前沿动态，为工厂管理者提供每日资讯精选",
        "",
        "---",
        "",
        "## 🏛️ 政策动态",
        "",
        "### [政策标题]",
        "- **要点**：",
        "- **影响**：",
        "- **来源**：",
        "",
        "### [政策标题]",
        "- **要点**：",
        "- **影响**：",
        "- **来源**：",
        "",
        "---",
        "",
        "## 🏭 行业案例",
        "",
        "### [案例标题]",
        "- **企业**：",
        "- **做法**：",
        "- **结果**：",
        "- **启示**：",
        "",
        "### [案例标题]",
        "- **企业**：",
        "- **做法**：",
        "- **结果**：",
        "- **启示**：",
        "",
        "---",
        "",
        "## 🛠️ 工具方法",
        "",
        "### [工具名称]",
        "- **工具名称**：",
        "- **适用场景**：",
        "- **核心要点**：",
        "- **实施步骤**：",
        "",
        "### [工具名称]",
        "- **工具名称**：",
        "- **适用场景**：",
        "- **核心要点**：",
        "- **实施步骤**：",
        "",
        "---",
        "",
        "## 📊 趋势洞察",
        "",
        "### [趋势标题]",
        "- **趋势**：",
        "- **数据支撑**：",
        "- **影响分析**：",
        "",
        "### [趋势标题]",
        "- **趋势**：",
        "- **数据支撑**：",
        "- **影响分析**：",
        "",
        "---",
        "",
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
    ]

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"✅ 模板已生成: {filepath}")
    return filepath


# ============================================================
# 读取快讯文件 → 提取摘要 → 通知
# ============================================================

def extract_summary(filepath: str) -> str:
    """从已填充的快讯文件中提取摘要信息"""
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    sections = content.split("---")
    result_parts = []

    for section in sections:
        section = section.strip()
        if not section:
            continue

        # 提取政策动态
        if "## 🏛️ 政策动态" in section:
            lines = section.split("\n")
            items = [l for l in lines if l.startswith("- **要点**：")]
            if items:
                result_parts.append("🏛️ **政策动态**")
                for item in items[:2]:
                    point = item.replace("- **要点**：", "").strip()
                    if len(point) > 60:
                        point = point[:60] + "…"
                    result_parts.append(f"  • {point}")

        # 提取行业案例
        if "## 🏭 行业案例" in section:
            lines = section.split("\n")
            items = [l for l in lines if l.startswith("- **结果**：")]
            if items:
                result_parts.append("🏭 **行业案例**")
                for item in items[:2]:
                    point = item.replace("- **结果**：", "").strip()
                    if len(point) > 60:
                        point = point[:60] + "…"
                    result_parts.append(f"  • {point}")

        # 提取工具方法
        if "## 🛠️ 工具方法" in section:
            lines = section.split("\n")
            titles = [l.strip("# ") for l in lines if l.startswith("### ") and "工具名称" not in l]
            if not titles:
                # try finding ### lines with content
                titles = [l.strip("# ").strip() for l in lines if l.startswith("### ") and l.strip("# ").strip() and "请输入" not in l]
            if titles:
                result_parts.append("🛠️ **工具方法**")
                for t in titles[:2]:
                    result_parts.append(f"  • {t}")

    # 提取老K点评
    start_idx = content.find("## 💡 老K点评")
    if start_idx >= 0:
        end_idx = content.find("## 📌 今日互动", start_idx)
        if end_idx < 0:
            end_idx = content.find("---", start_idx)
        if end_idx < 0:
            end_idx = start_idx + 500
        comment_section = content[start_idx:end_idx]
        quote_match = re.search(r'>\s*(.+?)\n', comment_section)
        if quote_match:
            comment = quote_match.group(1).strip()
            if comment and comment != "（待补充）" and comment != "*（待补充）*":
                result_parts.append(f"\n💡 **老K点评**")
                result_parts.append(f"  \"{comment[:80]}{'…' if len(comment)>80 else ''}\"")

    if not result_parts:
        return "今日快讯尚未填充内容，请查看完整文件。"

    return "\n".join(result_parts)


def read_file_content(filepath: str) -> str:
    """读取文件内容"""
    with open(filepath, "r", encoding="utf-8") as f:
        return f.read()


# ============================================================
# 主逻辑
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="思派工业 · 每日行业快讯自动化管线")
    parser.add_argument("--date", type=str, default=None, help="目标日期 (YYYY-MM-DD，默认今天)")
    parser.add_argument("--notify", action="store_true", help="仅发送飞书通知（审核通过后调用）")
    parser.add_argument("--dry-run", action="store_true", help="预览模式，不生成文件")
    parser.add_argument("--file", type=str, default=None, help="指定快讯文件路径（--notify时使用）")
    parser.add_argument("--wechat", action="store_true", help="生成公众号图文HTML")
    parser.add_argument("--wechat-publish", action="store_true", help="生成并自动发布到公众号（需配置凭证）")
    args = parser.parse_args()

    date_str = args.date if args.date else datetime.now().strftime("%Y-%m-%d")
    date_obj = datetime.strptime(date_str, "%Y-%m-%d")
    filename = f"每日快讯_{date_obj.strftime('%Y%m%d')}.md"
    filepath = args.file if args.file else os.path.join(OUTPUT_DIR, filename)

    # ----- 仅通知模式（审核通过后调用）-----
    if args.notify:
        if not os.path.exists(filepath):
            print(f"❌ 文件不存在: {filepath}")
            sys.exit(1)

        summary = extract_summary(filepath)

        # 读取状态
        content = read_file_content(filepath)
        status_match = re.search(r'status:\s*(.+?)\n', content)
        status = status_match.group(1).strip() if status_match else "未知"

        if args.dry_run:
            print("=" * 50)
            print(f"📰 每日快讯 — {date_str}")
            print(f"文件: {filepath}")
            print(f"状态: {status}")
            print("=" * 50)
            print(summary)
            print("=" * 50)
            return

        # 发送飞书通知
        date_cn = date_obj.strftime("%Y年%m月%d日")
        weekday = WEEKDAY_CN[date_obj.weekday()]

        msg = (
            f"📰 **每日行业快讯 · {date_cn} · 星期{weekday}**\n\n"
            f"{summary}\n\n"
            f"---\n"
            f"📁 完整内容：`{filepath}`\n"
            f"🔄 状态：**{status}**\n\n"
            f"🙋 如需调整或确认发布，请回复此消息。"
        )

        success = send_feishu_notification(msg, f"📰 每日行业快讯 · {date_str}")
        if success:
            print(f"✅ 快讯已推送至创始人的飞书")
        else:
            print(f"❌ 推送失败")
        return

    # ----- 公众号模式 -----
    if args.wechat or args.wechat_publish:
        if not os.path.exists(filepath):
            print(f"❌ 快讯文件不存在: {filepath}")
            print(f"  请先填充内容后再生成公众号图文")
            sys.exit(1)
        
        # 调用 wechat_article_builder.py 生成HTML
        builder_script = os.path.join(OUTPUT_DIR, "wechat_article_builder.py")
        result = subprocess.run(
            ["python3", builder_script, "--input", filepath],
            capture_output=True, text=True, timeout=30
        )
        print(result.stdout)
        if result.returncode != 0:
            print(f"❌ 公众号图文生成失败: {result.stderr}")
            sys.exit(1)
        
        if args.wechat_publish:
            # 调用 push_to_wechat_mp.py 发布
            push_script = os.path.join(OUTPUT_DIR, "push_to_wechat_mp.py")
            html_path = filepath.replace(".md", "_wechat.html")
            result = subprocess.run(
                ["python3", push_script, "--file", html_path, "--publish"],
                capture_output=True, text=True, timeout=30
            )
            print(result.stdout)
            if result.returncode != 0:
                print(f"❌ 公众号发布失败: {result.stderr}")
        return

    # ----- 日常模式：生成模板 -----
    if args.dry_run:
        print(f"🔍 预览模式: {date_str}")
        print(f"   输出路径: {filepath}")
        print(f"   文件将生成空白模板（如已存在则跳过）")
        return

    filepath = generate_blank_template(date_str)
    print(f"📄 模板就绪: {filepath}")

    # 尝试发送通知（不阻塞）
    try:
        summary = (
            f"📋 **今日行业快讯模板已生成**\n\n"
            f"请在 `{filepath}` 中查看并填充内容。\n"
            f"填充完成后，请回复告知我进行技术审核。\n\n"
            f"---\n"
            f"⏰ 自动生成时间: {datetime.now().strftime('%H:%M')}\n"
            f"📌 审核流程: 内容师填充 → 诊断师审核 → 推送创始人确认"
        )
        if FOUNDER_OPEN_ID:
            send_feishu_notification(summary, "📰 每日行业快讯模板已就绪")
    except Exception as e:
        print(f"⚠️ 通知发送异常（不阻塞流程）: {e}")

    print("✅ 每日快讯自动化管线执行完毕")


if __name__ == "__main__":
    main()
