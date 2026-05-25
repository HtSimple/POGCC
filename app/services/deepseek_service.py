from openai import OpenAI
from app.utils.config import Config


class DeepSeekService:

    def __init__(self, config=None):
        if config is None:
            config = Config()
        self._config = config

        self.api_key = self._config.get('deepseek_api_key')
        if not self.api_key:
            raise ValueError("配置文件中未设置 deepseek_api_key")

        self.client = OpenAI(
            api_key=self.api_key,
            base_url="https://api.deepseek.com"
        )

    def generate(self, prompt, model="deepseek-v4-pro", temperature=0.3, max_tokens=4096, response_format=None):
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
                extra_body={"thinking": {"type": "disabled"}},
                **kwargs,
            )

            content = completion.choices[0].message.content or ''
            if not content.strip():
                finish_reason = completion.choices[0].finish_reason or ''
                if finish_reason == 'length':
                    return "[DeepSeek] 回复被截断，请增加 max_tokens 后重试"
                return "[DeepSeek] 模型未返回有效内容"

            return content

        except Exception as e:
            return f"[DeepSeek] 请求发生错误: {str(e)}"
