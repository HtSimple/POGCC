import os
import json
from dotenv import load_dotenv

class Config:
    """配置管理
    
    负责读取和管理配置
    """
    
    def __init__(self, config_file="config.json"):
        """初始化配置
        
        Args:
            config_file (str): 配置文件路径
        """
        # 加载环境变量
        load_dotenv()
        
        # 从配置文件读取配置
        self.config_file = config_file
        self.config = {}
        self._load_config()
    
    def _load_config(self):
        """加载配置
        """
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    self.config = json.load(f)
        except Exception as e:
            print(f"加载配置文件失败: {e}")
    
    def get(self, key, default=None):
        """获取配置值
        
        Args:
            key (str): 配置键
            default: 默认值
            
        Returns:
            配置值
        """
        # 优先从环境变量获取
        if key in os.environ:
            return os.environ[key]
        
        # 从配置文件获取
        return self.config.get(key, default)
    
    def set(self, key, value):
        """设置配置值
        
        Args:
            key (str): 配置键
            value: 配置值
        """
        self.config[key] = value
        self._save_config()
    
    def _save_config(self):
        """保存配置
        """
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"保存配置文件失败: {e}")

# 创建全局配置实例
config = Config()