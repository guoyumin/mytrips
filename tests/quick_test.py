#!/usr/bin/env python3
"""
快速测试脚本 - 验证基本功能
"""
import os
import sys
import json

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))

from lib.gmail_client import GmailClient
from lib.email_classifier import EmailClassifier

def quick_test():
    """快速测试核心功能"""
    print("🚀 快速测试开始...")
    
    # 配置
    project_root = os.path.dirname(os.path.dirname(__file__))
    credentials_path = os.path.join(project_root, 'config', 'credentials.json')
    token_path = os.path.join(project_root, 'config', 'token.json')
    gemini_config_path = os.path.join(project_root, 'config', 'gemini_config.json')
    
    # Test 1: Gmail 连接
    print("\n1️⃣ 测试 Gmail 连接...")
    try:
        gmail = GmailClient(credentials_path, token_path)
        # 获取最近 3 封邮件
        messages = gmail.search_emails_by_date(days_back=3)[:3]
        print(f"✅ 成功连接 Gmail，找到 {len(messages)} 封邮件")
        
        if messages:
            # 获取第一封邮件的详情
            headers = gmail.get_message_headers(messages[0]['id'])
            print(f"   示例邮件: {headers.get('subject', 'No subject')[:50]}...")
    except Exception as e:
        print(f"❌ Gmail 连接失败: {e}")
        return False
    
    # Test 2: Gemini 分类
    print("\n2️⃣ 测试 Gemini 分类...")
    try:
        # 加载 API key
        with open(gemini_config_path, 'r') as f:
            api_key = json.load(f).get('api_key')
        
        classifier = EmailClassifier(api_key)
        
        # 创建测试邮件
        test_emails = [
            {
                'email_id': 'test1',
                'subject': 'Your flight booking confirmation - AA123',
                'from': 'noreply@americanairlines.com'
            },
            {
                'email_id': 'test2',
                'subject': 'Weekly Newsletter - Travel Deals',
                'from': 'deals@travelcompany.com'
            },
            {
                'email_id': 'test3',
                'subject': 'Your Amazon order has shipped',
                'from': 'shipment@amazon.com'
            }
        ]
        
        # 分类
        results = classifier.classify_batch(test_emails)
        
        print("✅ 分类成功!")
        for email, result in zip(test_emails, results):
            travel = "🧳" if result.get('is_travel_related') else "📧"
            print(f"   {travel} [{result['classification']}] {email['subject']}")
            
    except Exception as e:
        print(f"❌ Gemini 分类失败: {e}")
        return False
    
    print("\n✅ 所有测试通过！")
    return True

if __name__ == "__main__":
    success = quick_test()
    sys.exit(0 if success else 1)