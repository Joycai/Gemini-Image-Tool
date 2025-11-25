import time
from google import genai
from google.genai import types
from PIL import Image
from io import BytesIO
import gradio as gr
import logger_utils
import i18n

# [新增] 模型配置字典，方便未來擴展
MODEL_CONFIGS = {
    "default": {
        "ignore_params": False,
        "base_config": {"response_modalities": ["IMAGE"]}
    },
    "gemini-flash": { # 修正：使用更通用的 'flash' 键
        "ignore_params": True, # Flash 系列忽略比例和分辨率
        "base_config": {"response_modalities": ["IMAGE"]}
    }
}


def _get_model_config(model_id, aspect_ratio, resolution):
    """根據模型 ID 返回對應的配置對象"""
    # 修正：检查模型 ID 是否包含 'flash'
    is_flash_model = "flash" in model_id

    if is_flash_model:
        logger_utils.log(i18n.get("api_log_gemini25")) # 日志消息可以保留，或创建一个更通用的
        return types.GenerateContentConfig(**MODEL_CONFIGS["gemini-flash"]["base_config"])
    else:
        # Gemini 1.5 Pro 或其他標準模型
        if not resolution: resolution = "2K"

        image_config_dict = {"image_size": resolution}
        
        # 仅当 aspect_ratio 被指定且不是 "ar_none" 时才添加它
        if aspect_ratio and aspect_ratio != "ar_none":
            image_config_dict["aspect_ratio"] = aspect_ratio
        
        return types.GenerateContentConfig(
            response_modalities=["IMAGE"],
            image_config=types.ImageConfig(**image_config_dict)
        )

def call_google_genai(prompt, image_paths, api_key, model_id, aspect_ratio, resolution):
    if not api_key:
        msg = i18n.get("api_error_apiKey")
        logger_utils.log(msg)
        raise gr.Error(msg)

    if not model_id:
        model_id = "gemini-1.5-pro" # 修正：与新模型名称保持一致

    client = genai.Client(api_key=api_key)

    contents = [prompt]
    if image_paths:
        logger_utils.log(i18n.get("api_log_loadingImgs", count=len(image_paths)))
        for path in image_paths:
            try:
                img = Image.open(path)
                contents.append(img)
            except Exception as e:
                logger_utils.log(i18n.get("api_log_skipImg", path=path, err=e))

    # 在日志中显示用户选择的原始值，即使是 "ar_none"
    ar_log_val = i18n.get(aspect_ratio, aspect_ratio)
    logger_utils.log(i18n.get("api_log_requestInfo", prompt_len=len(prompt), img_count=len(image_paths)))
    logger_utils.log(i18n.get("api_log_requestSent", model=model_id, ar=ar_log_val, res=resolution))

    config = _get_model_config(model_id, aspect_ratio, resolution)

    max_retries = 3
    last_exception = None

    for attempt in range(max_retries):
        try:
            if attempt > 0:
                logger_utils.log(i18n.get("api_log_networkRetry", attempt=attempt + 1, max_retries=max_retries))

            response = client.models.generate_content(
                model=model_id,
                contents=contents,
                config=config
            )

            if hasattr(response, "usage_metadata") and response.usage_metadata:
                u = response.usage_metadata
                logger_utils.log(i18n.get("api_log_tokenUsage", input=getattr(u, "prompt_token_count", 0),
                                          output=getattr(u, "candidates_token_count", 0),
                                          total=getattr(u, "total_token_count", 0)))

            if not hasattr(response, 'parts'):
                raise ValueError(i18n.get("api_error_noParts"))

            for part in response.parts:
                if part.inline_data and part.inline_data.data:
                    logger_utils.log(i18n.get("api_log_receivedImgInline"))
                    return Image.open(BytesIO(part.inline_data.data))

                if hasattr(part, "as_image"):
                    try:
                        g_img = part.as_image()
                        if hasattr(g_img, "data"):
                            logger_utils.log(i18n.get("api_log_receivedImgSdk"))
                            return Image.open(BytesIO(g_img.data))
                        elif hasattr(g_img, "_pil_image"):
                            logger_utils.log(i18n.get("api_log_receivedImgSdk"))
                            return g_img._pil_image
                    except:
                        pass

                if hasattr(part, 'text') and part.text:
                    raise ValueError(i18n.get("api_error_textResponse", text=part.text))

            raise ValueError(i18n.get("api_error_noValidImage"))

        except Exception as e:
            last_exception = e
            if "401" in str(e) or "403" in str(e):
                break
            time.sleep(2 * (attempt + 1))
            continue

    sys_err_msg = i18n.get("api_error_system", err=str(last_exception))
    logger_utils.log(sys_err_msg)
    raise gr.Error(sys_err_msg)