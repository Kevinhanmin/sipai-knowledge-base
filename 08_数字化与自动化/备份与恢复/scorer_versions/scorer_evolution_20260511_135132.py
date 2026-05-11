#!/usr/bin/env python3
"""
"评分师 + 架构师 · PDCA联合工作循环 (v3.0)
==========================================
评分师与架构师的PDCA协同工作机制

## PDCA联合循环
┌─────────────────────────────────────────────────────────┐
│  P 架构师规划 → D 评分师执行 → C 联合评估 → A 架构师调整│
│           ↑_______________________________↓             │
└─────────────────────────────────────────────────────────┘

## 双Agent PDCA周期
│ 阶段 │ 角色     │ 动作                                               │
│ P    │ 架构师   │ 设计/更新8维权重、问卷内容、边界规则              │
│ D    │ 评分师   │ 执行评分、生成报告、更新飞书状态                   │
│ C    │ 评分师   │ 分析区分度/偏态/痛点/转化率（问卷质量评估）       │
│      │ +架构师  │ 联合评估是否需要调整维度权重或问题设计            │
│ A    │ 架构师   │ 根据评估结果调整维度配置、优化问卷                 │
│      │ 评分师   │ 同步更新评分引擎权重，准备下一轮PDCA              │

## 里程碑触发器
- 30+样本 → 自动触发PDCA联合评估（checkpoint）
- (距上次评估)每新增50样本 → 追加检查
- 发现异常 → 即时触发（区分度<0.8持续3周期，或偏态持续）

## 自进化能力
1. 问卷质量分析 — 哪道题区分度低？哪道题客户跳过多？
2. 评分模型调优 — 根据最终诊断结果校准评分权重
3. 报告模板迭代 — 根据创始人反馈优化报告格式
4. 问题建议优化 — 自动生成问卷改进建议
5. PDCA里程碑触发 — 30+样本后自动生成联合评估报告

使用方式：
  python3 scorer_evolution.py --cycle            # 执行一次完整工作循环（含PDCA检查）
  python3 scorer_evolution.py --watch            # 持续监听模式
  python3 scorer_evolution.py --analyze          # 执行问卷质量分析
  python3 scorer_evolution.py --report-stats     # 输出评分师运营统计数据
  python3 scorer_evolution.py --pdca-check       # 检查是否需要触发PDCA里程碑

依赖:
  pip install requests
"""

import os
import sys
import json
import time
import math
import hashlib
import argparse
from datetime import datetime, timezone, timedelta
from pathlib import Path
from collections import Counter, defaultdict

# ============================================================
# 配置
# ============================================================
FEISHU_APP_ID = os.environ.get("FEISHU_APP_ID", "")
FEISHU_APP_SECRET = os.environ.get("FEISHU_APP_SECRET", "")
FEISHU_API_BASE = os.environ.get("FEISHU_API_BASE_URL", "https://open.feishu.cn/open-apis")

BITABLE_APP_TOKEN = "VU3hbjRyuabLhAseoK3ckzOzndg"
TABLE_ID = "tblofr6TCloHk5Zb"

REPORT_DIR = os.path.expanduser("~/scorer_reports")
EVOLUTION_DIR = os.path.expanduser("~/scorer_evolution")
os.makedirs(EVOLUTION_DIR, exist_ok=True)

PROCESSING_FLAG_FIELD = "跟进进度"

# ============================================================
# 维度配置（可自更新）
# ============================================================
DIMENSION_CONFIG = {
    "生产效率": {"weight": 0.20, "questions": ["Q7", "Q8"], "fenlei": "生产效率", "feishu_formula": "AVERAGE(Q7,Q8)*0.20"},
    "质量控制": {"weight": 0.15, "questions": ["Q9", "Q10"], "fenlei": "质量控制", "feishu_formula": "AVERAGE(Q9,Q10)*0.15"},
    "库存物流": {"weight": 0.15, "questions": ["Q11", "Q12"], "fenlei": "库存与物流", "feishu_formula": "AVERAGE(Q11,Q12)*0.15"},
    "设备管理": {"weight": 0.10, "questions": ["Q13", "Q14"], "fenlei": "设备管理", "feishu_formula": "AVERAGE(Q13,Q14)*0.10"},
    "人员效率": {"weight": 0.10, "questions": ["Q15", "Q16"], "fenlei": "人员效率", "feishu_formula": "AVERAGE(Q15,Q16)*0.10"},
    "现场管理": {"weight": 0.10, "questions": ["Q17", "Q18"], "fenlei": "现场管理", "feishu_formula": "AVERAGE(Q17,Q18)*0.10"},
    "计划交付": {"weight": 0.10, "questions": ["Q19", "Q20"], "fenlei": "计划交付", "feishu_formula": "AVERAGE(Q19,Q20)*0.10"},
    "数字化": {"weight": 0.10, "questions": ["Q21", "Q22"], "fenlei": "数字化", "feishu_formula": "AVERAGE(Q21,Q22)*0.10"},
}

