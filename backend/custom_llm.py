# custom_llm.py
from langchain_openai import ChatOpenAI
import config
import base64
import httpx
from typing import Dict, List, Optional
from langchain_community.chat_models import QianfanChatEndpoint
from langchain.chat_models import init_chat_model

def create_custom_llm():
    return ChatOpenAI(
        api_key=config.API_KEY,
        base_url=config.API_BASE,
        model=config.MODEL,
        temperature=0.35,
        max_tokens=16000,
        streaming=True,
        default_headers=config.CUSTOM_HEADERS
    )
    # return QianfanChatEndpoint(
    #     model=config.MODEL,  # 或其他文心模型
    #     qianfan_ak=config.API_KEY,
    #     # 千帆特定的配置
    #     streaming=True
    # )
    # return init_chat_model(
    #     model=config.MODEL,
    #     # model_provider="anthropic",
    #     model_provider="openai",
    #     # OpenAI provider 支持的参数（通过 **kwargs 传递）
    #     api_key=config.API_KEY,
    #     base_url=config.API_BASE,  # 注意：参数名是 base_url，不是 openai_api_base
    #     temperature=0.3,
    #     max_tokens=16000,
    #     streaming=True,
    #     default_headers=config.CUSTOM_HEADERS if hasattr(config, 'CUSTOM_HEADERS') else None,
    # )
