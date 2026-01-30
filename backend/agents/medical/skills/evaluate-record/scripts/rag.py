import requests
import json
import argparse
import sys

def search_rag_knowledge_bookinfo(query: str, host: str = "http://10.11.133.6:8100", appid: str = "book_info", top_k: int = 3):
    """
    调用 retrieval ensemble 搜索接口 (book_info 版本)
    :param query: 检索内容 (文本)
    :param host: 服务地址 (默认 http://10.11.133.6:8100)
    :param appid: 应用ID (默认 book_info)
    :param top_k: 返回结果数量 (默认 3)
    :return: JSON 响应结果
    """
    url = f"{host}/innerservice/retrieval/search/ensemble"
    headers = {"Content-Type": "application/json"}
    payload = {
        "appid": appid,
        "input": [
            {
                "Content": query,
                "Type": "text",
                "ext": {
                    "url": "",
                    "multiModalAnalyse": {
                        "result": None
                    }
                }
            }
        ],
        "indexName": "",
        "termFilters": None,
        "inFilters": None,
        "num": top_k
    }

    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload), timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"请求失败: {e}")
        return None
    
def search_rag_knowledge_guideline(query: str, host: str = "http://10.11.133.6:8100", appid: str = "guideline_info", top_k: int = 3):
    """
    调用 retrieval ensemble 搜索接口 (book_info 版本)
    :param query: 检索内容 (文本)
    :param host: 服务地址 (默认 http://10.11.133.6:8100)
    :param appid: 应用ID (默认 book_info)
    :param top_k: 返回结果数量 (默认 3)
    :return: JSON 响应结果
    """
    url = f"{host}/innerservice/retrieval/search/ensemble"
    headers = {"Content-Type": "application/json"}
    
    payload = {
        "appid": appid,
        "input": [
            {
                "Content": query,
                "Type": "text",
                "ext": {
                    "url": "",
                    "multiModalAnalyse": {
                        "result": None
                    }
                }
            }
        ],
        "indexName": "",
        "termFilters": None,
        "inFilters": None,
        "num": top_k
    }

    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload), timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"请求失败: {e}")
        return None

def search_rag_knowledge_taboo(query: str, host: str = "http://10.11.132.195:8520/", appid: str = "report_negative_kg", top_k: int = 3):
    """
    调用 retrieval ensemble 搜索接口 (禁忌症知识图谱版本)
    :param query: 检索内容 (文本)
    :param host: 服务地址 (默认 http://10.11.132.195:8520/)
    :param appid: 应用ID (默认 report_negative_kg)
    :param top_k: 返回结果数量 (默认 3)
    :return: JSON 响应结果
    """
    url = f"{host}/innerservice/retrieval/search/ensemble"
    headers = {"Content-Type": "application/json"}
    payload = {
        "appid": appid,
        "input": [
            {
                "Content": query,
                "Type": "text",
                "ext": {
                    "url": "",
                    "multiModalAnalyse": {
                        "result": None
                    }
                }
            }
        ],
        "indexName": "",
        "termFilters": None,
        "inFilters": None,
        "num": top_k
    }

    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload), timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"请求失败: {e}")
        return None

def format_results(results):
    """格式化输出结果"""
    if not results or results.get("status") != 0:
        print("未找到相关结果")
        return
    
    data = results.get("data", {})
    total = data.get("Total", 0)
    items = data.get("List", [])
    
    print(f"找到 {total} 条相关结果:\n")
    
    for i, item in enumerate(items, 1):
        print(f"--- 结果 {i} ---")
        print(f"分数: {item.get('score', 0):.3f}")
        
        # 处理item['data']可能是字符串的情况
        item_data = item.get('data', {})
        if isinstance(item_data, str):
            try:
                import json
                item_data = json.loads(item_data)
            except json.JSONDecodeError:
                item_data = {}
        
        print(f"标题: {item_data.get('title', 'N/A')}")
        print(f"内容: {item_data.get('content', 'N/A')[:200]}...")
        print(f"来源: {item_data.get('book_name', 'N/A')}")
        print(f"作者: {', '.join(item_data.get('author_list', []))}")
        print()

def main():
    """命令行主函数"""
    parser = argparse.ArgumentParser(description="医学知识检索工具")
    parser.add_argument("--query", type=str, required=True, help="检索查询内容")
    parser.add_argument("--top_k", type=int, default=3, help="返回结果数量 (默认: 3)")
    parser.add_argument("--source", choices=["book", "taboo", "guideline"], default="book", 
                       help="检索源: book(医学书籍) 或 taboo(禁忌症知识图谱)")
    parser.add_argument("--host", type=str, help="自定义服务地址")
    
    args = parser.parse_args()
    
    # 选择检索函数
    if args.source == "book":
        search_func = search_rag_knowledge_bookinfo
        default_host = "http://10.11.133.6:8100"
    elif args.source == "guideline":
        search_func = search_rag_knowledge_guideline
        default_host = "http://10.11.133.6:8100"
    else:
        search_func = search_rag_knowledge_taboo
        default_host = "http://10.11.132.195:8520/"
    
    host = args.host or default_host
    
    print(f"开始检索: {args.query}")
    print(f"参数: top_k={args.top_k}, source={args.source}, host={host}\n")
    
    # 执行检索
    results = search_func(
        query=args.query,
        host=host,
        top_k=args.top_k
    )
    
    # 格式化输出
    format_results(results)

if __name__ == "__main__":
    main()