# 飞书字段名映射
FIELD_MAP = {
    "Q7": {"name": "Q7. 设备利用率情况如何？", "score_field": "生产效率Q7"},
    "Q8": {"name": "Q8. 是否经常加班仍无法按时交付？", "score_field": "生产效率Q8"},
    "Q9": {"name": "Q9. 产品不良率水平如何？", "score_field": "质量控制Q9"},
    "Q10": {"name": "Q10. 是否存在重复返工问题？", "score_field": "质量控制Q10"},
    "Q11": {"name": "Q11. 原材料和在制品库存情况？", "score_field": "库存与物流Q11"},
    "Q12": {"name": "Q12. 现场是否存在找料、等料现象？", "score_field": "库存与物流Q12"},
    "Q13": {"name": "Q13. 设备故障频率如何？", "score_field": "设备管理Q13"},
    "Q14": {"name": "Q14. 是否有系统的设备点检和保养机制？", "score_field": "设备管理Q14"},
    "Q15": {"name": "Q15. 是否存在人员冗余或等待浪费？", "score_field": "人员效率Q15"},
    "Q16": {"name": "Q16. 是否过度依赖熟练工？", "score_field": "人员效率Q16"},
    "Q17": {"name": "Q17. 现场（车间）是否整洁有序？", "score_field": "现场管理评分Q17"},
    "Q18": {"name": "Q18. 现场是否有明确的标识、看板和标准？", "score_field": "现场管理评分Q18"},
    "Q19": {"name": "Q19. 订单交付及时率如何？", "score_field": "计划交付Q19"},
    "Q20": {"name": "Q20. 生产计划是否频繁变更？", "score_field": "计划交付Q20"},
    "Q21": {"name": "Q21. 工厂是否使用了ERP/MES等信息化系统？", "score_field": "数字化Q21"},
    "Q22": {"name": "Q22. 关键生产数据是否实时可见？", "score_field": "数字化Q22"},
    # 新字段 (v2.1)
    "Q28": {"name": "Q28. 您的工厂最急需改善的领域是？", "score_field": None},
    "Q29": {"name": "Q29. 您是通过什么渠道了解到我们的？", "score_field": None},
}

DIM_SCORE_FIELDS = [
    ("生产效率", "生产效率评分"),
    ("质量控制", "质量控制评分"),
    ("库存物流", "库存物流评分"),
    ("设备管理", "设备管理评分"),
    ("人员效率", "人员效率评分"),
    ("现场管理", "现场管理评分"),
    ("计划交付", "计划交付评分"),
    ("数字化", "数字化评分"),
]


# ============================================================
# 飞书 API 客户端
# ============================================================
class FeishuClient:
    def __init__(self):
        self._token = None
        self._token_expire = 0
        self._import_urllib()
    
    def _import_urllib(self):
        import urllib.request, urllib.error
        self.request = urllib.request
        self.erro = urllib.error
    
    def _get_token(self):
        import json
        now = time.time()
        if self._token and now < self._token_expire - 60:
            return self._token
        data = json.dumps({
            "app_id": FEISHU_APP_ID,
            "app_secret": FEISHU_APP_SECRET
        }).encode("utf-8")
        req = self.request.Request(
            f"{FEISHU_API_BASE}/auth/v3/tenant_access_token/internal",
            data=data, headers={"Content-Type": "application/json"}, method="POST")
        with self.request.urlopen(req) as resp:
            result = json.loads(resp.read())
            if result.get("code") != 0:
                raise Exception(f"Token获取失败: {result.get('msg', 'unknown')}")
            self._token = result["tenant_access_token"]
            self._token_expire = now + result.get("expire", 7200)
            return self._token
    
    def _request(self, method, path, body=None):
        token = self._get_token()
        url = f"{FEISHU_API_BASE}{path}"
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        data = json.dumps(body).encode("utf-8") if body else None
        req = self.request.Request(url, data=data, headers=headers, method=method)
        try:
            with self.request.urlopen(req) as resp:
                return json.loads(resp.read())
        except self.erro.HTTPError as e:
            raise Exception(f"API请求失败 [{e.code}]: {e.read().decode()}")
    
    def list_records(self, page_size=50, page_token=None):
        path = f"/bitable/v1/apps/{BITABLE_APP_TOKEN}/tables/{TABLE_ID}/records?page_size={page_size}"
        if page_token:
            path += f"&page_token={page_token}"
        return self._request("GET", path)
    
    def update_record(self, record_id, fields):
        path = f"/bitable/v1/apps/{BITABLE_APP_TOKEN}/tables/{TABLE_ID}/records/{record_id}"
        return self._request("PUT", path, {"fields": fields})
    
    def get_fields(self):
        path = f"/bitable/v1/apps/{BITABLE_APP_TOKEN}/tables/{TABLE_ID}/fields"
        return self._request("GET", path)


# ============================================================
# 核心评分引擎
# ============================================================
class ScoringEngine:
    def __init__(self, config=None):
        self.dim_config = config or DIMENSION_CONFIG
    
    def _extract_text(self, fields, field_name):
        raw = fields.get(field_name, "")
        if isinstance(raw, str): return raw
        if isinstance(raw, list):
            texts = [item.get("text", "") if isinstance(item, dict) else str(item) for item in raw]
            return "".join(texts)
        if isinstance(raw, dict):
            vals = raw.get("value", [])
            return str(vals[0]) if vals else ""
        return str(raw)
    
    def _get_score_value(self, fields, score_field_name):
        """从飞书字段中提取评分值"""
        field = fields.get(score_field_name, {})
        if isinstance(field, dict):
            vals = field.get("value", [])
            return float(vals[0]) if vals else 0.0
        if isinstance(field, (int, float)):
            return float(field)
        return 0.0
    
    def extract_all_scores(self, fields):
        """提取所有维度评分"""
        scores = {}
        for dim_name, score_field_name in DIM_SCORE_FIELDS:
            scores[dim_name] = self._get_score_value(fields, score_field_name)
        return scores
    
    def compute_total(self, dim_scores):
        total = 0.0
        for dim, cfg in self.dim_config.items():
            total += dim_scores.get(dim, 0) * cfg["weight"]
        return round(total, 3)
    
    def get_rating(self, total_score):
        thresholds = [
            (4.5, "A级 卓越", "精益管理成熟，可作为标杆案例"),
            (3.5, "B级 良好", "有精益基础，改善空间明确"),
            (2.5, "C级 注意", "精益基础薄弱，需系统性改善"),
            (0.0, "D级 风险", "管理水平亟待提升，改善需求迫切"),
        ]
        for threshold, grade, desc in thresholds:
            if total_score >= threshold:
                return grade, desc
        return "D级 风险", "管理水平亟待提升"
    
    def compute_sales_grade(self, fields):
        loss_raw = self._extract_text(fields, "Q24. 以上问题每年大概造成多少损失？（单选题）")
        mapping = [
            ("50万以下", "C级商机", 25),
            ("50–200万", "B级商机", 125),
            ("200–500万", "A级商机", 350),
            ("500–1000万", "S级商机", 750),
            ("1000万以上", "S级商机", 1500),
        ]
        for keyword, grade, mid in mapping:
            if keyword in loss_raw:
                return grade, mid, loss_raw
        return "待评估", 0, loss_raw


