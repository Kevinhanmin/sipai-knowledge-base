#!/usr/bin/env python3
"""
飞书多维表格数据导出脚本
=========================
功能：从飞书精益智能工厂诊断问卷多维表格导出数据到本地JSON/CSV
用途：本地备份、数据分析、灾难恢复

使用方式：
  python3 export_feishu_data.py                        # 完整导出所有记录
  python3 export_feishu_data.py --output-dir ./backup   # 指定输出目录
  python3 export_feishu_data.py --only-json             # 只导JSON（含所有原始字段）
  python3 export_feishu_data.py --only-csv              # 只导CSV（评分摘要）
  python3 export_feishu_data.py --last-24h              # 只导出最近24小时变更的记录

环境变量（通过.env或GitHub Secrets）：
  FEISHU_APP_ID       - 飞书应用App ID
  FEISHU_APP_SECRET   - 飞书应用App Secret
  BITABLE_APP_TOKEN   - 多维表格App Token（默认：VU3hbjRyuabLhAseoK3ckzOzndg）
  TABLE_ID            - 数据表ID（默认：tblofr6TCloHk5Zb）
"""

import os
import sys
import json
import csv
import time
from datetime import datetime, timedelta
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError

# ===== 配置 =====
FEISHU_API_BASE = "https://open.feishu.cn/open-apis"
BITABLE_APP_TOKEN = os.environ.get("BITABLE_APP_TOKEN", "VU3hbjRyuabLhAseoK3ckzOzndg")
TABLE_ID = os.environ.get("TABLE_ID", "tblofr6TCloHk5Zb")
FEISHU_APP_ID = os.environ.get("FEISHU_APP_ID", "")
FEISHU_APP_SECRET = os.environ.get("FEISHU_APP_SECRET", "")
OUTPUT_DIR = Path(os.environ.get("OUTPUT_DIR", "./feishu_backup"))

# 评分维度字段列表（用于CSV摘要）
DIM_FIELDS = [
    "生产效率评分", "质量控制评分", "库存物流评分",
    "设备管理评分", "人员效率评分", "现场管理评分",
    "计划交付评分", "数字化评分",
]

