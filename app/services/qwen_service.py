from openai import OpenAI
from app.utils.config import Config


class QwenService:

    def __init__(self, config=None):
        if config is None:
            config = Config()
        self._config = config

        self.api_key = self._config.get('dashscope_api_key')
        if not self.api_key:
            raise ValueError("配置文件中未设置 dashscope_api_key")

        self.client = OpenAI(
            api_key=self.api_key,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
        )

    def generate(self, prompt, model="qwen3.6-plus", temperature=0.3, max_tokens=4096):
        try:
            completion = self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": prompt}
                ],
                temperature=temperature,
                max_tokens=max_tokens,
                stream=False
            )

            content = completion.choices[0].message.content
            return content

        except Exception as e:
            return f"[Qwen] 请求发生错误: {str(e)}"
