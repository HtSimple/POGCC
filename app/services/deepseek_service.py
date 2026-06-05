from openai import OpenAI

from app.utils.config import Config


class DeepSeekService:
    """OpenAI-compatible DeepSeek API adapter."""

    def __init__(self, config=None):
        self._config = config or Config()
        self.api_key = self._config.get("deepseek_api_key")
        if not self.api_key:
            raise ValueError("deepseek_api_key is not configured")
        self.client = OpenAI(api_key=self.api_key, base_url="https://api.deepseek.com")

    def generate_with_usage(
        self,
        prompt,
        model="deepseek-v4-pro",
        temperature=0.3,
        max_tokens=4096,
        response_format=None,
    ):
        try:
            kwargs = {}
            if response_format is not None:
                kwargs["response_format"] = response_format
            completion = self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": prompt},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
                stream=False,
                extra_body={"thinking": {"type": "disabled"}},
                **kwargs,
            )
            content = completion.choices[0].message.content or ""
            if not content.strip():
                reason = completion.choices[0].finish_reason or ""
                message = (
                    "[DeepSeek] Response was truncated; increase max_tokens and retry"
                    if reason == "length"
                    else "[DeepSeek] Model returned no content"
                )
                return message, None
            usage = completion.usage
            return content, {
                "input_tokens": usage.prompt_tokens,
                "output_tokens": usage.completion_tokens,
                "total_tokens": usage.total_tokens,
                "cache_hit_tokens": getattr(usage, "prompt_cache_hit_tokens", 0) or 0,
                "cache_miss_tokens": getattr(
                    usage, "prompt_cache_miss_tokens", usage.prompt_tokens
                )
                or 0,
            }
        except Exception as exc:
            return f"[DeepSeek] Request failed: {exc}", None

    def generate(
        self,
        prompt,
        model="deepseek-v4-pro",
        temperature=0.3,
        max_tokens=4096,
        response_format=None,
    ):
        content, _ = self.generate_with_usage(
            prompt, model, temperature, max_tokens, response_format
        )
        return content