# ===== 飞书API =====
def get_token():
    """获取飞书tenant_access_token"""
    data = json.dumps({"app_id": FEISHU_APP_ID, "app_secret": FEISHU_APP_SECRET}).encode()
    req = Request(
        f"{FEISHU_API_BASE}/auth/v3/tenant_access_token/internal",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with urlopen(req) as resp:
        result = json.loads(resp.read())
        if result.get("code") != 0:
            raise Exception(f"Token获取失败: {result.get('msg', '')}")
        return result["tenant_access_token"]

def feishu_api(method, path, body=None, retries=3):
    """通用的飞书API调用（带重试）"""
    for attempt in range(retries):
        try:
            token = get_token()
            url = f"{FEISHU_API_BASE}{path}"
            headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
            data = json.dumps(body).encode() if body else None
            req = Request(url, data=data, headers=headers, method=method)
            with urlopen(req, timeout=30) as resp:
                return json.loads(resp.read())
        except Exception as e:
            print(f"  ⚠️ API调用失败 (尝试 {attempt+1}/{retries}): {e}", file=sys.stderr)
            if attempt < retries - 1:
                time.sleep(2 ** attempt)  # 指数退避
            else:
                raise

def get_table_fields():
    """获取表的字段定义"""
    result = feishu_api("GET", f"/bitable/v1/apps/{BITABLE_APP_TOKEN}/tables/{TABLE_ID}/fields")
    return result.get("data", {}).get("items", [])

def get_all_records():
    """获取所有记录（自动翻页）"""
    records = []
    page_token = None
    page_num = 0
    while True:
        path = f"/bitable/v1/apps/{BITABLE_APP_TOKEN}/tables/{TABLE_ID}/records?page_size=500"
        if page_token:
            path += f"&page_token={page_token}"
        result = feishu_api("GET", path)
        items = result.get("data", {}).get("items", [])
        records.extend(items)
        page_num += 1
        print(f"  📄 第{page_num}页: {len(items)} 条记录 (累计: {len(records)})")
        if not result.get("data", {}).get("has_more"):
            break
        page_token = result.get("data", {}).get("page_token")
    return records

def parse_field_value(field_name, raw_value):
    """
    将飞书字段原始值转换为可读格式
    飞书多维表格的值类型多样：字符串、数组（文本块）、dict（选项/用户/引用）等
    """
    if raw_value is None:
        return ""
    if isinstance(raw_value, (str, int, float, bool)):
        return raw_value
    if isinstance(raw_value, list):
        # 纯文本数组（多行文本）
        texts = []
        for item in raw_value:
            if isinstance(item, dict):
                texts.append(item.get("text", ""))
            else:
                texts.append(str(item))
        return "\n".join(texts)
    if isinstance(raw_value, dict):
        # 单选/多选
        if "value" in raw_value:
            vals = raw_value["value"]
            if isinstance(vals, list):
                return ", ".join(str(v) for v in vals)
            return str(vals)
        # 人员/部门引用
        if "id" in raw_value:
            return raw_value.get("name", raw_value["id"])
        # 其他结构
        return json.dumps(raw_value, ensure_ascii=False)
    return str(raw_value)

def flatten_record(fields):
    """将飞书记录字段扁平化为简单键值对（所有值转为字符串）"""
    flat = {}
    for key, value in fields.items():
        flat[key] = parse_field_value(key, value)
    return flat

# ===== 导出 =====
def export_json(records, output_path):
    """导出为JSON格式"""
    # 每条记录包含record_id和扁平化的fields
    export_data = []
    for rec in records:
        flat_fields = flatten_record(rec.get("fields", {}))
        export_data.append({
            "record_id": rec["record_id"],
            "created_at": rec.get("created_at", ""),
            "updated_at": rec.get("updated_at", ""),
            **flat_fields
        })

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(export_data, f, ensure_ascii=False, indent=2)
    return len(export_data)

def export_csv(records, output_path):
    """导出为CSV格式（只包含关键字段）"""
    # 提取评分摘要字段
    csv_data = []
    for rec in records:
        fields = rec.get("fields", {})
        # 提取关键信息
        row = {
            "record_id": rec["record_id"],
            "企业名称": parse_field_value("Q1. 企业名称（填空题，必填）", fields.get("Q1. 企业名称（填空题，必填）", "")),
            "联系人": parse_field_value("Q29.联系人和联系方式（手机号/微信，必填）", fields.get("Q29.联系人和联系方式（手机号/微信，必填）", "")),
            "跟进进度": parse_field_value("跟进进度", fields.get("跟进进度", "")),
            "创建时间": rec.get("created_at", ""),
            "更新时间": rec.get("updated_at", ""),
        }
        # 加入评分维度
        for dim in DIM_FIELDS:
            row[dim] = parse_field_value(dim, fields.get(dim, 0))
        csv_data.append(row)

    # 写入CSV
    if not csv_data:
        print("  ⚠️ 没有数据")
        return 0

    fieldnames = [
        "record_id", "企业名称", "联系人", "跟进进度",
        "创建时间", "更新时间"
    ] + DIM_FIELDS

    with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(csv_data)
    return len(csv_data)

def export_field_definition(fields, output_path):
    """导出字段定义（方便重建表格）"""
    field_data = []
    for f in fields:
        field_data.append({
            "field_name": f.get("field_name", ""),
            "type": f.get("type", 0),
            "property": f.get("property", {}),
        })
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(field_data, f, ensure_ascii=False, indent=2)
    print(f"  📋 字段定义 ({len(field_data)} 个字段)")

def main():
    export_json_only = "--only-json" in sys.argv
    export_csv_only = "--only-csv" in sys.argv
    last_24h = "--last-24h" in sys.argv

    # 自定义输出目录
    for i, arg in enumerate(sys.argv):
        if arg == "--output-dir" and i + 1 < len(sys.argv):
            global OUTPUT_DIR
            OUTPUT_DIR = Path(sys.argv[i + 1])

    # 创建输出目录
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    print(f"{'='*50}")
    print(f"📤 飞书数据导出工具")
    print(f"{'='*50}")
    print(f"  App Token: {BITABLE_APP_TOKEN[:8]}...")
    print(f"  Table ID:  {TABLE_ID[:8]}...")
    print(f"  输出目录:  {OUTPUT_DIR}")
    if last_24h:
        print(f"  模式:      仅最近24小时")

    # 1) 获取字段定义
    print(f"\n📋 获取字段定义...")
    fields = get_table_fields()
    print(f"  共 {len(fields)} 个字段")
    export_field_definition(fields, OUTPUT_DIR / f"fields_{timestamp}.json")

    # 2) 获取所有记录
    print(f"\n🔍 获取记录...")
    records = get_all_records()
    print(f"  共获取 {len(records)} 条记录")

    # 过滤最近24小时
    if last_24h:
        cutoff = datetime.now() - timedelta(hours=24)
        cutoff_str = cutoff.strftime("%Y-%m-%dT%H:%M:%S")
        filtered = []
        for rec in records:
            updated = rec.get("updated_at", "")
            created = rec.get("created_at", "")
            if updated >= cutoff_str or created >= cutoff_str:
                filtered.append(rec)
        records = filtered
        print(f"  过滤后: {len(records)} 条（24小时内变更）")

    # 3) 导出
    if not export_csv_only:
        json_path = OUTPUT_DIR / f"records_{timestamp}.json"
        count = export_json(records, json_path)
        print(f"\n✅ JSON导出: {count} 条 → {json_path}")

    if not export_json_only:
        csv_path = OUTPUT_DIR / f"records_{timestamp}.csv"
        count = export_csv(records, csv_path)
        print(f"✅ CSV导出:  {count} 条 → {csv_path}")

    # 4) 生成备份清单
    manifest = {
        "export_time": datetime.now().isoformat(),
        "bitable_app_token": BITABLE_APP_TOKEN,
        "table_id": TABLE_ID,
        "record_count": len(records),
        "field_count": len(fields),
        "files": [
            f"fields_{timestamp}.json",
            f"records_{timestamp}.json",
            f"records_{timestamp}.csv",
        ]
    }
    manifest_path = OUTPUT_DIR / f"manifest_{timestamp}.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(f"✅ 清单:    {manifest_path}")

    print(f"\n{'-'*50}")
    print(f"📦 导出文件总览:")
    for fname in manifest["files"]:
        fpath = OUTPUT_DIR / fname
        size = fpath.stat().st_size if fpath.exists() else 0
        print(f"  📄 {fname:45s} {size:>8,} bytes")
    print(f"{'='*50}")
    return 0

if __name__ == "__main__":
    if not FEISHU_APP_ID or not FEISHU_APP_SECRET:
        print("❌ 请设置 FEISHU_APP_ID 和 FEISHU_APP_SECRET 环境变量")
        print("   或在.env文件中配置")
        sys.exit(1)
    sys.exit(main())
