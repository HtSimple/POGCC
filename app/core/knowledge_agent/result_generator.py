from app.prompts.templates import RAG_TEMPLATE


class ResultGenerator:

    def __init__(self, llm_service=None):
        self.llm_service = llm_service

    def generate(self, query, knowledge, max_tokens=4096):
        prompt = self._build_prompt(query, knowledge)
        answer = self.llm_service.generate(prompt, max_tokens=max_tokens)
        processed_answer = self._process_answer(answer)
        return processed_answer

    def _build_prompt(self, query, knowledge):
        knowledge_text = knowledge if knowledge else "无相关知识"

        prompt = RAG_TEMPLATE
        prompt = prompt.replace("{{query}}", query)
        prompt = prompt.replace("{{relevant_docs}}", knowledge_text)

        return prompt

    def _process_answer(self, answer):
        return answer
