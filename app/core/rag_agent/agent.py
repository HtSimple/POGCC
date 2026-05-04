from langgraph.graph import StateGraph, END
from .query_processor import QueryProcessor
from .document_retriever import DocumentRetriever
from .result_generator import ResultGenerator

class RAGAgent:
    def __init__(self, document_parser=None, vector_db=None, llm_service=None):
        self.document_parser = document_parser
        self.vector_db = vector_db
        self.query_processor = QueryProcessor()
        self.document_retriever = DocumentRetriever(vector_db)
        self.result_generator = ResultGenerator(llm_service=llm_service)
        self.graph = self._build_graph()

    def _build_graph(self):
        graph = StateGraph(dict)

        graph.add_node("process_query", self._process_query_node)
        graph.add_node("retrieve_documents", self._retrieve_documents_node)
        graph.add_node("generate_answer", self._generate_answer_node)

        graph.add_edge("process_query", "retrieve_documents")
        graph.add_edge("retrieve_documents", "generate_answer")
        graph.add_edge("generate_answer", END)

        graph.set_entry_point("process_query")

        return graph.compile()

    def _process_query_node(self, state):
        print("=== 处理查询节点运行 ===")
        processed_query = self.query_processor.process(state["query"])
        print(f"原始查询: {state['query']}")
        print(f"处理后查询: {processed_query}")
        return {
            "query": state["query"],
            "processed_query": processed_query,
            "relevant_docs": state.get("relevant_docs"),
            "answer": state.get("answer"),
            "max_tokens": state.get("max_tokens", 4096),
        }

    def _retrieve_documents_node(self, state):
        print("=== 检索文档节点运行 ===")
        relevant_docs = self.document_retriever.retrieve(state["processed_query"])
        print(f"检索到的文档数量: {len(relevant_docs)}")
        for i, doc in enumerate(relevant_docs):
            print(f"文档 {i+1}: {doc[:100]}...")
        return {
            "query": state["query"],
            "processed_query": state["processed_query"],
            "relevant_docs": relevant_docs,
            "answer": state.get("answer"),
            "max_tokens": state.get("max_tokens", 4096),
        }

    def _generate_answer_node(self, state):
        print("=== 生成回答节点运行 ===")
        max_tokens = state.get("max_tokens", 4096)
        answer = self.result_generator.generate(
            state["processed_query"], state["relevant_docs"], max_tokens=max_tokens
        )
        print("回答生成完成")
        return {
            "query": state["query"],
            "processed_query": state["processed_query"],
            "relevant_docs": state["relevant_docs"],
            "answer": answer,
            "max_tokens": max_tokens,
        }

    def process_query(self, query, max_tokens=4096):
        result = self.graph.invoke({
            "query": query,
            "max_tokens": max_tokens,
        })
        return result["answer"]
