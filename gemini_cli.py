#!/usr/bin/env python3
"""
Gemini 网页版剧本生成 CLI
用法: python3 gemini_cli.py [选项]

示例:
  python3 gemini_cli.py --theme "十日终焉" --style 悬疑
  python3 gemini_cli.py --prompt "写一个爱情故事"
"""

import argparse
import json
import sys
import os

# 添加 src 到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))


def main():
    parser = argparse.ArgumentParser(description="Gemini 网页版剧本生成器")
    parser.add_argument("--prompt", "-p", type=str, help="自定义提示词")
    parser.add_argument("--theme", "-t", type=str, help="基于热门小说主题")
    parser.add_argument("--style", "-s", type=str, default="悬疑", 
                       choices=["悬疑", "爱情", "仙侠", "都市"],
                       help="剧本风格")
    parser.add_argument("--novel", "-n", type=str, help="基于小说生成")
    parser.add_argument("--output", "-o", type=str, help="输出文件路径")
    
    args = parser.parse_args()
    
    # 构建提示词
    if args.novel:
        # 基于小说生成
        prompt = f"""基于《{args.novel}》的风格，写一个1分钟{args.style}短剧剧本。
要求：
1. 高智商悬疑
2. 紧张刺激
3. 有反转
4. 输出JSON格式：{{"title": "标题", "scenes": [{{"scene": 1, "content": "场景描述", "dialogue": "对白"}}]}}"""
    elif args.prompt:
        prompt = args.prompt
    elif args.theme:
        prompt = f"""基于{args.theme}类型，写一个1分钟{args.style}短剧剧本。
输出JSON格式：{{"title": "标题", "scenes": [{{"scene": 1, "content": "场景描述", "dialogue": "对白"}}]}}"""
    else:
        # 默认：基于热门小说生成
        prompt = f"""基于《十日终焉》和《异兽迷城》的风格，写一个1分钟悬疑惊悚短剧剧本。
要求：
1. 高智商悬疑
2. 紧张刺激
3. 有反转
4. 输出JSON格式：{{"title": "标题", "scenes": [{{"scene": 1, "content": "场景描述", "dialogue": "对白"}}]}}"""
    
    print("=" * 50)
    print("🎬 Gemini 网页版剧本生成器")
    print("=" * 50)
    print(f"\n📝 生成提示词:\n{prompt[:200]}...")
    print("\n⚠️  请在浏览器中手动操作:")
    print("   1. 打开 https://gemini.google.com/u/1/app")
    print("   2. 输入上述提示词")
    print("   3. 复制生成的剧本到 output/ 目录")
    print("\n💡 后续将实现自动化执行...")
    print("=" * 50)
    
    # 尝试导入（如果实现了自动化）
    try:
        from gemini_web_client import GeminiWebClient
        client = GeminiWebClient()
        result = client.generate_script(prompt)
        
        if args.output:
            output_path = args.output
            output_dir = os.path.dirname(output_path)
            if output_dir and not os.path.exists(output_dir):
                os.makedirs(output_dir, exist_ok=True)
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            print(f"\n✅ 剧本已保存到: {args.output}")
        else:
            print(json.dumps(result, ensure_ascii=False, indent=2))
            
    except Exception as e:
        print(f"\n⚠️  自动化功能待实现: {e}")


if __name__ == "__main__":
    main()
