import json

PATH = r"E:\code\project\Software Engineering Management and Economics_project\POGCC\testing\quality_validation\outputs\quality_validation_results.json"

SCORE_MAP = {
    "人工智能在教育中的应用": {
        "scores": {
            "relevance": 5,
            "authority": 4,
            "coverage": 5,
            "diversity": 5,
            "redundancy": 5,
            "answer_completeness": 5,
            "answer_structure": 4,
            "answer_alignment": 4,
            "answer_uncertainty": 2,
        },
        "coverage": {
            "背景与发展趋势": (True, "answer"),
            "核心技术与应用场景": (True, "answer"),
            "典型案例或成效": (True, "answer"),
            "风险与伦理问题": (True, "answer"),
            "未来展望": (True, "answer"),
        },
        "notes": "Manual scoring based on search titles and answer content; fact-check snippet-based.",
    },
    "碳中和政策对制造业的影响": {
        "scores": {
            "relevance": 5,
            "authority": 5,
            "coverage": 5,
            "diversity": 5,
            "redundancy": 5,
            "answer_completeness": 5,
            "answer_structure": 5,
            "answer_alignment": 4,
            "answer_uncertainty": 2,
        },
        "coverage": {
            "政策背景与目标": (True, "answer"),
            "对生产流程与成本的影响": (True, "answer"),
            "技术改造与绿色转型": (True, "answer"),
            "行业挑战与机会": (True, "answer"),
            "案例或数据支撑": (True, "answer"),
        },
        "notes": "Manual scoring based on search titles and answer content; fact-check snippet-based.",
    },
    "智慧城市中的5G应用": {
        "scores": {
            "relevance": 4,
            "authority": 4,
            "coverage": 4,
            "diversity": 5,
            "redundancy": 5,
            "answer_completeness": 4,
            "answer_structure": 4,
            "answer_alignment": 3,
            "answer_uncertainty": 2,
        },
        "coverage": {
            "5G特性与城市需求匹配": (True, "answer"),
            "交通/安防/能源等应用": (True, "answer"),
            "基础设施建设要点": (True, "answer"),
            "运营与治理挑战": (False, "not explicit"),
            "代表性项目或成效": (True, "answer"),
        },
        "notes": "Manual scoring based on search titles and answer content; governance challenges not explicit; fact-check snippet-based.",
    },
    "医疗健康领域的数字化转型": {
        "scores": {
            "relevance": 4,
            "authority": 3,
            "coverage": 4,
            "diversity": 5,
            "redundancy": 5,
            "answer_completeness": 4,
            "answer_structure": 3,
            "answer_alignment": 3,
            "answer_uncertainty": 2,
        },
        "coverage": {
            "转型驱动力与目标": (True, "answer"),
            "数据与平台建设": (True, "answer"),
            "AI/IoT等技术应用": (True, "answer"),
            "数据隐私与合规": (True, "answer"),
            "实践案例或趋势": (True, "answer"),
        },
        "notes": "Manual scoring based on search titles and answer content; includes vendor sources; fact-check snippet-based.",
    },
}

