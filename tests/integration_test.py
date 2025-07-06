#!/usr/bin/env python3
"""
集成测试 - 测试完整的邮件获取和分类流程
"""
import os
import sys
import json
import csv
from datetime import datetime

# 添加项目路径
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))

from lib.gmail_client import GmailClient
from lib.email_cache_db import EmailCacheDB
from lib.email_classifier import EmailClassifier

def run_integration_test():
    """运行集成测试"""
    print("=" * 60)
    print("MyTrips 集成测试")
    print("=" * 60)
    
    # 配置路径
    project_root = os.path.dirname(os.path.dirname(__file__))
    credentials_path = os.path.join(project_root, 'config', 'credentials.json')
    token_path = os.path.join(project_root, 'config', 'token.json')
    gemini_config_path = os.path.join(project_root, 'config', 'gemini_config.json')
    
    # 测试输出目录
    test_output_dir = os.path.join(project_root, 'tests', 'test_output')
    os.makedirs(test_output_dir, exist_ok=True)
    
    # 测试文件路径
    test_timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    test_emails_file = os.path.join(test_output_dir, f'test_emails_{test_timestamp}.csv')
    test_results_file = os.path.join(test_output_dir, f'test_results_{test_timestamp}.json')
    
    # Step 1: 初始化 Gmail 客户端
    print("\n1. 初始化 Gmail 客户端...")
    try:
        gmail_client = GmailClient(credentials_path, token_path)
        print("✅ Gmail 客户端初始化成功")
    except Exception as e:
        print(f"❌ Gmail 客户端初始化失败: {e}")
        return False
    
    # Step 2: 获取最近的邮件（小批量）
    print("\n2. 获取最近 20 封邮件...")
    try:
        # 获取最近 7 天的邮件，最多 20 封
        messages = gmail_client.search_emails_by_date(days_back=7)[:20]
        print(f"✅ 找到 {len(messages)} 封邮件")
        
        if not messages:
            print("⚠️  没有找到邮件，尝试扩大搜索范围...")
            messages = gmail_client.search_emails_by_date(days_back=30)[:20]
            print(f"✅ 找到 {len(messages)} 封邮件")
        
        # 获取邮件详情
        email_details = []
        for i, msg in enumerate(messages):
            print(f"   获取邮件 {i+1}/{len(messages)}...", end='\r')
            headers = gmail_client.get_message_headers(msg['id'])
            headers['email_id'] = msg['id']
            email_details.append(headers)
        
        print(f"\n✅ 成功获取 {len(email_details)} 封邮件的详情")
        
        # 保存邮件到 CSV
        with open(test_emails_file, 'w', newline='', encoding='utf-8') as f:
            fieldnames = ['email_id', 'subject', 'from', 'date']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for email in email_details:
                writer.writerow({
                    'email_id': email.get('email_id', ''),
                    'subject': email.get('subject', ''),
                    'from': email.get('from', ''),
                    'date': email.get('date', '')
                })
        
        print(f"📄 邮件保存到: {test_emails_file}")
        
    except Exception as e:
        print(f"❌ 获取邮件失败: {e}")
        return False
    
    # Step 3: 初始化分类器
    print("\n3. 初始化 Gemini 分类器...")
    try:
        # 加载 Gemini 配置
        with open(gemini_config_path, 'r') as f:
            gemini_config = json.load(f)
        
        api_key = gemini_config.get('api_key')
        if not api_key:
            raise Exception("Gemini API key not found")
        
        classifier = EmailClassifier(api_key)
        print("✅ Gemini 分类器初始化成功")
        
    except Exception as e:
        print(f"❌ 分类器初始化失败: {e}")
        return False
    
    # Step 4: 对邮件进行分类
    print("\n4. 使用 AI 对邮件进行分类...")
    try:
        # 估算成本
        cost_estimate = classifier.estimate_cost(len(email_details))
        print(f"💰 预估成本: ${cost_estimate['estimated_cost_usd']:.6f}")
        
        # 执行分类
        print("🤖 正在分类...")
        classifications = classifier.classify_batch(email_details)
        
        print(f"✅ 分类完成，处理了 {len(classifications)} 封邮件")
        
        # 统计分类结果
        category_counts = {}
        travel_count = 0
        
        for result in classifications:
            category = result['classification']
            category_counts[category] = category_counts.get(category, 0) + 1
            if result.get('is_travel_related', False):
                travel_count += 1
        
        print(f"\n📊 分类统计:")
        print(f"   - 旅行相关: {travel_count} 封")
        print(f"   - 非旅行相关: {len(classifications) - travel_count} 封")
        print(f"\n   分类详情:")
        for category, count in sorted(category_counts.items()):
            print(f"   - {category}: {count} 封")
        
        # 保存结果
        test_results = {
            'timestamp': datetime.now().isoformat(),
            'total_emails': len(email_details),
            'total_classified': len(classifications),
            'travel_related': travel_count,
            'category_counts': category_counts,
            'classifications': []
        }
        
        # 合并邮件信息和分类结果
        for email, classification in zip(email_details, classifications):
            test_results['classifications'].append({
                'email_id': email.get('email_id', ''),
                'subject': email.get('subject', ''),
                'from': email.get('from', ''),
                'classification': classification.get('classification', ''),
                'is_travel_related': classification.get('is_travel_related', False)
            })
        
        # 保存 JSON 结果
        with open(test_results_file, 'w', encoding='utf-8') as f:
            json.dump(test_results, f, ensure_ascii=False, indent=2)
        
        print(f"\n📄 测试结果保存到: {test_results_file}")
        
        # 打印一些示例
        print("\n📧 分类示例:")
        travel_examples = [r for r in test_results['classifications'] if r['is_travel_related']][:3]
        non_travel_examples = [r for r in test_results['classifications'] if not r['is_travel_related']][:3]
        
        if travel_examples:
            print("\n   旅行相关邮件:")
            for ex in travel_examples:
                print(f"   - [{ex['classification']}] {ex['subject'][:60]}...")
        
        if non_travel_examples:
            print("\n   非旅行相关邮件:")
            for ex in non_travel_examples:
                print(f"   - [{ex['classification']}] {ex['subject'][:60]}...")
        
    except Exception as e:
        print(f"❌ 分类失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print("\n" + "=" * 60)
    print("✅ 集成测试完成！")
    print("=" * 60)
    
    return True

if __name__ == "__main__":
    success = run_integration_test()
    sys.exit(0 if success else 1)