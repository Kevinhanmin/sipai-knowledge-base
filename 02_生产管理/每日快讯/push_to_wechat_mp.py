#!/usr/bin/env python3
"""
思派工业 · 微信公众号自动发布客户端
=================================
通过微信公众号 API 自动创建图文素材并发布。

⚠️ 使用前需先提供以下信息：
  1. 公众号 AppID
  2. 公众号 AppSecret
  3. 已上传的封面图 media_id

用法：
  python3 push_to_wechat_mp.py --file 每日快讯_20260511_wechat.html    # 手动发布
  python3 push_to_wechat_mp.py --today                                 # 发布今日
  python3 push_to_wechat_mp.py --draft                                  # 仅存为草稿（不发布）
  python3 push_to_wechat_mp.py --check                                  # 查看当前token状态
"""

import argparse
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime

OUTPUT_DIR = os.path.expanduser("~/Documents/精益智能工厂/02_生产管理/每日快讯")
ENV_PATH = os.path.expanduser("~/.hermes/.env")

# 从 .env 加载公众号配置
WECHAT_APPID = os.environ.get("WECHAT_MP_APPID", "")
WECHAT_APPSECRET = os.environ.get("WECHAT_MP_APPSECRET", "")
WECHAT_THUMB_MEDIA_ID = os.environ.get("WECHAT_THUMB_MEDIA_ID", "")

_token_cache = {"token": None, "expires_at": 0}


def load_env():
    global WECHAT_APPID, WECHAT_APPSECRET, WECHAT_THUMB_MEDIA_ID
    if os.path.exists(ENV_PATH):
        with open(ENV_PATH) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                v = v.strip().strip('"').strip("'")
                if k == "WECHAT_MP_APPID":
                    WECHAT_APPID = v
                elif k == "WECHAT_MP_APPSECRET":
                    WECHAT_APPSECRET = v
                elif k == "WECHAT_THUMB_MEDIA_ID":
                    WECHAT_THUMB_MEDIA_ID = v


def wechat_api_post(path: str, body: dict) -> dict:
    """调用微信公众平台 API"""
    token = _get_access_token()
    url = f"https://api.weixin.qq.com/cgi-bin{path}?access_token={token}"
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            return result
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8") if e.fp else ""
        return {"errcode": e.code, "errmsg": str(e), "body": err_body}


def _get_access_token() -> str:
    """获取 access_token（自动缓存刷新）"""
    now = time.time()
    if _token_cache["token"] and now < _token_cache["expires_at"] - 120:
        return _token_cache["token"]
    
    if not WECHAT_APPID or not WECHAT_APPSECRET:
        raise ValueError("未配置公众号凭证。请在 ~/.hermes/.env 中添加：\n"
                         "  WECHAT_MP_APPID=你的AppID\n"
                         "  WECHAT_MP_APPSECRET=你的AppSecret")
    
    url = (f"https://api.weixin.qq.com/cgi-bin/token"
           f"?grant_type=client_credential"
           f"&appid={WECHAT_APPID}&secret={WECHAT_APPSECRET}")
    
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    
    if "access_token" in data:
        _token_cache["token"] = data["access_token"]
        _token_cache["expires_at"] = now + data.get("expires_in", 7200)
        return _token_cache["token"]
    else:
        raise RuntimeError(f"获取 access_token 失败: {data.get('errmsg', '未知错误')}")


def check_token():
    """检查 access_token 状态"""
    try:
        token = _get_access_token()
        print(f"✅ access_token 获取成功")
        print(f"   Token: {token[:10]}...{token[-5:]}")
        print(f"   过期时间: {datetime.fromtimestamp(_token_cache['expires_at']).strftime('%H:%M:%S')}")
        return True
    except Exception as e:
        print(f"❌ access_token 获取失败: {e}")
        return False


def upload_image(filepath: str) -> str | None:
    """上传图片作为封面，返回 media_id"""
    token = _get_access_token()
    url = f"https://api.weixin.qq.com/cgi-bin/material/add_material?access_token={token}&type=image"
    
    import http.client
    
    boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
    with open(filepath, "rb") as f:
        file_data = f.read()
    
    filename = os.path.basename(filepath)
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="media"; filename="{filename}"\r\n'
        f"Content-Type: image/jpeg\r\n\r\n"
    ).encode("utf-8") + file_data + (
        f"\r\n--{boundary}--\r\n"
    ).encode("utf-8")
    
    headers = {"Content-Type": f"multipart/form-data; boundary={boundary}"}
    
    parsed = urllib.parse.urlparse(url)
    conn = http.client.HTTPSConnection(parsed.hostname)
    conn.request("POST", parsed.path + "?" + parsed.query, body=body, headers=headers)
    resp = conn.getresponse()
    result = json.loads(resp.read().decode("utf-8"))
    conn.close()
    
    if "media_id" in result:
        return result["media_id"]
    else:
        print(f"❌ 上传图片失败: {result.get('errmsg', '未知错误')}")
        return None


