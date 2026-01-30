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
    origins = []
    if env_value:
        origins.extend([origin.strip() for origin in env_value.split(",") if origin.strip()])

    render_external_url = os.getenv("RENDER_EXTERNAL_URL", "").strip()
    render_external_hostname = os.getenv("RENDER_EXTERNAL_HOSTNAME", "").strip()
    if render_external_url:
        origins.append(render_external_url)
    if render_external_hostname:
        origins.append(f"https://{render_external_hostname}")

    if not origins:
        origins = [
            "http://localhost:8000",
            "http://127.0.0.1:8000",
        ]

    # 去重并保持顺序
    return list(dict.fromkeys([origin for origin in origins if origin]))


CORS_ORIGINS = _parse_cors_origins()