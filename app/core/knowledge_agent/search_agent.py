import json
from langgraph.graph import StateGraph, END
from app.services.llm_service import LLMService
from app.services.web_search_service import WebSearchService
from app.prompts.templates import SEARCH_PLAN_PROMPT, SEARCH_EVALUATE_PROMPT, SEARCH_SUMMARIZE_PROMPT


class SearchAgent:

    MAX_SEARCH_ROUNDS = 3

    def __init__(self, llm_service=None, web_search_service=None):
        self.llm_service = llm_service or LLMService()
        self.web_search_service = web_search_service or WebSearchService()
        self.graph = self._build_graph()

    def _build_graph(self):
        graph = StateGraph(dict)

        graph.add_node("plan_searches", self._plan_searches_node)
        graph.add_node("execute_search", self._execute_search_node)
        graph.add_node("evaluate_knowledge", self._evaluate_knowledge_node)
        graph.add_node("summarize_knowledge", self._summarize_knowledge_node)

        graph.set_entry_point("plan_searches")
        graph.add_edge("plan_searches", "execute_search")
        graph.add_edge("execute_search", "evaluate_knowledge")
        graph.add_conditional_edges(
            "evaluate_knowledge",
            self._should_continue_search,
            {
                "continue": "execute_search",
                "done": "summarize_knowledge",
            }
        )
        graph.add_edge("summarize_knowledge", END)

        return graph.compile()

    def _plan_searches_node(self, state):
        print("=== 规划搜索节点 ===")
        topic = state["topic"]
        prompt = SEARCH_PLAN_PROMPT.format(topic=topic)
        response = self.llm_service.generate(prompt, max_tokens=4096)

        try:
            parsed = self._parse_json_response(response)
            search_queries = parsed.get("search_queries", [])
        except (json.JSONDecodeError, AttributeError):
            print(f"[SearchAgent] 解析搜索规划失败，使用主题作为默认搜索词")
            search_queries = [topic]

        print(f"规划搜索关键词: {search_queries}")
        return {
            "topic": topic,
            "search_queries": search_queries,
            "search_results": state.get("search_results", []),
            "collected_knowledge": state.get("collected_knowledge", ""),
            "search_round": state.get("search_round", 0),
            "max_tokens": state.get("max_tokens", 4096),
        }

    def _execute_search_node(self, state):
        print("=== 执行搜索节点 ===")
        search_queries = state.get("search_queries", [])
        existing_results = state.get("search_results", [])
        search_round = state.get("search_round", 0) + 1

        new_results = []
        for query in search_queries:
            print(f"  搜索: {query}")
            results = self.web_search_service.search(query, max_results=3)
            for r in results:
                new_results.append({
                    "query": query,
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "content": r.get("content", ""),
                })

        all_results = existing_results + new_results
        print(f"  本轮搜索到 {len(new_results)} 条结果，累计 {len(all_results)} 条")

        return {
            "topic": state["topic"],
            "search_queries": search_queries,
            "search_results": all_results,
            "collected_knowledge": state.get("collected_knowledge", ""),
            "search_round": search_round,
            "max_tokens": state.get("max_tokens", 4096),
        }

    def _evaluate_knowledge_node(self, state):
        print("=== 评估知识充分性节点 ===")
        topic = state["topic"]
        search_results = state.get("search_results", [])
        search_round = state.get("search_round", 0)

        knowledge_text = ""
        for i, r in enumerate(search_results):
            knowledge_text += f"\n[{i+1}] 来源: {r.get('title', '')}\n内容: {r.get('content', '')}\n"

        if not knowledge_text.strip():
            knowledge_text = "暂无收集到的知识"

        prompt = SEARCH_EVALUATE_PROMPT.format(
            topic=topic,
            collected_knowledge=knowledge_text
        )
        response = self.llm_service.generate(prompt, max_tokens=4096)

        try:
            parsed = self._parse_json_response(response)
            sufficient = parsed.get("sufficient", False)
            reason = parsed.get("reason", "")
            additional_queries = parsed.get("additional_queries", [])
        except (json.JSONDecodeError, AttributeError):
            print(f"[SearchAgent] 解析评估结果失败，默认知识已充分")
            sufficient = True
            reason = "解析失败，默认充分"
            additional_queries = []

        print(f"  充分性: {sufficient}")
        print(f"  理由: {reason}")
        if additional_queries:
            print(f"  补充搜索词: {additional_queries}")

        return {
            "topic": topic,
            "search_queries": additional_queries,
            "search_results": search_results,
            "collected_knowledge": knowledge_text,
            "search_round": search_round,
            "sufficient": sufficient,
            "max_tokens": state.get("max_tokens", 4096),
        }

    def _should_continue_search(self, state):
        sufficient = state.get("sufficient", False)
        search_round = state.get("search_round", 0)
        has_more_queries = bool(state.get("search_queries", []))

        if sufficient or search_round >= self.MAX_SEARCH_ROUNDS or not has_more_queries:
            print(f"  决策: 结束搜索 (充分={sufficient}, 轮次={search_round})")
            return "done"
        else:
            print(f"  决策: 继续搜索 (轮次={search_round}/{self.MAX_SEARCH_ROUNDS})")
            return "continue"

    def _summarize_knowledge_node(self, state):
        print("=== 整理知识节点 ===")
        topic = state["topic"]
        search_results = state.get("search_results", [])

        results_text = ""
        for i, r in enumerate(search_results):
            results_text += f"\n[{i+1}] 标题: {r.get('title', '')}\n来源: {r.get('url', '')}\n内容: {r.get('content', '')}\n"

        prompt = SEARCH_SUMMARIZE_PROMPT.format(
            topic=topic,
            search_results=results_text
        )
        summary = self.llm_service.generate(prompt, max_tokens=state.get("max_tokens", 4096))

        print(f"  知识整理完成，摘要长度: {len(summary)} 字符")
        return {
            "topic": topic,
            "search_results": search_results,
            "collected_knowledge": summary,
            "search_round": state.get("search_round", 0),
            "sufficient": True,
            "max_tokens": state.get("max_tokens", 4096),
        }

    def _parse_json_response(self, response):
        text = response.strip()

        for marker in ["【最终回答】", "【最终答案】"]:
            if marker in text:
                text = text.split(marker)[-1].strip()

        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()

        first_brace = text.find("{")
        last_brace = text.rfind("}")
        if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
            text = text[first_brace:last_brace + 1]

        return json.loads(text)

    def search(self, topic, max_tokens=4096):
        result = self.graph.invoke({
            "topic": topic,
            "max_tokens": max_tokens,
        })
        return result.get("collected_knowledge", "")
