import time
from google import genai
from google.genai import types
from PIL import Image
from io import BytesIO
import gradio as gr
import logger_utils
import i18n

def call_google_genai(prompt, image_paths, api_key, model_id, aspect_ratio, resolution):
    if not api_key:
        msg = i18n.get("err_apikey")
        logger_utils.log(msg)
        raise gr.Error(msg)

    if not model_id:
        model_id = "gemini-3-pro-image-preview"

    client = genai.Client(api_key=api_key)

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
        logger_utils.log(i18n.get("detect_25"))
        config = types.GenerateContentConfig(response_modalities=["IMAGE"])
    else:
        if not aspect_ratio: aspect_ratio = "1:1"
        if not resolution: resolution = "2K"
        config = types.GenerateContentConfig(
            response_modalities=["IMAGE"],
            image_config=types.ImageConfig(aspect_ratio=aspect_ratio, image_size=resolution)
        )

    max_retries = 3
    last_exception = None

    for attempt in range(max_retries):
        try:
            if attempt > 0:
                logger_utils.log(f"🔄 网络重试 (第 {attempt + 1}/{max_retries} 次)...")

            response = client.models.generate_content(
                model=model_id,
                contents=contents,
                config=config
            )

            if hasattr(response, "usage_metadata") and response.usage_metadata:
                u = response.usage_metadata
                logger_utils.log(i18n.get("log_token_usage", input=getattr(u, "prompt_token_count", 0),
                                          output=getattr(u, "candidates_token_count", 0),
                                          total=getattr(u, "total_token_count", 0)))

            if not hasattr(response, 'parts'):
                raise ValueError(i18n.get("err_no_parts"))

            for part in response.parts:
                if part.inline_data and part.inline_data.data:
                    logger_utils.log(i18n.get("recv_img_inline"))
                    return Image.open(BytesIO(part.inline_data.data))

                if hasattr(part, "as_image"):
                    try:
                        g_img = part.as_image()
                        if hasattr(g_img, "data"):
                            logger_utils.log(i18n.get("recv_img_sdk"))
                            return Image.open(BytesIO(g_img.data))
                        elif hasattr(g_img, "_pil_image"):
                            logger_utils.log(i18n.get("recv_img_sdk"))
                            return g_img._pil_image
                    except:
                        pass

                if hasattr(part, 'text') and part.text:
                    raise ValueError(i18n.get("err_text_response", text=part.text))

            raise ValueError(i18n.get("err_no_valid_image"))

        except Exception as e:
            last_exception = e
            if "401" in str(e) or "403" in str(e):
                break
            time.sleep(2 * (attempt + 1))
            continue

    sys_err_msg = i18n.get("err_sys", err=str(last_exception))
    logger_utils.log(sys_err_msg)
    raise gr.Error(sys_err_msg)