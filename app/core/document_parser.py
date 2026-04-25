import os
from docx import Document
import PyPDF2

class DocumentParser:
    """文档解析器
    
    负责解析Word和PDF文档
    """
    
    def parse(self, file_path):
        """解析文档
        
        Args:
            file_path (str): 文档文件路径
            
        Returns:
            str: 解析后的文本内容
        """
        # 获取文件扩展名
        ext = os.path.splitext(file_path)[1].lower()
        
        if ext in ['.docx', '.doc']:
            return self._parse_word(file_path)
        elif ext == '.pdf':
            return self._parse_pdf(file_path)
        else:
            raise ValueError(f"不支持的文件格式: {ext}")
    
    def _parse_word(self, file_path):
        """解析Word文档
        
        Args:
            file_path (str): Word文档路径
            
        Returns:
            str: 解析后的文本内容
        """
        try:
            doc = Document(file_path)
            text = []
            
            for paragraph in doc.paragraphs:
                if paragraph.text.strip():
                    text.append(paragraph.text)
            
            return '\n'.join(text)
        except Exception as e:
            raise Exception(f"解析Word文档失败: {str(e)}")
    
    def _parse_pdf(self, file_path):
        """解析PDF文档
        
        Args:
            file_path (str): PDF文档路径
            
        Returns:
            str: 解析后的文本内容
        """
        try:
            with open(file_path, 'rb') as f:
                reader = PyPDF2.PdfReader(f)
                text = []
                
                for page_num in range(len(reader.pages)):
                    page = reader.pages[page_num]
                    page_text = page.extract_text()
                    if page_text:
                        text.append(page_text)
                
                return '\n'.join(text)
        except Exception as e:
            raise Exception(f"解析PDF文档失败: {str(e)}")