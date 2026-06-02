from openai import OpenAI
from app.utils.config import Config


class QwenService:
    """阿里云百炼 Qwen 的 OpenAI 兼容接口适配器。"""

    def __init__(self, config=None):
        """读取 DashScope API Key，并初始化 OpenAI 兼容客户端。"""
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

    def generate(self, prompt, model="qwen3.6-plus", temperature=0.3, max_tokens=4096, response_format=None):
        """调用 Qwen Chat Completions，返回文本内容或带前缀的错误信息。"""
        try:
            kwargs = {}
            if response_format is not None:
                kwargs["response_format"] = response_format

            completion = self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": prompt}
                ],
                temperature=temperature,
                max_tokens=max_tokens,
                stream=False,
                **kwargs,
            )

            content = completion.choices[0].message.content
            return content

        except Exception as e:
            return f"[Qwen] 请求发生错误: {str(e)}"
