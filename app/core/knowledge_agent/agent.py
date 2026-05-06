from langgraph.graph import StateGraph, END
from .query_processor import QueryProcessor
from .search_agent import SearchAgent
from .result_generator import ResultGenerator


class KnowledgeAgent:

    def __init__(self, llm_service=None, web_search_service=None):
        self.query_processor = QueryProcessor()
        self.search_agent = SearchAgent(
            llm_service=llm_service,
            web_search_service=web_search_service,
        )
        self.result_generator = ResultGenerator(llm_service=llm_service)
        self.graph = self._build_graph()

    def _build_graph(self):
        graph = StateGraph(dict)

        graph.add_node("process_query", self._process_query_node)
        graph.add_node("retrieve_knowledge", self._retrieve_knowledge_node)
        graph.add_node("generate_answer", self._generate_answer_node)

        graph.add_edge("process_query", "retrieve_knowledge")
        graph.add_edge("retrieve_knowledge", "generate_answer")
        graph.add_edge("generate_answer", END)

        graph.set_entry_point("process_query")

        return graph.compile()

    def _process_query_node(self, state):
        print("=== 处理查询节点 ===")
        query = state["query"]
        processed_query = self.query_processor.process(query)
        print(f"原始查询: {query}")
        print(f"处理后查询: {processed_query}")
        return {
            "query": query,
            "processed_query": processed_query,
            "knowledge": state.get("knowledge", ""),
            "answer": state.get("answer"),
            "max_tokens": state.get("max_tokens", 4096),
        }

    def _retrieve_knowledge_node(self, state):
        print("=== 检索知识节点 ===")
        query = state["query"]

        # === 加入本地知识库检索后参考代码如下 ===
        #
        # # 1. 先查本地知识库
        # local_docs = []
        # if self.vector_db is not None:
        #     local_docs = self.vector_db.search(query, top_k=3)
        #
        # # 2. 判断本地知识是否充分
        # local_knowledge = ""
        # if local_docs:
        #     local_knowledge = "\n".join([f"[本地文档{i+1}] {doc}" for i, doc in enumerate(local_docs)])
        #
        # # 3. 本地知识不足时，补充网络搜索
        # web_knowledge = ""
        # if len(local_docs) < 2:  # 本地检索结果不足2条，认为知识不充分
        #     print("  本地知识不足，启动网络搜索...")
        #     web_knowledge = self.search_agent.search(query)
        #
        # # 4. 合并知识
        # knowledge_parts = []
        # if local_knowledge:
        #     knowledge_parts.append(f"【本地知识库】\n{local_knowledge}")
        # if web_knowledge:
        #     knowledge_parts.append(f"【网络搜索】\n{web_knowledge}")
        # knowledge = "\n\n".join(knowledge_parts) if knowledge_parts else "无相关知识"
        # === 加入本地知识库检索后的参考代码结束 ===

        knowledge = self.search_agent.search(query)  #加入本地知识库检索加入后删去该代码
        print(f"检索到知识摘要长度: {len(knowledge)} 字符")
        return {
            "query": query,
            "processed_query": state["processed_query"],
            "knowledge": knowledge,
            "answer": state.get("answer"),
            "max_tokens": state.get("max_tokens", 4096),
        }

    def _generate_answer_node(self, state):
        print("=== 生成回答节点 ===")
        max_tokens = state.get("max_tokens", 4096)
        answer = self.result_generator.generate(
            state["processed_query"], state["knowledge"], max_tokens=max_tokens
        )
        print("回答生成完成")
        return {
            "query": state["query"],
            "processed_query": state["processed_query"],
            "knowledge": state["knowledge"],
            "answer": answer,
            "max_tokens": max_tokens,
        }

    def process_query(self, query, max_tokens=4096):
        result = self.graph.invoke({
            "query": query,
            "max_tokens": max_tokens,
        })
        return result["answer"]
