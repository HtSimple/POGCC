from openai import OpenAI

client = OpenAI(
    api_key = "8P30FGwcS4wpeEyk58Bb7244Fd8b42AfA2Bc2a61D7C32895",   # 替换为你的API密钥
    base_url = "https://llmapi.tongji.edu.cn/v1"
)
chat_completion = client.chat.completions.create(
    model="DeepSeek-R1",  # 替换为你的模型名称
    messages=[
        {
            "role": "user",
            "content": "地球的半径是多少?",
        }
    ]
)

print(chat_completion.choices[0].message.content)

'''
from openai import OpenAI

client = OpenAI(
    api_key = "your_api_key",   # 替换为你的API密钥
    base_url = "https://llmapi.tongji.edu.cn/v1"
)
# 设置 stream=True 以支持流式输出
chat_completion = client.chat.completions.create(
    model="DeepSeek-R1",  # 替换为你的模型名称
    messages=[
        {
            "role": "user",
            "content": "0110110110110中有几个1?",
        }
    ],
    stream=True
)

# 流式输出结果
for chunk in chat_completion:
    if chunk.choices[0].delta.content is not None:
        print(chunk.choices[0].delta.content, end="", flush=True)
'''