import os

API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
API_BASE = os.getenv("ANTHROPIC_API_BASE", "http://api.dbh.baidu-int.com/v1/")
MODEL = os.getenv("ANTHROPIC_MODEL", "gpt-5.2")  # 更新默认模型
# MODEL = os.getenv("ANTHROPIC_MODEL", "gemini-3-pro-preview")  # 更新默认模型

CUSTOM_HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

############## gemini3 ###################


################### 常规调用 ###########################################################
# API_KEY = "bce-v3/ALTAK-XmUk8V2Xy6yGS9ptI6nSi/5c695a759b75f79d2fd3bf0c66c81476b1cae74d"
# API_BASE = "https://qianfan.baidubce.com/v2"
# MODEL= "qwen3-vl-235b-a22b-instruct" # ok
# MODEL = "qwen3-vl-8b-instruct"  # no ok
# MODEL = "qwen3-vl-8b-instruct" # no ok
# MODEL = "qwen-vl-plus" # no ok
# MODEL = "ernie-4.5-turbo-vl" # no ok
# MODEL = "internvl3-38b" # no ok

# # 纯文本模型
# # MODEL = "deepseek-v3.2"
# # MODEL = "qianfan-lightning-128b-a19b"
# # MODEL = "ernie-5.0-thinking-preview"



# CUSTOM_HEADERS = {
#     "Authorization": f"Bearer {API_KEY}",
#     "Content-Type": "application/json"
# }



# CUSTOM_HEADERS = {
#     "Authorization": f"Bearer {API_KEY}",
#     # 或者可能是
#     "X-API-Key": API_KEY,
# }


# config.py
# import os

# API_KEY = os.getenv("ANTHROPIC_API_KEY", "sk-KoheN3EL0CnZDuE77QmV86rOnpk1Az8jEzQ1wr0RIYyyVUHy")  # 代理提供的 Key
# API_BASE = os.getenv("ANTHROPIC_API_BASE", "https://sg.uiuiapi.com/v1")  # 代理端点
# MODEL = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")

# # 对于代理，可能需要在请求中使用自定义头部
# CUSTOM_HEADERS = {
#     # "Authorization": f"Bearer {API_KEY}",
#     # 或者可能是
#     "X-API-Key": API_KEY,
# }

def _parse_cors_origins() -> list:
    env_value = os.getenv("CORS_ORIGINS", "").strip()
    if env_value:
        return [origin.strip() for origin in env_value.split(",") if origin.strip()]
    return [
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ]


CORS_ORIGINS = _parse_cors_origins()