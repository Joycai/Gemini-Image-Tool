import time
from google import genai
from google.genai import types
from PIL import Image
from io import BytesIO
import gradio as gr
import logger_utils
import i18n


def call_google_genai(prompt, image_paths, api_key, model_id, aspect_ratio, resolution):
    """
    调用 Google API (带重试机制)
    """
    if not api_key:
        msg = i18n.get("err_apikey")
        logger_utils.log(msg)
        raise gr.Error(msg)

    if not model_id:
        model_id = "gemini-3-pro-image-preview"

    client = genai.Client(api_key=api_key)

    # 准备配置和内容
    contents = [prompt]
    if image_paths:
        logger_utils.log(i18n.get("loading_imgs", count=len(image_paths)))
        for path in image_paths:
            try:
                img = Image.open(path)
                contents.append(img)
            except Exception as e:
                logger_utils.log(i18n.get("skip_img", path=path, err=e))

    logger_utils.log(i18n.get("req_sent", model=model_id, ar=aspect_ratio, res=resolution))

    if "2.5" in model_id:
        config = types.GenerateContentConfig(response_modalities=["IMAGE"])
    else:
        if not aspect_ratio: aspect_ratio = "1:1"
        if not resolution: resolution = "2K"
        config = types.GenerateContentConfig(
            response_modalities=["IMAGE"],
            image_config=types.ImageConfig(aspect_ratio=aspect_ratio, image_size=resolution)
        )

    # ⬇️ 新增：重试逻辑 (最多重试 3 次)
    max_retries = 3
    last_exception = None

    for attempt in range(max_retries):
        try:
            if attempt > 0:
                logger_utils.log(f"🔄 网络重试 (第 {attempt + 1}/{max_retries} 次)...")

            # 发起请求
            response = client.models.generate_content(
                model=model_id,
                contents=contents,
                config=config
            )

            # ⬇️ 解析逻辑 (保持不变)
            if hasattr(response, "usage_metadata") and response.usage_metadata:
                u = response.usage_metadata
                logger_utils.log(i18n.get("log_token_usage", input=getattr(u, "prompt_token_count", 0),
                                          output=getattr(u, "candidates_token_count", 0),
                                          total=getattr(u, "total_token_count", 0)))

            if not hasattr(response, 'parts'):
                raise ValueError("No 'parts' in response")

            for part in response.parts:
                if part.inline_data and part.inline_data.data:
                    logger_utils.log(i18n.get("recv_img_inline"))
                    return Image.open(BytesIO(part.inline_data.data))

                if hasattr(part, "as_image"):
                    try:
                        g_img = part.as_image()
                        if hasattr(g_img, "data"):
                            return Image.open(BytesIO(g_img.data))
                        elif hasattr(g_img, "_pil_image"):
                            return g_img._pil_image
                    except:
                        pass

                if hasattr(part, 'text') and part.text:
                    raise ValueError(f"Text response: {part.text}")

            raise ValueError("No valid image data found")

        except Exception as e:
            last_exception = e
            # 如果是严重错误（如 API Key 错误），直接抛出不重试
            if "401" in str(e) or "403" in str(e):
                break

            # 如果是网络错误，等待后重试
            time.sleep(2 * (attempt + 1))  # 递增等待 2s, 4s, 6s
            continue

    # 如果 3 次都失败了
    sys_err_msg = i18n.get("err_sys", err=str(last_exception))
    logger_utils.log(sys_err_msg)
    raise gr.Error(sys_err_msg)