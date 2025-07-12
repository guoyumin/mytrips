#!/usr/bin/env python3
"""
完全重置所有数据库数据（通过API调用）
WARNING: 这将删除所有数据，请谨慎使用！

使用方法：
    python reset_all_data.py          # 需要确认
    python reset_all_data.py --force  # 跳过确认
"""
import logging
import requests
import sys

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# API基础URL
API_BASE_URL = "http://localhost:8000"


def reset_all_data():
    """通过API调用重置所有数据"""
    
    logger.info("=" * 60)
    logger.info("开始重置所有数据...")
    logger.info("WARNING: 这将删除所有数据！")
    logger.info("=" * 60)
    
    # 定义重置步骤
    reset_steps = [
        {
            'name': 'Trip Detection',
            'endpoint': '/api/trips/detection/reset',
            'description': '重置Trip检测数据'
        },
        {
            'name': 'Booking Extraction',
            'endpoint': '/api/content/reset-booking',
            'description': '重置Booking提取数据'
        },
        {
            'name': 'Content Extraction',
            'endpoint': '/api/content/reset',
            'description': '重置内容提取数据'
        },
        {
            'name': 'Email Classification',
            'endpoint': '/api/emails/reset-classification',
            'description': '重置邮件分类数据'
        },
        {
            'name': 'All Emails',
            'endpoint': '/api/emails/reset-all',
            'description': '删除所有邮件数据'
        }
    ]
    
    all_success = True
    results = []
    
    for step in reset_steps:
        logger.info(f"\n正在执行: {step['description']}...")
        
        try:
            # 发送POST请求
            response = requests.post(f"{API_BASE_URL}{step['endpoint']}")
            
            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    logger.info(f"✓ {step['name']}: {result.get('message', '成功')}")
                    results.append({
                        'step': step['name'],
                        'success': True,
                        'message': result.get('message', '成功'),
                        'details': result
                    })
                else:
                    logger.error(f"✗ {step['name']}: {result.get('message', '失败')}")
                    all_success = False
                    results.append({
                        'step': step['name'],
                        'success': False,
                        'message': result.get('message', '失败'),
                        'error': result.get('error')
                    })
            else:
                error_msg = f"API请求失败，状态码: {response.status_code}"
                logger.error(f"✗ {step['name']}: {error_msg}")
                all_success = False
                results.append({
                    'step': step['name'],
                    'success': False,
                    'message': error_msg,
                    'error': response.text
                })
                
        except requests.exceptions.ConnectionError:
            error_msg = "无法连接到API服务器，请确保服务器正在运行"
            logger.error(f"✗ {step['name']}: {error_msg}")
            all_success = False
            results.append({
                'step': step['name'],
                'success': False,
                'message': error_msg
            })
            # 如果无法连接服务器，停止执行
            break
            
        except Exception as e:
            error_msg = f"发生错误: {str(e)}"
            logger.error(f"✗ {step['name']}: {error_msg}")
            all_success = False
            results.append({
                'step': step['name'],
                'success': False,
                'message': error_msg
            })
    
    # 打印总结
    logger.info("\n" + "=" * 60)
    logger.info("重置总结:")
    logger.info("=" * 60)
    
    for result in results:
        status = "✓" if result['success'] else "✗"
        logger.info(f"{status} {result['step']}: {result['message']}")
        if result.get('details'):
            for key, value in result['details'].items():
                if key not in ['success', 'message']:
                    logger.info(f"    - {key}: {value}")
    
    if all_success:
        logger.info("\n✅ 所有数据已成功重置！")
        return True
    else:
        logger.warning("\n⚠️  部分重置操作失败，请检查日志！")
        return False


def confirm_reset():
    """确认是否要重置所有数据"""
    print("\n" + "=" * 60)
    print("⚠️  警告：此操作将删除数据库中的所有数据！")
    print("=" * 60)
    print("\n请确认您要执行此操作。")
    print("输入 'YES' 继续，其他任何输入将取消操作。")
    
    response = input("\n您的选择: ").strip()
    return response == "YES"


if __name__ == "__main__":
    # 检查是否有 --force 参数
    force_mode = "--force" in sys.argv
    
    if force_mode:
        logger.info("使用 --force 模式，跳过确认...")
        success = reset_all_data()
        if success:
            logger.info("\n数据重置完成！")
            sys.exit(0)
        else:
            logger.error("\n数据重置失败！")
            sys.exit(1)
    else:
        if confirm_reset():
            success = reset_all_data()
            if success:
                logger.info("\n数据重置完成！")
                sys.exit(0)
            else:
                logger.error("\n数据重置失败！")
                sys.exit(1)
        else:
            logger.info("\n操作已取消。")
            sys.exit(0)