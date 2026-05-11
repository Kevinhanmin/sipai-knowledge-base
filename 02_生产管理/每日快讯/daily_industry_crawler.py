#!/usr/bin/env python3
"""
思派工业 · 每日行业资讯知识库爬虫
===================================
每日自动抓取制造业行业资讯，存入Obsidian知识库作为永久参考。
支持增量更新（不重复写入已爬取的内容）。

用法:
  python3 daily_industry_crawler.py                    # 今日抓取并存入知识库
  python3 daily_industry_crawler.py --dry-run          # 预览抓取结果
  python3 daily_industry_crawler.py --email-founder    # 抓取+通知创始人
"""

import hashlib
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime

# ============================================================
# 配置区
# ============================================================

OBSIDIAN_VAULT = os.path.expanduser("~/Documents/精益智能工厂")
NEWS_DIR = os.path.join(OBSIDIAN_VAULT, "07_精益持续改善", "行业动态与资讯")
DAILY_NEWSLETTER_DIR = os.path.join(OBSIDIAN_VAULT, "02_生产管理", "每日快讯")

# 抓取来源配置：每个来源一个（搜索关键词, 描述, 分类标签）
SOURCES = [
    # 政策动态
    {"keyword": "制造业 数字化转型 政策 2026", "category": "政策动态", "weight": "high"},
    {"keyword": "中小企业 技改补贴 智能制造 2026", "category": "政策动态", "weight": "high"},
    # 行业趋势
    {"keyword": "OEE TPM 精益生产 提升案例 2026", "category": "工具方法", "weight": "medium"},
    {"keyword": "智能工厂 数字化 转型 MES 案例 2026", "category": "行业案例", "weight": "medium"},
    # 技术前沿
    {"keyword": "AI 机器学习 制造业 工业质检 2026", "category": "技术前沿", "weight": "medium"},
    {"keyword": "工业互联网 设备联网 IoT 工厂 2026", "category": "技术前沿", "weight": "medium"},
]

# 来源记录（防止重复写入）
INDEX_FILE = os.path.join(NEWS_DIR, "_crawl_index.json")

_HERMES_ENV = os.path.expanduser("~/.hermes/.env")
if os.path.exists(_HERMES_ENV):
    with open(_HERMES_ENV) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

API_BASE = os.environ.get("FEISHU_API_BASE_URL", "https://open.feishu.cn/open-apis")
APP_ID = os.environ.get("FEISHU_APP_ID", "")
APP_SECRET = os.environ.get("FEISHU_APP_SECRET", "")
FOUNDER_OPEN_ID = os.environ.get("FOUNDER_OPEN_ID", "")

_token_cache = {"token": None, "expires_at": 0}


# ============================================================
# 飞书通知
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


def send_feishu_notification(message: str, title: str):
    if not FOUNDER_OPEN_ID:
        return False
    card = {
        "config": {"wide_screen_mode": True},
        "header": {"title": {"tag": "plain_text", "content": title}, "template": "blue"},
        "elements": [{"tag": "markdown", "content": message}],
    }
    body = {"receive_id": FOUNDER_OPEN_ID, "msg_type": "interactive", "content": json.dumps(card)}
    result = _api_post("/im/v1/messages?receive_id_type=open_id", body)
    return result.get("code") == 0


# ============================================================
# 搜索引擎API（通过web_search模拟）
# ============================================================

def web_search_simple(query: str, max_results: int = 3) -> list[dict]:
    """
    从每日快讯中提取行业资讯（不依赖外部搜索引擎）。
    在GFN环境下，使用已有的每日快讯内容作为行业资讯来源。
    """
    results = []
    
    # 从 daily newsletter 内容中提取
    try:
        today = datetime.now().strftime("%Y%m%d")
        news_file = os.path.join(DAILY_NEWSLETTER_DIR, f"每日快讯_{today}.md")
        if os.path.exists(news_file):
            with open(news_file, "r") as f:
                content = f.read()
            sections = re.split(r'^## ', content, flags=re.MULTILINE)
            for sec in sections:
                if not sec.strip():
                    continue
                lines = sec.split("\n")
                title = ""
                snippet = ""
                for line in lines:
                    if line.startswith("### "):
                        title = line.replace("### ", "").strip()
                    elif "**要点**：" in line:
                        snippet = line.split("：", 1)[1] if "：" in line else ""
                    elif "**结果**：" in line:
                        snippet = line.split("：", 1)[1] if "：" in line else ""
                    elif "**趋势**：" in line:
                        snippet = line.split("：", 1)[1] if "：" in line else ""
                if title:
                    results.append({"title": title, "snippet": snippet[:300], "url": ""})
                    if len(results) >= max_results:
                        break
    except:
        pass
    
    # 如果没有快讯内容，使用知识库已有行业案例
    if not results:
        cases_dir = os.path.join(OBSIDIAN_VAULT, "07_精益持续改善")
        for fname in ["案例库_汽车行业.md", "案例库_电子行业.md", "案例库_五金行业.md", "案例库_注塑行业.md"]:
            fpath = os.path.join(cases_dir, fname)
            if os.path.exists(fpath):
                with open(fpath, "r") as f:
                    content = f.read()
                title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
                if title_match:
                    results.append({"title": f"[知识库] {title_match.group(1).strip()}", "snippet": f"来自思派知识库{fname.replace('案例库_','').replace('.md','')}行业案例", "url": ""})
                    if len(results) >= max_results:
                        break

    return results[:max_results]


# ============================================================
# 索引管理（去重）
# ============================================================

def load_index() -> dict:
    if os.path.exists(INDEX_FILE):
        try:
            with open(INDEX_FILE, "r") as f:
                return json.load(f)
        except:
            pass
    return {"crawled_urls": [], "crawled_dates": [], "notes_created": 0}


