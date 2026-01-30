"""
简单客户端模块
提供基本的客户端功能
"""

import requests

class SimpleClient:
    def __init__(self, base_url):
        self.base_url = base_url
        self.session = requests.Session()
    
    def get(self, endpoint, params=None):
        """发送GET请求"""
        url = f"{self.base_url}/{endpoint}"
        return self.session.get(url, params=params)
    
    def post(self, endpoint, data=None, json=None):
        """发送POST请求"""
        url = f"{self.base_url}/{endpoint}"
        return self.session.post(url, data=data, json=json)
    
    def close(self):
        """关闭客户端连接"""
        self.session.close()