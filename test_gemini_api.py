#!/usr/bin/env python3
"""
测试 Gemini API 连接和配额状态
"""

import google.generativeai as genai
import json
import os
import traceback

def test_gemini_api():
    print("=== Gemini API 测试 ===\n")
    
    # 1. 加载配置
    config_path = 'config/gemini_config.json'
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
        api_key = config.get('api_key')
        model_name = config.get('model', 'gemini-2.5-pro')
        print(f"✓ 配置文件加载成功")
        print(f"  API Key: {api_key[:20]}..." if api_key else "  ❌ API Key 未找到")
        print(f"  模型: {model_name}")
    except Exception as e:
        print(f"❌ 配置文件加载失败: {e}")
        return

    # 2. 配置 Gemini
    try:
        genai.configure(api_key=api_key)
        print(f"✓ Gemini 配置成功")
    except Exception as e:
        print(f"❌ Gemini 配置失败: {e}")
        return

    # 3. 检查模型列表
    try:
        print("\n--- 可用模型列表 ---")
        for model in genai.list_models():
            if 'generateContent' in model.supported_generation_methods:
                print(f"  • {model.name}")
    except Exception as e:
        print(f"❌ 获取模型列表失败: {e}")
        print(f"详细错误: {traceback.format_exc()}")

    # 4. 测试简单调用
    try:
        print(f"\n--- 测试模型 {model_name} ---")
        model = genai.GenerativeModel(model_name)
        
        test_prompt = """请用中文回答: 什么是人工智能?"""
        
        print(f"发送测试提示: {test_prompt}")
        response = model.generate_content(test_prompt)
        
        print(f"✓ API 调用成功!")
        print(f"响应: {response.text[:200]}...")
        
    except Exception as e:
        print(f"❌ API 调用失败: {e}")
        print(f"详细错误: {traceback.format_exc()}")
        
        # 检查是否是配额问题
        error_str = str(e).lower()
        if 'quota' in error_str or 'rate limit' in error_str or 'exceeded' in error_str:
            print("\n🚨 这看起来像是配额限制问题!")
            print("免费版 Gemini API 限制:")
            print("  • 每分钟 60 次请求")
            print("  • 每天有总使用限制")
            print("  • 需要等待或升级到付费版本")

    # 5. 测试邮件分类调用
    try:
        print(f"\n--- 测试邮件分类 ---")
        
        test_emails = [
            {"email_id": "test1", "subject": "Flight confirmation - AA123", "from": "american@airlines.com"},
            {"email_id": "test2", "subject": "Newsletter - Special deals", "from": "deals@booking.com"}
        ]
        
        classification_prompt = """Classify these 2 emails as travel-related or not.

Categories:
- flight: Flight booking confirmations
- marketing: Travel company promotions  
- not_travel: Not travel-related

Return ONLY a JSON array:
[{"id": 1, "is_travel": true, "category": "flight"}, {"id": 2, "is_travel": false, "category": "marketing"}]

Emails to classify:
1. From: american@airlines.com | Subject: Flight confirmation - AA123
2. From: deals@booking.com | Subject: Newsletter - Special deals"""

        print("发送分类测试...")
        response = model.generate_content(classification_prompt)
        
        print(f"✓ 邮件分类调用成功!")
        print(f"响应: {response.text}")
        
        # 尝试解析JSON
        try:
            result = json.loads(response.text.strip())
            print(f"✓ JSON 解析成功: {result}")
        except:
            print(f"❌ JSON 解析失败，原始响应: {response.text}")
            
    except Exception as e:
        print(f"❌ 邮件分类测试失败: {e}")
        print(f"详细错误: {traceback.format_exc()}")

if __name__ == "__main__":
    test_gemini_api()