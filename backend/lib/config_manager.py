"""
配置管理模块
统一管理应用程序的所有配置
"""
import json
import os
from typing import Dict, Any

class ConfigManager:
    """配置管理器"""
    
    def __init__(self, config_path: str = None):
        """
        初始化配置管理器
        
        Args:
            config_path: 配置文件路径
        """
        if config_path is None:
            # 默认配置文件路径
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            config_path = os.path.join(project_root, 'config', 'app_config.json')
        
        self.config_path = config_path
        self.project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        self._config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """加载配置文件"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            raise Exception(f"配置文件不存在: {self.config_path}")
        except json.JSONDecodeError as e:
            raise Exception(f"配置文件格式错误: {e}")
    
    def get_absolute_path(self, relative_path: str) -> str:
        """
        获取绝对路径
        
        Args:
            relative_path: 相对于项目根目录的路径
            
        Returns:
            绝对路径
        """
        return os.path.join(self.project_root, relative_path)
    
    def get_cache_file_path(self, cache_type: str = None) -> str:
        """
        获取缓存文件路径
        
        Args:
            cache_type: 缓存类型 ('email_cache', 'email_cache_test', 'email_classification_test')
                       如果为None，则根据use_test_cache设置自动选择
            
        Returns:
            缓存文件的绝对路径
        """
        if cache_type is None:
            # 根据配置自动选择
            use_test = self._config.get('settings', {}).get('use_test_cache', False)
            cache_type = 'email_cache_test' if use_test else 'email_cache'
        
        relative_path = self._config['cache_files'][cache_type]
        return self.get_absolute_path(relative_path)
    
    def get_classification_test_file_path(self) -> str:
        """获取分类测试文件路径"""
        relative_path = self._config['cache_files']['email_classification_test']
        return self.get_absolute_path(relative_path)
    
    def get_database_path(self) -> str:
        """获取数据库文件路径"""
        relative_path = self._config['database']['sqlite_path']
        return self.get_absolute_path(relative_path)
    
    def get_gmail_credentials_path(self) -> str:
        """获取Gmail凭证文件路径"""
        relative_path = self._config['gmail']['credentials_path']
        return self.get_absolute_path(relative_path)
    
    def get_gmail_token_path(self) -> str:
        """获取Gmail token文件路径"""
        relative_path = self._config['gmail']['token_path']
        return self.get_absolute_path(relative_path)
    
    def get_gemini_config_path(self) -> str:
        """获取Gemini配置文件路径"""
        relative_path = self._config['gemini']['config_path']
        return self.get_absolute_path(relative_path)
    
    def get_batch_size(self) -> int:
        """获取批处理大小"""
        return self._config.get('settings', {}).get('batch_size', 20)
    
    def get_save_interval(self) -> int:
        """获取保存间隔"""
        return self._config.get('settings', {}).get('save_interval', 10)
    
    def is_using_test_cache(self) -> bool:
        """是否使用测试缓存"""
        return self._config.get('settings', {}).get('use_test_cache', False)
    
    def get_log_level(self) -> str:
        """获取日志级别"""
        return self._config.get('settings', {}).get('log_level', 'INFO')
    
    def set_use_test_cache(self, use_test: bool):
        """设置是否使用测试缓存"""
        if 'settings' not in self._config:
            self._config['settings'] = {}
        self._config['settings']['use_test_cache'] = use_test
        self._save_config()
    
    def set_log_level(self, log_level: str):
        """设置日志级别"""
        if 'settings' not in self._config:
            self._config['settings'] = {}
        self._config['settings']['log_level'] = log_level.upper()
        self._save_config()
    
    def _save_config(self):
        """保存配置到文件"""
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(self._config, f, indent=2, ensure_ascii=False)
    
    def get_config(self) -> Dict[str, Any]:
        """获取完整配置"""
        return self._config.copy()

# 全局配置管理器实例
config_manager = ConfigManager()