"""
邮件分类库
使用 AI 对邮件进行分类
"""
import json
import logging
from typing import List, Dict, Optional
from backend.lib.ai.ai_provider_interface import AIProviderInterface

logger = logging.getLogger(__name__)


class EmailClassifier:
    """邮件分类器 - 使用依赖注入的AI Provider"""
    
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
    
    def __init__(self, ai_provider: AIProviderInterface):
        """
        初始化分类器
        
        Args:
            ai_provider: AI提供商实例
        """
        self.ai_provider = ai_provider
        logger.info(f"EmailClassifier initialized with {ai_provider.get_model_info()['model_name']}")
    
    def classify_batch(self, emails: List[Dict[str, str]]) -> Dict[str, any]:
        """
        批量分类邮件
        
        Args:
            emails: 邮件列表，每个邮件包含 email_id, subject, from 等字段
            
        Returns:
            包含分类结果和成本信息的字典
        """
        if not emails:
            return {'classifications': [], 'cost_info': None}
        
        # 创建提示
        prompt = self._create_classification_prompt(emails)
        
        try:
            # Log AI model being used
            model_info = self.ai_provider.get_model_info()
            logger.info(f"Calling AI model for email classification: {model_info.get('provider', 'Unknown')} - {model_info['model_name']}")
            
            # 调用 AI Provider
            response = self.ai_provider.generate_content(prompt)
            response_text = response['content']
            
            # 解析响应
            classifications = self._parse_response(response_text, emails)
            
            # 提取成本信息
            cost_info = {
                'input_tokens': response.get('input_tokens', 0),
                'output_tokens': response.get('output_tokens', 0),
                'total_tokens': response.get('total_tokens', 0),
                'estimated_cost_usd': response.get('estimated_cost_usd', 0.0)
            }
            
            return {
                'classifications': classifications,
                'cost_info': cost_info
            }
            
        except Exception as e:
            logger.error(f"分类错误: {e}")
            # 返回默认分类
            return {
                'classifications': [self._create_failed_classification(email) for email in emails],
                'cost_info': None
            }
    
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

CRITICAL REQUIREMENTS:
1. Return ONLY a JSON array - no other text, no explanations, no thinking
2. Do NOT use <think> tags or any other XML/HTML tags
3. Do NOT include any text before or after the JSON
4. Do NOT explain your reasoning or thinking process
5. Start your response with [ and end with ]

Return EXACTLY {len(emails)} objects in this format:
[{{"id": 1, "category": "flight"}}, {{"id": 2, "category": "not_travel"}}, ...]

Emails to classify:
{emails_text}

REMEMBER: Your response must start with [ and contain only valid JSON."""
        
        return prompt
    
    def _parse_response(self, response_text: str, emails: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """解析 AI 响应"""
        try:
            # 清理响应文本
            response_text = response_text.strip()
            
            # 移除 <think> 标签（如果存在）
            if '<think>' in response_text and '</think>' in response_text:
                think_start = response_text.find('<think>')
                think_end = response_text.find('</think>') + len('</think>')
                if think_end > think_start:
                    response_text = response_text[:think_start] + response_text[think_end:]
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
            logger.error(f"解析响应失败: {e}")
            logger.error(f"原始响应: {response_text[:200]}...")
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
    
