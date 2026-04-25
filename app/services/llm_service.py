import requests
import json
import os

class LLMService:
    """LLM服务
    
    负责与大语言模型API交互
    """
    
    def __init__(self, config_file="config.json"):
        """初始化LLM服务
        
        Args:
            config_file (str): 配置文件路径
        """
        # 从配置文件读取API密钥
        if not os.path.exists(config_file):
            raise FileNotFoundError(f"配置文件 {config_file} 不存在")
        
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        self.api_key = config.get('deepseek_api_key')
        if not self.api_key:
            raise ValueError("配置文件中未设置 deepseek_api_key")
    
    def generate(self, prompt, model="DeepSeek-R1", temperature=0.7, max_tokens=1000):
        """调用LLM生成回答
        
        Args:
            prompt (str): 提示文本
            
        Returns:
            str: 生成的回答
        """
        # API 端点
        url = "https://llmapi.tongji.edu.cn/v1/chat/completions"
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        # 参考示例：移除了 stream: True，新增了参数配置
        payload = {
            "model": "DeepSeek-R1", # R1 模型
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt}
            ],
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        
        try:
            # 发送请求
            response = requests.post(url, headers=headers, json=payload)
            
            # 参考示例：处理响应状态码
            if response.status_code == 200:
                result = response.json()
                message = result['choices'][0]['message']
                
                # DeepSeek-R1 (reasoner) 返回体中包含 'reasoning_content' (思考过程) 和 'content' (最终回答)
                reasoning = message.get('reasoning_content', '')
                content = message.get('content', '')
                
                # 将思考过程和最终回答格式化拼接 (如果您不需要显示思考过程，直接 return content 即可)
                final_answer = ""
                if reasoning:
                    final_answer += f"【思考过程】\n{reasoning}\n\n【最终回答】\n"
                final_answer += content
                
                return final_answer
            else:
                # 不直接抛出异常中断整个程序，而是作为字符串返回错误信息，方便上层处理
                return f"API调用失败: {response.status_code} - {response.text}"
                
        except Exception as e:
            return f"请求发生错误: {str(e)}"