import argparse
import datetime as dt
import json
import os
import sys
from urllib.parse import urlparse

def find_project_root(start_path):
    current = os.path.abspath(start_path)
    while True:
        if os.path.isdir(os.path.join(current, "app")):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            return os.path.abspath(start_path)
        current = parent


PROJECT_ROOT = find_project_root(os.path.dirname(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.services.web_search_service import WebSearchService
from app.core.knowledge_agent import KnowledgeAgent
from app.services.llm_service import LLMService


def build_topics():
    return [
        {
            "topic": "人工智能在教育中的应用",
            "key_points": [
                "背景与发展趋势",
                "核心技术与应用场景",
                "典型案例或成效",
                "风险与伦理问题",
                "未来展望",
            ],
        },
        {
            "topic": "碳中和政策对制造业的影响",
            "key_points": [
                "政策背景与目标",
                "对生产流程与成本的影响",
                "技术改造与绿色转型",
                "行业挑战与机会",
                "案例或数据支撑",
            ],
        },
        {
            "topic": "智慧城市中的5G应用",
            "key_points": [
                "5G特性与城市需求匹配",
                "交通/安防/能源等应用",
                "基础设施建设要点",
                "运营与治理挑战",
                "代表性项目或成效",
            ],
        },
        {
            "topic": "医疗健康领域的数字化转型",
            "key_points": [
                "转型驱动力与目标",
                "数据与平台建设",
                "AI/IoT等技术应用",
                "数据隐私与合规",
                "实践案例与趋势",
            ],
        },
    ]


def load_topics(path):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError("topics file must be a list of objects")

    for idx, item in enumerate(data):
        if not isinstance(item, dict):
            raise ValueError(f"topic entry {idx} must be an object")
        if "topic" not in item or "key_points" not in item:
            raise ValueError(f"topic entry {idx} must contain topic and key_points")
        if not isinstance(item["key_points"], list):
            raise ValueError(f"key_points in entry {idx} must be a list")

    return data


def domain_from_url(url):
    try:
        return urlparse(url).netloc.lower()
    except Exception:
        return ""


def analyze_search_results(results):
    domains = [domain_from_url(r.get("url", "")) for r in results]
    titles = [r.get("title", "").strip().lower() for r in results if r.get("title")]
    unique_domains = sorted(set([d for d in domains if d]))
    duplicate_title_count = len(titles) - len(set(titles))

    return {
        "result_count": len(results),
        "unique_domains": unique_domains,
        "unique_domain_count": len(unique_domains),
        "duplicate_title_count": max(0, duplicate_title_count),
    }


def build_record(topic_entry, search_results, answer, error=None):
    return {
        "topic": topic_entry["topic"],
        "key_points": topic_entry["key_points"],
        "search_results": search_results,
        "search_stats": analyze_search_results(search_results),
        "answer": answer,
        "scores": {
            "relevance": None,
            "authority": None,
            "coverage": None,
            "diversity": None,
            "redundancy": None,
            "answer_completeness": None,
            "answer_structure": None,
            "answer_alignment": None,
            "answer_uncertainty": None,
        },
        "coverage_checklist": [
            {"point": p, "covered": None, "evidence": ""}
            for p in topic_entry["key_points"]
        ],
        "fact_check": {
            "supported": 0,
            "insufficient": 0,
            "contradicted": 0,
            "no_evidence": 0,
            "claims": [],
        },
        "notes": "",
        "error": error,
    }


def run(args):
    topics = load_topics(args.topics_file) if args.topics_file else build_topics()
    web_search_service = WebSearchService()

    knowledge_agent = None
    init_error = None
    llm_provider = None
    if not args.skip_answer:
        try:
            llm_service = LLMService()
            llm_provider = llm_service.provider_name
            knowledge_agent = KnowledgeAgent(
                llm_service=llm_service,
                web_search_service=web_search_service,
            )
        except Exception as exc:
            init_error = str(exc)

    records = []
    for entry in topics:
        answer = ""
        error = init_error
        try:
            search_results = web_search_service.search(
                entry["topic"],
                max_results=args.max_results,
                search_depth=args.search_depth,
            )
            if knowledge_agent is not None:
                answer = knowledge_agent.process_query(entry["topic"])
        except Exception as exc:
            search_results = []
            error = str(exc)

        records.append(build_record(entry, search_results, answer, error))

    output = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "topic_count": len(topics),
        "max_results": args.max_results,
        "search_depth": args.search_depth,
        "skip_answer": args.skip_answer,
        "llm_provider": llm_provider,
        "init_error": init_error,
        "records": records,
    }

    output_path = args.output
    if not os.path.isabs(output_path):
        output_path = os.path.join(PROJECT_ROOT, output_path)
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"Saved: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Run quality validation data collection for search and QA."
    )
    parser.add_argument(
        "--output",
        default="testing/quality_validation/outputs/quality_validation_results.json",
        help="Output JSON path",
    )
    parser.add_argument(
        "--max-results",
        type=int,
        default=5,
        help="Max search results per topic",
    )
    parser.add_argument(
        "--search-depth",
        default="advanced",
        choices=["advanced", "basic"],
        help="Search depth for Tavily",
    )
    parser.add_argument(
        "--topics-file",
        help="JSON file that defines topics and key_points",
    )
    parser.add_argument(
        "--skip-answer",
        action="store_true",
        help="Skip LLM answer generation to avoid cost",
    )
    args = parser.parse_args()

    run(args)


if __name__ == "__main__":
    main()
