from app.prompts.templates import RAG_TEMPLATE


class ResultGenerator:

    def __init__(self, llm_service=None):
        self.llm_service = llm_service

    def generate(self, query, relevant_docs, max_tokens=4096):
        prompt = self._build_prompt(query, relevant_docs)
        answer = self.llm_service.generate(prompt, max_tokens=max_tokens)
        processed_answer = self._process_answer(answer)
        return processed_answer

    def _build_prompt(self, query, relevant_docs):
        docs_text = ""
        if relevant_docs:
            for i, doc in enumerate(relevant_docs[:3]):
                docs_text += f"{i+1}. {doc}\n"
        else:
            docs_text = "无相关文档"

        prompt = RAG_TEMPLATE
        prompt = prompt.replace("{{query}}", query)
        prompt = prompt.replace("{{relevant_docs}}", docs_text)

        return prompt

    def _process_answer(self, answer):
        return answer
