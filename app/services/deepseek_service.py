import requests
from app.utils.config import Config


class DeepSeekService:

    def __init__(self, config=None):
        if config is None:
            config = Config()
        self._config = config

        self.api_key = self._config.get('deepseek_api_key')
        if not self.api_key:
            raise ValueError("配置文件中未设置 deepseek_api_key")

    def generate(self, prompt, model="DeepSeek-R1", temperature=0.3, max_tokens=4096, response_format=None):
        url = "https://llmapi.tongji.edu.cn/v1/chat/completions"

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt}
            ],
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        if response_format is not None:
            payload["response_format"] = response_format

        try:
            response = requests.post(url, headers=headers, json=payload)

            if response.status_code == 200:
                result = response.json()
                message = result['choices'][0]['message']

                reasoning = message.get('reasoning', '') or ''
                content = message.get('content', '') or ''

                include_reasoning = bool(self._config.get('deepseek_include_reasoning', False))
                if include_reasoning and reasoning:
                    final_answer = f"【思考过程】\n{reasoning}\n\n【最终回答】\n{content}"
                else:
                    final_answer = content

                if not final_answer.strip():
                    finish_reason = result['choices'][0].get('finish_reason', '')
                    if finish_reason == 'length':
                        return "[DeepSeek] 回复被截断，请增加 max_tokens 后重试"
                    return "[DeepSeek] 模型未返回有效内容"

                return final_answer
            else:
                return f"[DeepSeek] API调用失败: {response.status_code} - {response.text}"

        except Exception as e:
            return f"[DeepSeek] 请求发生错误: {str(e)}"
