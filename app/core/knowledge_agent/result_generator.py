from app.prompts.templates import RAG_TEMPLATE


class ResultGenerator:
    """根据检索知识构造 RAG 提示词，并调用 LLM 生成答案。"""

    def __init__(self, llm_service=None):
        """保存外部注入的 LLM 服务，便于复用当前模型配置。"""
        self.llm_service = llm_service

    def generate(self, query, knowledge, max_tokens=4096):
        """构造提示词、调用 LLM，并返回后处理后的回答文本。"""
        prompt = self._build_prompt(query, knowledge)
        answer = self.llm_service.generate(prompt, max_tokens=max_tokens)
        processed_answer = self._process_answer(answer)
        return processed_answer

    def _build_prompt(self, query, knowledge):
        """把用户查询和检索知识填入 RAG 模板，形成最终模型输入。"""
        knowledge_text = knowledge if knowledge else "无相关知识"

        prompt = RAG_TEMPLATE
        prompt = prompt.replace("{{query}}", query)
        prompt = prompt.replace("{{relevant_docs}}", knowledge_text)

        return prompt

    def _process_answer(self, answer):
        """预留答案后处理入口，目前保持模型原始输出不变。"""
        return answer
