"""
邮件分类库
使用 AI 对邮件进行分类
"""
import json
from typing import List, Dict, Optional, Tuple
import google.generativeai as genai

class EmailClassifier:
    """邮件分类器"""
    
    # 旅行相关分类
    TRAVEL_CATEGORIES = {
        'flight', 'hotel', 'car_rental', 'train', 'cruise',
        'tour', 'travel_insurance', 'flight_change',
        'hotel_change', 'other_travel'
    }
    
    # 非旅行分类
    NON_TRAVEL_CATEGORIES = {
        'marketing', 'not_travel', 'classification_failed'
    }
    
    def __init__(self, config_path: str = None, api_key: str = None, model_name: str = 'gemini-2.5-pro'):
        """
        初始化分类器
        
        Args:
            config_path: Gemini 配置文件路径
            api_key: Gemini API 密钥（可选，如果提供则忽略config_path）
            model_name: 使用的模型名称
        """
        if api_key:
            # 直接使用提供的API密钥
            genai.configure(api_key=api_key)
        elif config_path:
            # 从配置文件读取
            with open(config_path, 'r') as f:
                config = json.load(f)
            genai.configure(api_key=config['api_key'])
            if 'model' in config:
                model_name = config['model']
        else:
            raise ValueError("必须提供 api_key 或 config_path")
        
        self.model = genai.GenerativeModel(model_name)
    
    def classify_batch(self, emails: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """
        批量分类邮件
        
        Args:
            emails: 邮件列表，每个邮件包含 email_id, subject, from 等字段
            
        Returns:
            分类结果列表
        """
        if not emails:
            return []
        
        # 创建提示
        prompt = self._create_classification_prompt(emails)
        
        try:
            # 调用 AI 模型
            response = self.model.generate_content(prompt)
            
            # 解析响应
            classifications = self._parse_response(response.text, emails)
            
            return classifications
            
        except Exception as e:
            print(f"分类错误: {e}")
            # 返回默认分类
            return [self._create_failed_classification(email) for email in emails]
    
    def _create_classification_prompt(self, emails: List[Dict[str, str]]) -> str:
        """创建分类提示"""
        # 构建邮件列表
        email_list = []
        for i, email in enumerate(emails):
            subject = email.get('subject', '')[:100]  # 限制长度
            sender = email.get('from', '')[:50]
            email_list.append(f"{i+1}. From: {sender} | Subject: {subject}")
        
        emails_text = "\n".join(email_list)
        
        prompt = f"""Classify these {len(emails)} emails as travel-related or not.

IMPORTANT: Only classify emails that contain ACTUAL ITINERARY INFORMATION (booking confirmations, tickets, reservations with specific dates/times/locations) as travel categories. Marketing emails from travel companies should be classified as 'marketing'.

Categories:
- flight: Flight booking confirmations, boarding passes, e-tickets (with flight numbers/times)
- hotel: Hotel reservation confirmations (with check-in/out dates)
- car_rental: Car rental confirmations (with pickup dates/locations)
- train: Train/rail ticket confirmations
- cruise: Cruise booking confirmations
- tour: Tour/activity booking confirmations (with specific dates)
- travel_insurance: Travel insurance policy confirmations
- flight_change: Flight changes, delays, cancellations (for existing bookings)
- hotel_change: Hotel changes, cancellations (for existing bookings)
- other_travel: Other travel confirmations (visas, parking reservations, etc.)
- marketing: Travel company promotions, newsletters, deals (NO specific booking info)
- not_travel: Not travel-related at all

Return ONLY a JSON array with {len(emails)} objects in this exact format:
[{{"id": 1, "category": "flight"}}, {{"id": 2, "category": "not_travel"}}, ...]

Emails to classify:
{emails_text}"""
        
        return prompt
    
    def _parse_response(self, response_text: str, emails: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """解析 AI 响应"""
        try:
            # 清理响应文本
            response_text = response_text.strip()
            
            # 移除 Markdown 代码块标记
            if '```json' in response_text:
                start = response_text.find('```json') + 7
                end = response_text.rfind('```')
                if end > start:
                    response_text = response_text[start:end].strip()
            elif '```' in response_text:
                start = response_text.find('```') + 3
                end = response_text.rfind('```')
                if end > start:
                    response_text = response_text[start:end].strip()
            
            # 解析 JSON
            classifications = json.loads(response_text)
            
            # 构建结果
            results = []
            for i, classification in enumerate(classifications):
                if i < len(emails):
                    email = emails[i]
                    category = classification.get('category', 'not_travel')
                    
                    result = {
                        'email_id': email.get('email_id', ''),
                        'classification': category,
                        'is_travel_related': category in self.TRAVEL_CATEGORIES
                    }
                    results.append(result)
            
            # 补充遗漏的结果
            while len(results) < len(emails):
                results.append(self._create_failed_classification(emails[len(results)]))
            
            return results
            
        except Exception as e:
            print(f"解析响应失败: {e}")
            print(f"原始响应: {response_text[:200]}...")
            return [self._create_failed_classification(email) for email in emails]
    
    def _create_failed_classification(self, email: Dict[str, str]) -> Dict[str, str]:
        """创建失败的分类结果"""
        return {
            'email_id': email.get('email_id', ''),
            'classification': 'classification_failed',
            'is_travel_related': False
        }
    
    def is_travel_category(self, category: str) -> bool:
        """判断是否为旅行相关分类"""
        return category in self.TRAVEL_CATEGORIES
    
    def estimate_cost(self, num_emails: int) -> Dict[str, float]:
        """
        估算分类成本
        
        Args:
            num_emails: 邮件数量
            
        Returns:
            成本估算信息
        """
        # 粗略估算：每封邮件约 50 个 token（输入 + 输出）
        estimated_tokens = num_emails * 50
        
        # Gemini Pro 定价（近似值）
        input_cost_per_1k = 0.000125
        output_cost_per_1k = 0.000375
        
        estimated_cost = (estimated_tokens * input_cost_per_1k / 1000) + \
                        (num_emails * 20 * output_cost_per_1k / 1000)
        
        return {
            'estimated_tokens': estimated_tokens,
            'estimated_cost_usd': round(estimated_cost, 6)
        }