def create_draft(html_path: str, publish: bool = False) -> dict:
    """创建图文素材（草稿或发布）"""
    if not os.path.exists(html_path):
        return {"errcode": -1, "errmsg": f"文件不存在: {html_path}"}
    
    with open(html_path, "r", encoding="utf-8") as f:
        html_content = f.read()
    
    # 提取标题
    title_match = re.search(r'<h1>(.+?)</h1>', html_content)
    title = title_match.group(1) if title_match else "每日行业快讯"
    
    # 提取摘要
    body_text = re.sub(r'<[^>]+>', '', html_content)
    body_text = re.sub(r'\s+', ' ', body_text).strip()
    digest = body_text[:80]
    
    # 构建图文素材
    article = {
        "title": title,
        "thumb_media_id": WECHAT_THUMB_MEDIA_ID,
        "author": "老K",
        "digest": digest,
        "show_cover_pic": 1 if WECHAT_THUMB_MEDIA_ID else 0,
        "need_open_comment": 1,
        "only_fans_can_comment": 0,
        "content": html_content,
        "content_source_url": "",  # 原文链接（可选）
    }
    
    # 创建草稿（公众号新版接口）
    # 使用草稿箱 API: POST /cgi-bin/draft/add
    body = {"articles": [article]}
    result = wechat_api_post("/draft/add", body)
    
    if result.get("media_id"):
        print(f"✅ 图文草稿已创建: {result['media_id']}")
        if publish:
            # 发布草稿
            return publish_draft(result["media_id"])
        return result
    else:
        print(f"❌ 创建草稿失败: {result.get('errmsg', '未知错误')}")
        return result


def publish_draft(media_id: str) -> dict:
    """发布草稿"""
    body = {"media_id": media_id}
    result = wechat_api_post("/freepublish/submit", body)
    if result.get("publish_id"):
        print(f"✅ 发布已提交: publish_id={result['publish_id']}")
        print(f"   可在公众号后台查看发布状态")
    else:
        print(f"❌ 发布失败: {result.get('errmsg', '未知错误')}")
    return result


def main():
    load_env()
    parser = argparse.ArgumentParser(description="微信公众号自动发布")
    parser.add_argument("--file", type=str, default=None, help="公众号HTML文件路径")
    parser.add_argument("--today", action="store_true", help="发布今日快讯")
    parser.add_argument("--draft", action="store_true", help="仅存为草稿（不发布）")
    parser.add_argument("--publish", action="store_true", help="创建草稿并发布")
    parser.add_argument("--check", action="store_true", help="检查token状态")
    args = parser.parse_args()

    if args.check:
        check_token()
        return

    # 确定HTML文件
    html_path = None
    if args.today:
        today = datetime.now().strftime("%Y%m%d")
        html_path = os.path.join(OUTPUT_DIR, f"每日快讯_{today}_wechat.html")
    elif args.file:
        html_path = args.file

    if not html_path or not os.path.exists(html_path):
        print(f"❌ 文件未找到。请先生成公众号HTML：")
        print(f"   python3 wechat_article_builder.py --today")
        sys.exit(1)

    print(f"📖 读取: {html_path}")
    
    if args.draft:
        create_draft(html_path, publish=False)
    else:
        # 默认发布
        if not WECHAT_APPID or not WECHAT_APPSECRET:
            print("⚠️ 公众号凭证未配置。请在 ~/.hermes/.env 中添加：")
            print("   WECHAT_MP_APPID=你的AppID")
            print("   WECHAT_MP_APPSECRET=你的AppSecret")
            print("   WECHAT_THUMB_MEDIA_ID=封面图media_id（可选）")
            print()
            print("📌 临时方案：手动登录公众号后台发布，HTML文件已准备好。")
            return
        create_draft(html_path, publish=args.publish)


if __name__ == "__main__":
    main()
