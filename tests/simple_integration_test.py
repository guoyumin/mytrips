#!/usr/bin/env python3
"""
简单集成测试 - 使用现有服务进行测试
"""
import os
import sys
import json
import csv
from datetime import datetime

# 添加项目路径
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))

from lib.gmail_client import GmailClient
from lib.email_classifier import EmailClassifier

def simple_integration_test():
    """运行简单的集成测试"""
    print("=" * 60)
    print("MyTrips 简单集成测试")
    print("=" * 60)
    
    # 测试输出目录
    test_output_dir = os.path.join(os.path.dirname(__file__), 'test_output')
    os.makedirs(test_output_dir, exist_ok=True)
    
    # 测试文件
    test_timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    test_results_file = os.path.join(test_output_dir, f'simple_test_{test_timestamp}.json')
    
    # Step 1: 测试 Gmail 客户端
    print("\n1. 测试 Gmail 客户端...")
    try:
        # 初始化Gmail客户端
        project_root = os.path.dirname(os.path.dirname(__file__))
        credentials_path = os.path.join(project_root, 'config', 'credentials.json')
        token_path = os.path.join(project_root, 'config', 'token.json')
        
        gmail_client = GmailClient(credentials_path, token_path)
        
        # 搜索最近1天的邮件
        messages = gmail_client.search_emails_by_date(1)
        
        # 获取邮件详情
        emails = []
        for msg in messages[:5]:  # 只取前5封
            headers = gmail_client.get_message_headers(msg['id'])
            headers['email_id'] = msg['id']
            emails.append(headers)
        
        print(f"✅ 成功获取 {len(emails)} 封邮件")
        
        # 显示几个例子
        print("\n   邮件示例:")
        for i, email in enumerate(emails[:3]):
            subject = email.get('subject', 'No subject')[:50]
            print(f"   {i+1}. {subject}...")
            
    except Exception as e:
        print(f"❌ Gmail 客户端测试失败: {e}")
        return False
    
    # Step 2: 测试 Gemini 分类
    print("\n2. 测试 Gemini 分类...")
    try:
        # 初始化分类器
        gemini_config_path = os.path.join(project_root, 'config', 'gemini_config.json')
        email_classifier = EmailClassifier(gemini_config_path)
        
        # 使用前面获取的邮件进行分类
        test_emails = emails[:5]  # 只测试前5封
        
        print(f"   对 {len(test_emails)} 封邮件进行分类...")
        results = email_classifier.classify_batch(test_emails)
        
        # 显示分类结果
        print("\n   分类结果:")
        for email, result in zip(test_emails, results):
            classification = result.get('classification', 'unknown')
            is_travel = "🧳" if result.get('is_travel_related', False) else "📧"
            subject = email.get('subject', '')[:40]
            print(f"   {is_travel} [{classification}] {subject}...")
        
        # 保存结果
        test_data = {
            'timestamp': datetime.now().isoformat(),
            'emails_tested': len(test_emails),
            'results': []
        }
        
        for email, result in zip(test_emails, results):
            test_data['results'].append({
                'email_id': email.get('email_id', ''),
                'subject': email.get('subject', ''),
                'from': email.get('from', ''),
                'classification': result.get('classification', ''),
                'is_travel_related': result.get('is_travel_related', False)
            })
        
        # 统计
        travel_count = sum(1 for r in test_data['results'] if r['is_travel_related'])
        test_data['summary'] = {
            'total': len(test_emails),
            'travel_related': travel_count,
            'not_travel_related': len(test_emails) - travel_count
        }
        
        # 保存到文件
        with open(test_results_file, 'w', encoding='utf-8') as f:
            json.dump(test_data, f, ensure_ascii=False, indent=2)
        
        print(f"\n✅ 测试结果保存到: {test_results_file}")
        print(f"   - 旅行相关: {travel_count}")
        print(f"   - 非旅行相关: {len(test_emails) - travel_count}")
        
    except Exception as e:
        print(f"❌ Gemini 分类测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print("\n" + "=" * 60)
    print("✅ 集成测试完成！")
    print("=" * 60)
    
    return True

if __name__ == "__main__":
    success = simple_integration_test()
    sys.exit(0 if success else 1)