# ============================================================
# 问卷质量分析（自进化核心）
# ============================================================
class QuestionnaireAnalyzer:
    """
    问卷质量分析系统 — 评估问卷的有效性并给出改进建议
    
    分析维度：
    1. 区分度分析 — 每个问题的回答是否分布均匀，能否有效区分客户
    2. 缺失率分析 — 哪些问题客户跳过最多（可考虑移除或重新设计）
    3. 相关性分析 — 各问题与最终评分的相关性（低相关性问题可优化）
    4. 时效性分析 — 问卷整体完成率与趋势
    """
    
    def __init__(self, client: FeishuClient):
        self.client = client
    
    def fetch_all_records(self) -> list:
        """获取所有记录"""
        all_records = []
        page_token = None
        while True:
            result = self.client.list_records(page_size=50, page_token=page_token)
            items = result.get("data", {}).get("items", [])
            all_records.extend(items)
            has_more = result.get("data", {}).get("has_more", False)
            if not has_more:
                break
            page_token = result.get("data", {}).get("page_token")
        return all_records
    
    def _get_q_score(self, fields, score_field):
        """获取单题评分值"""
        f = fields.get(score_field, {})
        if isinstance(f, dict):
            vals = f.get("value", [])
            return vals[0] if vals else None
        return None
    
    def analyze_discrimination(self, records: list) -> dict:
        """
        区分度分析：计算每题得分分布和标准差
        标准差 < 0.8 → 区分度低（大家答得差不多，区分力弱）
        标准差 0.8-1.2 → 区分度中等
        标准差 > 1.2 → 区分度好
        """
        result = {}
        
        for dim_name, score_field_name in DIM_SCORE_FIELDS:
            scores = []
            for r in records:
                fields = r.get("fields", {})
                s = self._get_q_score(fields, score_field_name)
                if s is not None:
                    scores.append(s)
            
            if not scores:
                result[dim_name] = {"status": "无数据", "scores": []}
                continue
            
            n = len(scores)
            mean = sum(scores) / n
            variance = sum((s - mean) ** 2 for s in scores) / n
            std = math.sqrt(variance)
            
            # 分布分析
            count_1 = sum(1 for s in scores if s <= 1.5)
            count_2 = sum(1 for s in scores if 1.5 < s <= 2.5)
            count_3 = sum(1 for s in scores if 2.5 < s <= 3.5)
            count_4 = sum(1 for s in scores if 3.5 < s <= 4.5)
            count_5 = sum(1 for s in scores if s > 4.5)
            
            # 判定
            if std < 0.8:
                discrimination = "弱 — 区分度不足，难以区分客户水平"
                suggestion = "考虑调整选项设置，增加区分粒度"
                priority = "中"
            elif std < 1.2:
                discrimination = "中等 — 有一定区分能力"
                suggestion = "保持现状，继续观察"
                priority = "低"
            else:
                discrimination = "好 — 能有效区分客户水平"
                suggestion = "优秀，保持"
                priority = "低"
            
            # 偏态分析
            skew_type = "正态分布"
            if count_1 + count_2 > n * 0.6:
                skew_type = "左偏 — 大多数客户得分偏低"
            elif count_4 + count_5 > n * 0.6:
                skew_type = "右偏 — 大多数客户得分偏高"
            
            result[dim_name] = {
                "样本量": n,
                "均值": round(mean, 2),
                "标准差": round(std, 2),
                "区分度": discrimination,
                "分布": {"1-1.5分": count_1, "2分": count_2, "3分": count_3, "4分": count_4, "5分": count_5},
                "偏态分析": skew_type,
                "建议": suggestion,
                "优先级": priority,
            }
        
        return result
    
    def analyze_pain_points(self, records: list) -> dict:
        """分析Q23/Q24 — 客户痛点与损失分布 (v2.1: 新增Q28/Q29分析)"""
        q23_options = Counter()
        q24_options = Counter()
        q28_options = Counter()  # 改善优先级
        q29_options = Counter()  # 获客渠道
        
        for r in records:
            fields = r.get("fields", {})
            q23 = fields.get("Q23. 当前工厂面临的最大问题是什么？（多选题）", [])
            if isinstance(q23, list):
                for opt in q23:
                    q23_options[opt] += 1
            
            q24 = self._extract_text_simple(fields, "Q24. 以上问题每年大概造成多少损失？（单选题）")
            if q24:
                q24_options[q24] += 1
            
            # 新字段Q28/Q29
            q28 = self._extract_text_simple(fields, "您的工厂最急需改善的领域是？（单选题）")
            if q28 and q28 not in ["", "-"]:
                q28_options[q28] += 1
            
            q29 = self._extract_text_simple(fields, "您是通过什么渠道了解到我们的？")
            if q29 and q29 not in ["", "-"]:
                q29_options[q29] += 1
        
        result = {
            "q23_pain_points": dict(q23_options.most_common()),
            "q24_loss_distribution": dict(q24_options.most_common()),
        }
        
        if q28_options:
            result["q28_priority"] = dict(q28_options.most_common())
        
        if q29_options:
            result["q29_channel"] = dict(q29_options.most_common())
        
        return result
    
    def _extract_text_simple(self, fields, field_name):
        raw = fields.get(field_name, "")
        if isinstance(raw, str): return raw
        if isinstance(raw, list):
            texts = [item.get("text", "") if isinstance(item, dict) else str(item) for item in raw]
            return "".join(texts)
        return str(raw)
    
    def analyze_willingness(self, records: list) -> dict:
        """分析Q25/Q26 — 客户转化意愿"""
        want_report = Counter()
        want_consult = Counter()
        
        for r in records:
            fields = r.get("fields", {})
            q25 = self._extract_text_simple(fields, "Q25.愿意免费获得初步诊断分析报告吗？")
            if q25:
                want_report[q25] += 1
            q26 = self._extract_text_simple(fields, "Q26.是否愿意预约30分钟专家在线解读？")
            if q26:
                want_consult[q26] += 1
        
        # 转化率
        total = len(records)
        report_yes = sum(v for k, v in want_report.items() if "是" in k)
        consult_yes = sum(v for k, v in want_consult.items() if "是" in k)
        
        return {
            "总样本": total,
            "想要免费报告": f"{report_yes}/{total} ({report_yes/total*100:.1f}%)" if total else "N/A",
            "预约解读意愿": f"{consult_yes}/{total} ({consult_yes/total*100:.1f}%)" if total else "N/A",
            "q25_detail": dict(want_report),
            "q26_detail": dict(want_consult),
        }
    
    def analyze_industry_distribution(self, records: list) -> dict:
        """分析客户行业分布"""
        industries = Counter()
        employees = Counter()
        revenues = Counter()
        
        for r in records:
            fields = r.get("fields", {})
            q2 = self._extract_text_simple(fields, "Q2. 所属行业（单选题）")
            if q2: industries[q2] += 1
            q4 = self._extract_text_simple(fields, "Q4. 员工人数（单选题）")
            if q4: employees[q4] += 1
            q3 = self._extract_text_simple(fields, "Q3. 年营业额（单选题）")
            if q3: revenues[q3] += 1
        
        return {
            "行业分布": dict(industries.most_common()),
            "员工规模分布": dict(employees.most_common()),
            "营收分布": dict(revenues.most_common()),
        }
    
    def generate_evolution_suggestions(self, discrimination: dict, pain_points: dict) -> list:
        """生成问卷改进建议"""
        suggestions = []
        
        # 1. 基于区分度给出建议
        low_disc = [(dim, info) for dim, info in discrimination.items()
                    if info.get("标准差", 1) < 0.8 and info.get("样本量", 0) >= 3]
        if low_disc:
            for dim, info in low_disc:
                suggestions.append({
                    "类型": "区分度优化",
                    "维度": dim,
                    "问题": f"区分度偏低（标准差={info['标准差']}），客户得分集中在同一区间",
                    "建议": "考虑增加选项间的区分度，细化评分描述",
                    "优先级": info.get("优先级", "中"),
                })
        
        # 2. 基于样本量建议
        sample_sizes = [info.get("样本量", 0) for info in discrimination.values()]
        total = max(sample_sizes) if sample_sizes else 0
        suggestions.append({
            "类型": "数据积累",
            "维度": "全局",
            "问题": f"当前共有 {total} 条样本数据",
            "建议": f"建议至少积累 30 条样本后再做权重调优。当前进度 {total}/30",
            "优先级": "低" if total >= 30 else "中",
        })
        
        # 3. 基于客户痛点建议
        if pain_points and "q23_pain_points" in pain_points:
            top_pain = list(pain_points["q23_pain_points"].keys())[:3] if pain_points["q23_pain_points"] else []
            if top_pain:
                suggestions.append({
                    "类型": "问卷内容优化",
                    "维度": "全局",
                    "问题": f"客户最集中的痛点是: {', '.join(top_pain)}",
                    "建议": f"考虑在问卷中增加针对'{top_pain[0]}'的细化问题",
                    "优先级": "低",
                })
        
        # 4. 基于转化率建议
        if pain_points and "q24_loss_distribution" in pain_points:
            loss_dist = pain_points["q24_loss_distribution"]
            if loss_dist:
                top_loss = list(loss_dist.keys())[0]
                suggestions.append({
                    "类型": "评分模型",
                    "维度": "损失估算",
                    "问题": f"客户最常报告的损失范围是: {top_loss}",
                    "建议": "确认损失估算公式与该区间匹配",
                    "优先级": "低",
                })
        
        return suggestions
    
    def generate_full_report(self) -> dict:
        """生成完整的问卷质量分析报告"""
        print("📊 正在获取所有问卷数据...")
        records = self.fetch_all_records()
        print(f"   共获取 {len(records)} 条记录\n")
        
        if not records:
            return {"status": "无数据", "message": "数据库中暂无问卷记录"}
        
        print("📊 分析区分度...")
        discrimination = self.analyze_discrimination(records)
        
        print("📊 分析客户痛点...")
        pain_points = self.analyze_pain_points(records)
        
        print("📊 分析转化意愿...")
        willingness = self.analyze_willingness(records)
        
        print("📊 分析客户画像...")
        industry_dist = self.analyze_industry_distribution(records)
        
        print("📊 生成进化建议...")
        suggestions = self.generate_evolution_suggestions(discrimination, pain_points)
        
        report = {
            "report_time": datetime.now().isoformat(),
            "total_records": len(records),
            "discrimination_analysis": discrimination,
            "pain_points": pain_points,
            "conversion_willingness": willingness,
            "customer_profile": industry_dist,
            "evolution_suggestions": suggestions,
            "dimension_config": DIMENSION_CONFIG,
        }
        
        # 保存分析报告
        report_path = os.path.join(EVOLUTION_DIR, f"问卷分析_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        print(f"\n✅ 问卷分析报告已保存: {report_path}")
        
        return report


# ============================================================
# 评分师运营报告生成
# ============================================================
def generate_scorer_stats(records: list) -> dict:
    """生成评分师运营统计数据"""
    processed = sum(1 for r in records if r.get("fields", {}).get(PROCESSING_FLAG_FIELD) == "已生成报告")
    pending = sum(1 for r in records if r.get("fields", {}).get(PROCESSING_FLAG_FIELD) in ["待联系", "", None])
    total = len(records)
    
    # 评级分布
    ratings = Counter()
    for r in records:
        fields = r.get("fields", {})
        rating = fields.get("综合评级", {})
        if isinstance(rating, dict):
            vals = rating.get("value", [])
            if vals and isinstance(vals[0], dict):
                ratings[vals[0].get("text", "未知")] += 1
        elif isinstance(rating, str):
            ratings[rating] += 1
    
    return {
        "总记录数": total,
        "已处理": processed,
        "待处理": pending,
        "处理率": f"{processed/total*100:.1f}%" if total else "0%",
        "评级分布": dict(ratings.most_common()),
    }



# ============================================================
# HTML报告生成器
# ============================================================
def generate_diagnosis_report_html(company, contact, dim_scores, total_score, rating, rating_desc, loss_label, sales_grade):
    """生成免费诊断报告HTML"""
    now_str = datetime.now().strftime("%Y-%m-%d")
    
    sorted_dims = sorted(dim_scores.items(), key=lambda x: x[1])
    worst_3 = sorted_dims[:3] if len(sorted_dims) >= 3 else sorted_dims
    best_1 = sorted_dims[-1:] if sorted_dims else []
    
    def score_color(s):
        if s >= 4.0: return "#16a34a"
        if s >= 3.0: return "#ca8a04"
        if s >= 2.0: return "#f97316"
        return "#dc2626"
    
    dim_bars = ""
    for name, score in sorted_dims:
        pct = int((score / 5.0) * 100)
        color = score_color(score)
        dim_bars += f"""
    <div style="display:flex;align-items:center;padding:8px 0;border-bottom:1px solid #f0f0f0;">
      <div style="width:100px;font-size:13px;color:#555;">{name}</div>
      <div style="flex:1;height:16px;background:#f0f0f0;border-radius:8px;margin:0 12px;overflow:hidden;">
        <div style="height:100%;width:{pct}%;background:{color};border-radius:8px;"></div>
      </div>
      <div style="width:36px;font-size:15px;font-weight:700;color:{color};text-align:right;">{score:.1f}</div>
    </div>"""
    
    top3_html = ""
    for i, (name, score) in enumerate(worst_3):
        top3_html += f"<li>{i+1}. {name}（{score:.1f}分）</li>"
    
    best_html = f"<span style='color:#16a34a;font-weight:600;'>✅ 优势维度：{best_1[0][0]}（{best_1[0][1]:.1f}分）</span>" if best_1 else ""
    
    loss_mid = 350
    if "50万以下" in loss_label: loss_mid = 25
    elif "50" in loss_label: loss_mid = 125
    elif "200" in loss_label: loss_mid = 350
    elif "500" in loss_label: loss_mid = 750
    elif "1000" in loss_label: loss_mid = 1500
    
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8">
<title>精益智能工厂免费诊断报告 - {company}</title>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
  *{{margin:0;padding:0;box-sizing:border-box;}}
  body{{font-family:-apple-system,sans-serif;background:#f5f7fa;color:#1a2332;padding:20px;}}
  .c{{max-width:760px;margin:0 auto;background:#fff;border-radius:16px;overflow:hidden;box-shadow:0 4px 20px rgba(0,0,0,0.06);}}
  .h{{background:linear-gradient(135deg,#1a365d,#2d5a8e);padding:32px 36px 28px;color:#fff;}}
  .h .l{{display:inline-block;background:rgba(255,255,255,0.12);padding:3px 12px;border-radius:14px;font-size:11px;margin-bottom:10px;}}
  .h h1{{font-size:22px;font-weight:700;}}
  .h .cname{{font-size:15px;opacity:0.85;margin-top:8px;}}
  .h .m{{font-size:11px;opacity:0.6;margin-top:4px;}}
  .b{{padding:28px 36px;}}
  .s{{display:flex;gap:20px;padding:20px 24px;background:#f8fafc;border-radius:12px;margin-bottom:24px;}}
  .s .big{{font-size:34px;font-weight:700;color:#1a365d;}}
  .s .info{{flex:1;}}
  .s .info .g{{font-size:17px;font-weight:700;}}
  .s .info .g .tag{{display:inline-block;margin-left:8px;padding:2px 10px;font-size:11px;border-radius:10px;background:#fee2e2;color:#b91c1c;font-weight:600;}}
  .s .info .d{{font-size:12px;color:#666;margin-top:4px;line-height:1.5;}}
  .st{{font-size:14px;font-weight:700;color:#1a365d;margin:18px 0 10px;padding-bottom:6px;border-bottom:2px solid #eef2f6;}}
  .lg{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px;margin-bottom:18px;}}
  .li{{text-align:center;padding:14px;background:#f8fafc;border-radius:10px;border:1px solid #eef2f6;}}
  .li .lbl{{font-size:10px;color:#888;margin-bottom:2px;}}
  .li .val{{font-size:20px;font-weight:700;}}
  .fb{{padding:14px 18px;border-radius:10px;margin-bottom:14px;font-size:12px;line-height:1.6;}}
  .ca{{text-align:center;padding:20px;background:linear-gradient(135deg,#1a365d,#2d5a8e);border-radius:12px;color:#fff;margin-top:18px;}}
  .ca h3{{font-size:14px;font-weight:600;}}
  .ca p{{font-size:11px;opacity:0.8;margin-top:4px;}}
  .ft{{text-align:center;padding:14px;font-size:10px;color:#aaa;border-top:1px solid #eef2f6;}}
  .disc{{font-size:9px;color:#999;padding:10px 14px;background:#fafafa;border-radius:8px;margin-top:12px;}}
</style></head>
<body>
<div class="c">
  <div class="h">
    <div class="l">📋 免费诊断报告</div>
    <h1>精益智能工厂初步诊断<br>分析报告</h1>
    <div class="cname">🏢 {company}</div>
    <div class="m">📅 {now_str}</div>
  </div>
  <div class="b">
    <div class="s">
      <div><div class="big">{total_score:.2f}</div><div style="font-size:11px;color:#888;">/ 5.00</div></div>
      <div class="info">
        <div class="g">综合评分 · {rating.split(' ')[0] if ' ' in rating else rating}<span class="tag">{rating}</span></div>
        <div class="d">{rating_desc}</div>
      </div>
    </div>
    
    <div class="st">📊 八维诊断评分</div>
    {dim_bars}
    
    <div class="st">💰 损失与商机评估</div>
    <div class="lg">
      <div class="li"><div class="lbl">年度损失（自评）</div><div class="val" style="color:#b91c1c;font-size:15px;">{loss_label}</div></div>
      <div class="li"><div class="lbl">商机等级</div><div class="val" style="color:#ca8a04;font-size:17px;">{sales_grade}</div></div>
      <div class="li"><div class="lbl">改善潜力</div><div class="val" style="color:#16a34a;font-size:15px;">约{loss_mid}万</div></div>
    </div>
    
    <div class="st">🔍 Top3改善方向</div>
    <div class="fb" style="background:#fef2f2;border:1px solid #fecaca;color:#991b1b;">
      <ol style="padding-left:16px;">{top3_html}</ol>
    </div>
    
    {f'<div class="fb" style="background:#f0fdf4;border:1px solid #86efac;color:#166534;">{best_html}</div>' if best_html else ''}
    
    <div class="ca">
      <h3>📞 想深入了解改善方案？</h3>
      <p>以上为初步诊断。如需详细改善路线图，请联系：<br>
      <strong>思派工业技术（深圳）有限公司 · 联系人：{contact}</strong></p>
    </div>
    
    <div class="disc">📌 本报告由精益智能工厂诊断系统基于线上问卷数据自动生成，仅供参考，不构成正式咨询意见。</div>
  </div>
  <div class="ft">思派工业技术 · 精益智能工厂领航员 · 评分师 自动生成</div>
</div>
</body>
</html>"""


# ============================================================
# 完整工作循环
# ============================================================
def run_full_cycle(client: FeishuClient):
    """
    评分师完整工作循环：
    Step 1: 监控 -> 获取所有记录
    Step 2: 评分 -> 处理待处理记录生成评分
    Step 3: 报告 -> 生成诊断报告
    Step 4: 反馈 -> 更新飞书状态
    Step 5: 进化 -> 分析问卷质量，生成改进建议
    """
    print(f"\n{'='*60}")
    print(f"🤖 评分师 · 完整工作循环 v2.0")
    print(f"{'='*60}\n")
    
    # Step 1: 获取所有数据
    print("🔍 Step 1: 监控 — 获取问卷数据")
    all_records = []
    page_token = None
    while True:
        result = client.list_records(page_size=50, page_token=page_token)
        items = result.get("data", {}).get("items", [])
        all_records.extend(items)
        has_more = result.get("data", {}).get("has_more", False)
        if not has_more:
            break
        page_token = result.get("data", {}).get("page_token")
    print(f"   共 {len(all_records)} 条记录\n")
    
    # Step 2: 处理待处理记录
    print("📊 Step 2: 评分 — 处理待处理记录")
    engine = ScoringEngine()
    pending_records = [r for r in all_records if r.get("fields", {}).get(PROCESSING_FLAG_FIELD) in ["待联系", "", None]]
    processed_count = 0
    
    for record in pending_records:
        record_id = record.get("record_id", "")
        fields = record.get("fields", {})
        
        dim_scores = engine.extract_all_scores(fields)
        total_score = engine.compute_total(dim_scores)
        rating, rating_desc = engine.get_rating(total_score)
        sales_grade, loss_mid, loss_label = engine.compute_sales_grade(fields)
        
        print(f"   处理 {record_id}: {total_score:.2f} → {rating} | 损失: {loss_label} → {sales_grade}")
        
        # 更新飞书状态
        try:
            client.update_record(record_id, {PROCESSING_FLAG_FIELD: "已生成报告"})
            processed_count += 1
        except Exception as e:
            print(f"   ⚠️ 更新失败: {e}")
    
    print(f"   新处理: {processed_count} 条 | 跳过: {len(all_records) - len(pending_records)} 条\n")
    
    # Step 3: 生成免费诊断报告
    print("📄 Step 3: 报告 — 生成诊断分析报告")
    stats = generate_scorer_stats(all_records)
    print(f"   总记录: {stats['总记录数']} | 已处理: {stats['已处理']} | 待处理: {stats['待处理']}")
    
    # 为每个新处理的记录生成HTML报告
    for record in pending_records:
        record_id = record.get("record_id", "")
        fields = record.get("fields", {})
        try:
            dim_scores = engine.extract_all_scores(fields)
            total_score = engine.compute_total(dim_scores)
            rating, rating_desc = engine.get_rating(total_score)
            sales_grade, loss_mid, loss_label = engine.compute_sales_grade(fields)
            
            company = engine._extract_text(fields, "Q1. 企业名称（填空题，必填）")
            contact = engine._extract_text(fields, "Q29.联系人和联系方式（手机号/微信，必填）")
            
            # Generate simple HTML report
            report_html = generate_diagnosis_report_html(company, contact, dim_scores, total_score, rating, rating_desc, loss_label, sales_grade)
            report_path = os.path.join(REPORT_DIR, f"诊断报告_{company or record_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html")
            with open(report_path, "w", encoding="utf-8") as f:
                f.write(report_html)
            print(f"   📄 报告已生成: {report_path}")
        except Exception as e:
            print(f"   ⚠️ 报告生成失败 ({record_id}): {e}")
    
    # Step 4: 保存运营统计
    print("📈 Step 4: 反馈 — 更新运营数据")
    stats_path = os.path.join(EVOLUTION_DIR, f"运营统计_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    with open(stats_path, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
    print(f"   统计已保存: {stats_path}\n")
    
    # Step 5: 进化 — 问卷质量分析
    print("🧬 Step 5: 进化 — 问卷质量分析与改进建议")
    analyzer = QuestionnaireAnalyzer(client)
    
    try:
        analysis = analyzer.generate_full_report()
        
        print(f"\n{'='*60}")
        print(f"🧬 自进化建议摘要")
        print(f"{'='*60}")
        
        for s in analysis.get("evolution_suggestions", []):
            icon = "🔴" if s["优先级"] == "高" else "🟡" if s["优先级"] == "中" else "🟢"
            print(f"  {icon} [{s['类型']}] {s['建议']} (优先级: {s['优先级']})")
        
        # 维度评分分布摘要
        print(f"\n  维度评分分布:")
        for dim, info in analysis.get("discrimination_analysis", {}).items():
            bar = "█" * int(info.get("均值", 0) * 4)
            print(f"    {dim}: {info.get('均值', 0):.1f} {bar} (σ={info.get('标准差', 0):.2f})")
        
        print(f"\n  客户转化:")
        conv = analysis.get("conversion_willingness", {})
        print(f"    想要免费报告: {conv.get('q25_detail', 'N/A')}")
        print(f"    预约解读意愿: {conv.get('q26_detail', 'N/A')}")
        
    except Exception as e:
        print(f"   ⚠️ 问卷分析失败（样本量不足）: {e}")
    
    print(f"\n{'='*60}")
    print(f"✅ 评分师工作循环完成")
    print(f"{'='*60}")
    
    # Step 6: PDCA里程碑检查
    pdca_result = PDCACheckpoint.check_milestone(len(all_records))
    if pdca_result["needs_pdca"]:
        print(f"\n🎯 PDCA里程碑触发！")
        for m in pdca_result["milestones_found"]:
            print(f"   [{m['severity']}] {m['trigger']}: {m['description']}")
    
    return stats


def watch_mode(client: FeishuClient, interval: int = 300):
    """持续监控模式"""
    print(f"🔄 评分师监控模式启动，每 {interval} 秒检查一次...")
    known_ids = set()
    cycle_count = 0
    
    while True:
        try:
            result = client.list_records(page_size=50)
            records = result.get("data", {}).get("items", [])
            
            # 检查新记录
            new_records = []
            for r in records:
                rid = r.get("record_id", "")
                status = r.get("fields", {}).get(PROCESSING_FLAG_FIELD, "")
                if rid not in known_ids and status in ["待联系", "", None]:
                    new_records.append(r)
                    known_ids.add(rid)
                elif rid not in known_ids:
                    known_ids.add(rid)
            
            if new_records:
                print(f"\n🔔 发现 {len(new_records)} 条新记录，执行完整工作循环...")
                run_full_cycle(client)
                cycle_count += 1
            
            if cycle_count == 0:
                print(f"⏳ 等待中... ({datetime.now().strftime('%H:%M:%S')}) 已知记录: {len(known_ids)}", end="\r")
            else:
                print(f"⏳ 等待中... ({datetime.now().strftime('%H:%M:%S')}) 循环 {cycle_count} 次", end="\r")
            
        except Exception as e:
            print(f"\n⚠️ 监控异常: {e}")
        
        time.sleep(interval)


# ============================================================
# PDCA里程碑检查
# ============================================================
class PDCACheckpoint:
    """
    PDCA联合评估检查点 — 架构师与评分师的协同评估机制
    
    当累积样本达到特定里程碑时，触发联合评估：
    - 30条 → 首次全面PDCA评估（架构师检查维度定义，评分师检查区分度）
    - 每50条 → 追加检查
    - 异常触发 → 区分度连续偏低时即时触发
    """
    
    CHECKPOINT_FILE = os.path.join(EVOLUTION_DIR, "pdca_checkpoint.json")
    
    @classmethod
    def load_checkpoint(cls) -> dict:
        """加载上次PDCA检查点状态"""
        if os.path.exists(cls.CHECKPOINT_FILE):
            with open(cls.CHECKPOINT_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"last_check_count": 0, "total_checks": 0, "milestones_triggered": [], "last_check_time": None}
    
    @classmethod
    def save_checkpoint(cls, state: dict):
        """保存PDCA检查点"""
        with open(cls.CHECKPOINT_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    
    @classmethod
    def check_milestone(cls, current_count: int) -> dict:
        """检查是否需要触发PDCA评估"""
        state = cls.load_checkpoint()
        last_count = state["last_check_count"]
        
        milestones = []
        
        # 条件1: 首次达到30条 → 全面评估
        if current_count >= 30 and last_count < 30:
            milestones.append({
                "type": "首次全面PDCA评估",
                "trigger": "30+样本里程碑",
                "severity": "重要",
                "description": "已积累30+客户样本，建议架构师与评分师联合评估维度权重和问卷质量"
            })
        
        # 条件2: 每新增50条 → 追加检查
        if current_count >= 50:
            next_50 = ((current_count // 50) * 50)
            if next_50 > 0 and last_count < next_50:
                milestones.append({
                    "type": "例行PDCA评估",
                    "trigger": f"{next_50}条里程碑",
                    "severity": "常规",
                    "description": f"已积累{next_50}+客户样本，执行例行维度权重和问卷质量检查"
                })
        
        if milestones:
            state["last_check_count"] = current_count
            state["total_checks"] += len(milestones)
            state["milestones_triggered"].extend(milestones)
            state["last_check_time"] = datetime.now().isoformat()
            cls.save_checkpoint(state)
        
        return {
            "current_count": current_count,
            "last_check_count": last_count,
            "milestones_found": milestones,
            "total_checks": state["total_checks"],
            "needs_pdca": len(milestones) > 0,
        }
    
    @classmethod
    def generate_pdca_report(cls, discrimination: dict, stats: dict) -> dict:
        """生成PDCA联合评估报告"""
        report = {
            "report_time": datetime.now().isoformat(),
            "report_type": "PDCA联合评估",
            "participants": ["评分师(data_analysis)", "架构师(dimension_review)"],
        }
        
        # 评分师部分：问卷质量
        scorer_findings = []
        for dim, info in discrimination.items():
            if info.get("样本量", 0) < 3:
                continue
            if info.get("标准差", 1) < 0.8:
                scorer_findings.append({
                    "dimension": dim,
                    "issue": "区分度不足",
                    "std": info["标准差"],
                    "mean": info["均值"],
                    "suggestion": "建议架构师重新审视该维度的问题选项设计"
                })
            if "左偏" in info.get("偏态分析", ""):
                scorer_findings.append({
                    "dimension": dim,
                    "issue": "评分左偏（普遍偏低）",
                    "mean": info["均值"],
                    "suggestion": "该维度问题可能标准偏严，或客户群体在该领域普遍薄弱"
                })
        
        report["scorer_assessment"] = {
            "findings": scorer_findings,
            "summary": f"发现 {len(scorer_findings)} 个待关注项" if scorer_findings else "所有维度区分度正常",
        }
        
        # 架构师部分：维度配置检查
        architect_checklist = [
            {
                "item": "维度权重",
                "check": "当前权重是否仍然反映业务重点？",
                "current": DIMENSION_CONFIG,
            },
            {
                "item": "问题选项",
                "check": "是否需要根据区分度分析调整选项？",
                "current": {dim: f"{cfg['questions']}" for dim, cfg in DIMENSION_CONFIG.items()},
            },
            {
                "item": "免费/收费边界",
                "check": "边界规则是否需要更新？",
            },
        ]
        
        report["architect_checklist"] = architect_checklist
        
        # 综合建议
        combined_suggestions = []
        if scorer_findings:
            combined_suggestions.append(f"架构师需优先审查的维度：{', '.join(f['dimension'] for f in scorer_findings)}")
        combined_suggestions.append("建议下次PDCA评估在新增50条样本后执行")
        
        report["combined_suggestions"] = combined_suggestions
        report["stats"] = stats
        
        return report


def pdca_check(client: FeishuClient):
    """执行PDCA里程碑检查"""
    print(f"\n{'='*60}")
    print(f"📋 PDCA联合评估检查")
    print(f"{'='*60}\n")
    
    # 获取所有记录
    all_records = []
    page_token = None
    while True:
        result = client.list_records(page_size=50, page_token=page_token)
        items = result.get("data", {}).get("items", [])
        all_records.extend(items)
        has_more = result.get("data", {}).get("has_more", False)
        if not has_more:
            break
        page_token = result.get("data", {}).get("page_token")
    
    current_count = len(all_records)
    print(f"当前样本量: {current_count}")
    
    # 检查里程碑
    milestone_result = PDCACheckpoint.check_milestone(current_count)
    
    if milestone_result["needs_pdca"]:
        print(f"\n🎯 触发PDCA评估！原因:")
        for m in milestone_result["milestones_found"]:
            print(f"   [{m['severity']}] {m['trigger']}: {m['description']}")
        
        # 生成全量PDCA报告
        if current_count >= 30:
            print("\n📊 生成PDCA联合评估报告...")
            analyzer = QuestionnaireAnalyzer(client)
            discrimination = analyzer.analyze_discrimination(all_records)
            stats_data = generate_scorer_stats(all_records)
            report = PDCACheckpoint.generate_pdca_report(discrimination, stats_data)
            
            report_path = os.path.join(EVOLUTION_DIR, f"PDCA报告_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
            with open(report_path, "w", encoding="utf-8") as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
            
            print(f"   ✅ PDCA报告已保存: {report_path}")
            print(f"\n   评分师发现: {report['scorer_assessment']['summary']}")
            print(f"   架构师检查项: {len(report['architect_checklist'])} 项")
            print(f"   综合建议:")
            for sug in report['combined_suggestions']:
                print(f"     → {sug}")
    else:
        next_milestone = 30 if current_count < 30 else ((current_count // 50) + 1) * 50
        print(f"\n⏳ 无需触发PDCA。下次评估节点: {next_milestone} 条样本")
        print(f"   距下次评估还需: {next_milestone - current_count} 条")
    
    return milestone_result


# ============================================================
# CLI入口
# ============================================================
def main():
    parser = argparse.ArgumentParser(description="评分师 + 架构师 · PDCA联合工作循环 v3.0")
    parser.add_argument("--cycle", action="store_true", help="执行一次完整工作循环")
    parser.add_argument("--watch", action="store_true", help="持续监控模式")
    parser.add_argument("--interval", type=int, default=300, help="监控间隔（秒，默认300）")
    parser.add_argument("--analyze", action="store_true", help="仅执行问卷质量分析")
    parser.add_argument("--stats", action="store_true", help="仅输出运营统计")
    parser.add_argument("--pdca-check", action="store_true", help="检查PDCA里程碑")
    args = parser.parse_args()
    
    if not FEISHU_APP_ID or not FEISHU_APP_SECRET:
        print("❌ 请设置 FEISHU_APP_ID 和 FEISHU_APP_SECRET 环境变量")
        sys.exit(1)
    
    client = FeishuClient()
    
    # 先获取数据
    all_records = []
    page_token = None
    while True:
        result = client.list_records(page_size=50, page_token=page_token)
        items = result.get("data", {}).get("items", [])
        all_records.extend(items)
        has_more = result.get("data", {}).get("has_more", False)
        if not has_more:
            break
        page_token = result.get("data", {}).get("page_token")
    
    if args.stats:
        stats = generate_scorer_stats(all_records)
        print(json.dumps(stats, ensure_ascii=False, indent=2))
    
    elif args.analyze:
        analyzer = QuestionnaireAnalyzer(client)
        report = analyzer.generate_full_report()
        print(json.dumps(report, ensure_ascii=False, indent=2)[:2000])
    
    elif args.pdca_check:
        pdca_check(client)
    
    elif args.watch:
        watch_mode(client, args.interval)
    
    else:  # 默认执行完整工作循环
        run_full_cycle(client)


if __name__ == "__main__":
    main()
