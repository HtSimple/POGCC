import json
from concurrent.futures import ThreadPoolExecutor, as_completed

from langgraph.graph import StateGraph, END
from app.services.llm_service import LLMService
from app.services.web_search_service import WebSearchService
from app.prompts.templates import SEARCH_PLAN_PROMPT, SEARCH_EVALUATE_PROMPT, SEARCH_SUMMARIZE_PROMPT
from app.utils.config import config


class SearchAgent:

    MAX_SEARCH_ROUNDS = 3
    _LOCAL_CHUNK_TEXT_LIMIT = 1800

    @staticmethod
    def _source_tag(result: dict) -> str:
        """区分本地向量库与网络结果，便于下游摘要与排查。"""
        url = str(result.get("url", "") or "")
        title = str(result.get("title", "") or "")
        if url.startswith("local://") or title.startswith("[本地]"):
            return "【RAG本地库】"
        return "【网络搜索】"

    def __init__(self, llm_service=None, web_search_service=None, retrieval_service=None):
        self.llm_service = llm_service or LLMService()
        self.web_search_service = web_search_service or WebSearchService()
        self.retrieval_service = retrieval_service
        self._graph_fast = self._build_fast_graph()
        self._graph_full = self._build_full_graph()

    def _build_fast_graph(self):
        """规划 → 执行检索 → 将结果拼成文本（不调评估 / 整理 LLM）。"""
        graph = StateGraph(dict)
        graph.add_node("plan_searches", self._plan_searches_node)
        graph.add_node("execute_search", self._execute_search_node)
        graph.add_node("materialize_knowledge", self._materialize_knowledge_from_results_node)
        graph.set_entry_point("plan_searches")
        graph.add_edge("plan_searches", "execute_search")
        graph.add_edge("execute_search", "materialize_knowledge")
        graph.add_edge("materialize_knowledge", END)
        return graph.compile()

    def _build_full_graph(self):
        """含评估多轮与整理知识（LLM），需要时 search(..., refine_knowledge=True)。"""
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

    def _format_search_results_as_knowledge(self, search_results: list) -> str:
        knowledge_text = ""
        for i, r in enumerate(search_results):
            tag = self._source_tag(r)
            knowledge_text += f"\n[{i+1}] {tag}\n来源: {r.get('title', '')}\n内容: {r.get('content', '')}\n"
        if not knowledge_text.strip():
            return "暂无收集到的知识"
        return knowledge_text

    def _materialize_knowledge_from_results_node(self, state):
        search_results = state.get("search_results", [])
        knowledge_text = self._format_search_results_as_knowledge(search_results)
        return {
            "topic": state["topic"],
            "search_queries": state.get("search_queries", []),
            "search_results": search_results,
            "collected_knowledge": knowledge_text,
            "search_round": state.get("search_round", 0),
            "max_tokens": state.get("max_tokens", 4096),
        }

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

        print(f"规划搜索关键词（共 {len(search_queries)} 个）:")
        for qi, sq in enumerate(search_queries, 1):
            print(f"  {qi}. {sq}")
        return {
            "topic": topic,
            "search_queries": search_queries,
            "search_results": state.get("search_results", []),
            "collected_knowledge": state.get("collected_knowledge", ""),
            "search_round": state.get("search_round", 0),
            "max_tokens": state.get("max_tokens", 4096),
        }

    def _fetch_results_for_query(self, query: str) -> list[dict]:
        """单条搜索词：本地 RAG + 网络（供并行调用）。"""
        rows: list[dict] = []
        if self.retrieval_service is not None:
            try:
                local_resp = self.retrieval_service.search(query, top_k=5)
                if len(local_resp.results) == 0:
                    print(f"  [本地] 0 条命中: {query[:80]}")
                for item in local_resp.results:
                    text = item.text
                    if len(text) > self._LOCAL_CHUNK_TEXT_LIMIT:
                        text = text[: self._LOCAL_CHUNK_TEXT_LIMIT] + "..."
                    rows.append({
                        "query": query,
                        "chunk_id": item.chunk_id,
                        "title": f"[本地] {item.source_file}",
                        "url": f"local://{item.doc_id}/{item.chunk_id}",
                        "content": text,
                    })
            except Exception as exc:
                print(f"  [本地] 检索失败: {exc}")

        print(f"  搜索: {query}")
        for r in self.web_search_service.search(query, max_results=3):
            rows.append({
                "query": query,
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "content": r.get("content", ""),
            })
        return rows

    def _merge_query_rows(self, rows: list[dict], seen_local_chunks: set[str]) -> list[dict]:
        merged: list[dict] = []
        for row in rows:
            cid = row.pop("chunk_id", None)
            if cid is not None:
                if cid in seen_local_chunks:
                    continue
                seen_local_chunks.add(cid)
            merged.append(row)
        return merged

    def _execute_search_node(self, state):
        print("=== 执行搜索节点 ===")
        search_queries = state.get("search_queries", [])
        existing_results = state.get("search_results", [])
        search_round = state.get("search_round", 0) + 1

        new_results: list[dict] = []
        seen_local_chunks: set[str] = set()

        if not search_queries:
            pass
        elif len(search_queries) == 1:
            new_results = self._merge_query_rows(
                self._fetch_results_for_query(search_queries[0]),
                seen_local_chunks,
            )
        else:
            max_q_workers = int(config.get("search_query_max_workers", 4) or 4)
            max_q_workers = max(1, min(max_q_workers, len(search_queries), 8))
            print(f"  并行执行 {len(search_queries)} 个搜索词 (workers={max_q_workers})")
            with ThreadPoolExecutor(max_workers=max_q_workers) as executor:
                future_map = {
                    executor.submit(self._fetch_results_for_query, q): q
                    for q in search_queries
                }
                for fut in as_completed(future_map):
                    query = future_map[fut]
                    try:
                        rows = fut.result()
                        added = self._merge_query_rows(rows, seen_local_chunks)
                        new_results.extend(added)
                        print(f"  [并行] 词「{query[:50]}」合并 {len(added)} 条")
                    except Exception as exc:
                        print(f"  [并行] 搜索词失败 {query[:60]}: {exc}")

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

        knowledge_text = self._format_search_results_as_knowledge(search_results)

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
            tag = self._source_tag(r)
            results_text += f"\n[{i+1}] {tag}\n标题: {r.get('title', '')}\n来源: {r.get('url', '')}\n内容: {r.get('content', '')}\n"

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

    def search(self, topic, max_tokens=4096, refine_knowledge: bool = False):
        """检索知识材料。

        refine_knowledge=False（默认）：规划 → 执行搜索 → 将检索结果拼接为文本，跳过评估与整理 LLM。
        refine_knowledge=True：走完整流程（评估多轮 + 整理知识摘要）。
        """
        graph = self._graph_full if refine_knowledge else self._graph_fast
        result = graph.invoke({
            "topic": topic,
            "max_tokens": max_tokens,
        })
        return result.get("collected_knowledge", "")