FACT_MAP = {
    "人工智能在教育中的应用": [
        {
            "claim": "AI可根据学生数据实现个性化学习与定制化内容",
            "verdict": "supported",
            "evidence": "[4] AI能够实时分析学生学习数据并提供个性化内容",
        },
        {
            "claim": "AI可自动批改作业、生成内容以减轻教师负担",
            "verdict": "supported",
            "evidence": "[4] 提到自动批改作业与教学内容生成",
        },
        {
            "claim": "AI在教育中的应用需要监管，且生成内容可能不准确",
            "verdict": "supported",
            "evidence": "[2] 指出生成式AI可能产生与事实不符内容并需监管",
        },
        {
            "claim": "AI可辅助语言学习与无障碍（如语音转文字）",
            "verdict": "supported",
            "evidence": "[3] 提到语言学习与语音转文字支持",
        },
        {
            "claim": "教育AI市场预计2034年突破1120亿美元",
            "verdict": "no_evidence",
            "evidence": "搜索摘要中未出现该市场规模数据",
        },
        {
            "claim": "只有半数师生接受过AI培训",
            "verdict": "no_evidence",
            "evidence": "搜索摘要中未出现相关比例数据",
        },
    ],
    "碳中和政策对制造业的影响": [
        {
            "claim": "制造业碳中和的关键途径包括供给侧减排（清洁能源、改进工艺、碳捕集）",
            "verdict": "supported",
            "evidence": "[1] 供给侧减排与碳捕捉等技术被强调",
        },
        {
            "claim": "中国提出2030年前碳达峰、2060年前实现碳中和",
            "verdict": "supported",
            "evidence": "[1] 2020年提出2030峰值、2060中和目标",
        },
        {
            "claim": "欧盟净零工业法案提出2030年战略性净零技术本土制造能力达到约40%",
            "verdict": "supported",
            "evidence": "[3] 提到2030年达到年度部署需求40%",
        },
        {
            "claim": "德国资助62个氢能项目，总投资约330亿欧元",
            "verdict": "supported",
            "evidence": "[3] 提到62个氢能项目与330亿欧元投资",
        },
        {
            "claim": "特斯拉通过碳积分交易获得17.76亿美元收入（2022年财报）",
            "verdict": "supported",
            "evidence": "[4] 提到特斯拉2022年碳排放积分收入17.76亿美元",
        },
        {
            "claim": "欧盟碳边境调节机制（CBAM）提高高碳行业合规成本",
            "verdict": "no_evidence",
            "evidence": "搜索摘要未出现CBAM或合规成本表述",
        },
        {
            "claim": "苹果要求供应商使用清洁能源带动供应链减碳",
            "verdict": "no_evidence",
            "evidence": "搜索摘要未出现具体企业案例",
        },
    ],
    "智慧城市中的5G应用": [
        {
            "claim": "5G具备高速度、低时延、大连接特性，为智慧城市提供连接能力",
            "verdict": "supported",
            "evidence": "[2] 明确描述5G超高速率、超低时延、超大连接",
        },
        {
            "claim": "智慧城市中5G应用于交通管理与公共安全场景",
            "verdict": "supported",
            "evidence": "[1] 提到交通管理、公共安全等应用场景",
        },
        {
            "claim": "5G与云计算、大数据、AI、物联网融合赋能智慧城市",
            "verdict": "supported",
            "evidence": "[2] 描述与云计算、大数据、AI、物联网融合",
        },
        {
            "claim": "应急响应提速30%+",
            "verdict": "no_evidence",
            "evidence": "搜索摘要未出现该具体数据",
        },
        {
            "claim": "边缘计算将时延降低到毫秒级",
            "verdict": "no_evidence",
            "evidence": "搜索摘要未出现边缘计算时延数据",
        },
        {
            "claim": "2030年IoT市场规模将达6210亿美元",
            "verdict": "no_evidence",
            "evidence": "搜索摘要未出现该市场规模数据",
        },
        {
            "claim": "自动驾驶车路协同时延<10ms",
            "verdict": "no_evidence",
            "evidence": "搜索摘要未出现该时延指标",
        },
    ],
    "医疗健康领域的数字化转型": [
        {
            "claim": "医疗数字化转型以大数据与AI作为重要驱动力",
            "verdict": "supported",
            "evidence": "[2] 提到大数据与人工智能推动数字化医疗",
        },
        {
            "claim": "需要建设数据平台与互联互通标准以打通信息孤岛",
            "verdict": "supported",
            "evidence": "[3] 描述数据标准、互联互通与数据平台建设",
        },
        {
            "claim": "远程医疗与物联网/可穿戴设备用于健康管理",
            "verdict": "supported",
            "evidence": "[5] 提到远程医疗与物联网/可穿戴设备",
        },
        {
            "claim": "数据治理与隐私保护是重要内容",
            "verdict": "supported",
            "evidence": "[5] 提到隐私保护与法律框架",
        },
        {
            "claim": "MIMIC重症医学库用于整合医疗数据",
            "verdict": "no_evidence",
            "evidence": "搜索摘要未出现MIMIC数据库",
        },
        {
            "claim": "HIPAA加密用于保障医疗数据隐私",
            "verdict": "no_evidence",
            "evidence": "搜索摘要未出现HIPAA加密",
        },
    ],
}

with open(PATH, encoding="utf-8") as f:
    data = json.load(f)

for rec in data.get("records", []):
    topic = rec.get("topic")
    if topic in SCORE_MAP:
        rec["scores"].update(SCORE_MAP[topic]["scores"])
        cov_map = SCORE_MAP[topic]["coverage"]
        for item in rec.get("coverage_checklist", []):
            point = item.get("point")
            if point in cov_map:
                covered, evidence = cov_map[point]
                item["covered"] = covered
                item["evidence"] = evidence
        rec["notes"] = SCORE_MAP[topic]["notes"]

    if topic in FACT_MAP:
        claims = FACT_MAP[topic]
        counts = {"supported": 0, "insufficient": 0, "contradicted": 0, "no_evidence": 0}
        for item in claims:
            verdict = item.get("verdict")
            if verdict in counts:
                counts[verdict] += 1
        rec["fact_check"]["claims"] = claims
        rec["fact_check"]["supported"] = counts["supported"]
        rec["fact_check"]["insufficient"] = counts["insufficient"]
        rec["fact_check"]["contradicted"] = counts["contradicted"]
        rec["fact_check"]["no_evidence"] = counts["no_evidence"]

with open(PATH, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print("Updated scores + fact_check in", PATH)