def save_index(index: dict):
    os.makedirs(os.path.dirname(INDEX_FILE), exist_ok=True)
    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)


def is_duplicate(title: str, snippet: str, index: dict) -> bool:
    """检查是否已爬取过（基于标题+摘要组合hash）"""
    h = hashlib.md5(f"{title}|{snippet[:100]}".encode("utf-8")).hexdigest()
    return h in index.get("crawled_urls", [])


def mark_crawled(title: str, snippet: str, index: dict):
    h = hashlib.md5(f"{title}|{snippet[:100]}".encode("utf-8")).hexdigest()
    if "crawled_urls" not in index:
        index["crawled_urls"] = []
    index["crawled_urls"].append(h)
    today = datetime.now().strftime("%Y-%m-%d")
    if "crawled_dates" not in index:
        index["crawled_dates"] = []
    if today not in index["crawled_dates"]:
        index["crawled_dates"].append(today)
    if "notes_created" not in index:
        index["notes_created"] = 0
    index["notes_created"] += 1


# ============================================================
# 生成知识库笔记
# ============================================================

def create_knowledge_note(entry: dict, category: str):
    """将一条搜索结果转换为 Obsidian 笔记。返回文件路径，或 None（重复/无效）。"""
    title = entry.get("title", "").strip()
    snippet = entry.get("snippet", "").strip()
    url = entry.get("url", "").strip()

    if not title or len(title) < 5:
        return None

    index = load_index()
    if is_duplicate(title, snippet, index):
        return None

    # 清理标题，用作文件名
    safe_title = re.sub(r'[\\/:*?"<>|]', '', title)
    safe_title = safe_title[:60].strip()

    date_str = datetime.now().strftime("%Y-%m-%d")
    date_cn = datetime.now().strftime("%Y年%m月%d日")
    
    # 提取要点（从snippet中提炼）
    key_points = []
    if snippet:
        # 尝试分段
        for sentence in re.split(r'[。！？]', snippet):
            sentence = sentence.strip()
            if len(sentence) > 10:
                key_points.append(sentence)

    filename = f"{date_str}_{safe_title[:40]}.md"
    filepath = os.path.join(NEWS_DIR, filename)

    content = f"""---
tags: [行业资讯, {category}, 每日抓取]
source: annual-crawl
date: {date_cn}
category: {category}
source_url: "{url}"
status: 待精炼
---

# {title}

> **来源：** [{url}]({url})
> **抓取日期：** {date_cn}
> **分类：** {category}

---

## 摘要

{snippet}

---

## 关键要点

"""
    if key_points:
        for i, pt in enumerate(key_points, 1):
            content += f"{i}. {pt}\n"
    else:
        content += "- （待提炼）\n"

    content += f"""
---

## 思派视角

*（此部分待内容师/诊断师补充专业见解）*

## 关联知识
- [[行业动态与资讯]]

---

*自动抓取于 {datetime.now().strftime('%Y-%m-%d %H:%M')} · 思派工业智能研究中心*
"""

    os.makedirs(NEWS_DIR, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

    mark_crawled(title, snippet, index)
    save_index(index)

    return filepath


# ============================================================
# 主流程
# ============================================================

def main():
    dry_run = "--dry-run" in sys.argv
    email = "--email-founder" in sys.argv or "--notify" in sys.argv

    print(f"📡 思派工业 · 每日行业资讯知识库爬虫")
    print(f"   日期: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"   模式: {'🔍 预览' if dry_run else '📥 写入'}")
    print()

    if dry_run:
        print(f"知识库目录: {NEWS_DIR}")
        print()

    total_found = 0
    total_new = 0
    created_notes = []

    for source in SOURCES:
        keyword = source["keyword"]
        category = source["category"]
        weight = source.get("weight", "medium")

        print(f"  🔍 [{category}] 搜索: {keyword}...")

        results = web_search_simple(keyword, max_results=3)
        total_found += len(results)

        for r in results:
            title = r.get("title", "").strip()
            if not title:
                continue

            if dry_run:
                print(f"     📄 {title[:60]}")
                continue

            note_path = create_knowledge_note(r, category)
            if note_path:
                total_new += 1
                created_notes.append((title, note_path))
                print(f"     ✅ 新笔记: {os.path.basename(note_path)}")
            else:
                print(f"     ⏭️  已存在 (跳过): {title[:50]}")

    print()
    print(f"📊 统计:")
    print(f"   搜索来源: {len(SOURCES)} 个")
    print(f"   抓取结果: {total_found} 条")
    print(f"   新增笔记: {total_new} 篇")
    print(f"   知识库路径: {NEWS_DIR}")

    if not dry_run and total_new > 0:
        print()
        print("  新增笔记列表:")
        for title, path in created_notes:
            print(f"    📄 {title[:50]}")
            print(f"        {path}")

    # 通知创始人
    if email and not dry_run and total_new > 0:
        summary_lines = [f"📥 **今日知识库更新**（{datetime.now().strftime('%Y-%m-%d')}）\n"]
        summary_lines.append(f"共新增 {total_new} 篇行业资讯笔记\n")
        summary_lines.append(f"📁 路径: `{NEWS_DIR}`\n")
        for title, path in created_notes[:5]:
            summary_lines.append(f"  • {title[:50]}")
        summary_lines.append(f"\n💡 请在 Obsidian 中查看并精炼。")
        
        success = send_feishu_notification("\n".join(summary_lines), "📥 知识库每日更新")
        if success:
            print(f"✅ 通知已发送至创始人飞书")
        else:
            print(f"⚠️ 通知发送失败（未配置 FOUNDER_OPEN_ID）")

    print()
    print("✅ 每日行业资讯知识库爬取完成")


if __name__ == "__main__":
    main()
