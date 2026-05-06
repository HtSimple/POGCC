from app.prompts.templates import OUTLINE_TEMPLATE

class OutlineMaker:
    
    def __init__(self, llm_service=None):
        self.llm_service = llm_service
    
    def generate_outline(self, topic, requirements=None, max_tokens=4096):
        """生成PPT大纲
        
        Args:
            topic (str): PPT主题
            requirements (str, optional): 额外需求
            
        Returns:
            dict: 生成的大纲结构
        """
        # 构建提示
        prompt = self._build_prompt(topic, requirements)
        
        # 调用LLM生成大纲
        outline_text = self.llm_service.generate(prompt, max_tokens=max_tokens)
        print(f"\n生成的大纲文本: {outline_text}")
        
        # 解析生成的大纲
        outline = self._parse_outline(outline_text)
        
        # 如果解析失败，返回默认大纲结构
        if len(outline["sections"]) == 0:
            print("解析失败，返回默认大纲结构")
            outline = {
                "title": f"{topic}",
                "sections": [
                    {
                        "title": "1. 概述",
                        "subsections": ["a. 背景介绍", "b. 研究意义"]
                    },
                    {
                        "title": "2. 主要内容",
                        "subsections": ["a. 核心概念", "b. 应用案例"]
                    },
                    {
                        "title": "3. 总结展望",
                        "subsections": ["a. 总结", "b. 未来发展"]
                    }
                ]
            }
        
        return outline
    
    def _build_prompt(self, topic, requirements):
        """构建大纲生成提示
        
        Args:
            topic (str): PPT主题
            requirements (str): 额外需求
            
        Returns:
            str: 构建好的提示
        """
        prompt = OUTLINE_TEMPLATE
        prompt = prompt.replace("{topic}", topic)
        
        if requirements:
            prompt = prompt.replace("{requirements}", f"额外需求：{requirements}")
        else:
            prompt = prompt.replace("{requirements}", "")
        
        return prompt
    
    def _parse_outline(self, outline_text):
        """解析生成的大纲
        
        Args:
            outline_text (str): LLM生成的大纲文本
            
        Returns:
            dict: 解析后的大纲结构
        """
        # 简单的大纲解析，实际项目中可能需要更复杂的解析逻辑
        # 这里假设LLM生成的是层级结构的大纲
        
        outline = {
            "title": "",
            "sections": []
        }
        
        # 提取标题
        lines = outline_text.strip().split('\n')
        if lines:
            outline["title"] = lines[0].strip()
            
            # 提取章节
            current_section = None
            for line in lines[1:]:
                line = line.strip()
                if not line:
                    continue
                
                # 检测一级标题
                if line.startswith('1. '):
                    if current_section:
                        outline["sections"].append(current_section)
                    current_section = {
                        "title": line[3:],
                        "subsections": []
                    }
                # 检测二级标题
                elif line.startswith('   a. '):
                    if current_section:
                        current_section["subsections"].append(line[5:])
        
        # 添加最后一个章节
        if current_section:
            outline["sections"].append(current_section)
        
        return outline