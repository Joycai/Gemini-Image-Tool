from google import genai
from google.genai import types
from PIL import Image
from io import BytesIO
import gradio as gr

# 引入日志模块和国际化模块
import logger_utils
import i18n


def call_google_genai(prompt, image_paths, api_key, model_id, aspect_ratio, resolution):
    """
    调用 Google Gen AI API 生成/编辑图片
    已修复：
    1. 兼容 Gemini 2.5 (参数屏蔽)
    2. 兼容 Gemini 3 Pro (Inline Data)
    3. 支持 i18n 国际化日志
    4. 新增 Token 用量统计
    """
    if not api_key:
        msg = i18n.get("err_apikey")
        logger_utils.log(msg)
        raise gr.Error(msg)

    if not model_id:
        model_id = "gemini-3-pro-image-preview"

    try:
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

        # --- 针对 2.5 模型的参数屏蔽 ---
        if "2.5" in model_id:
            logger_utils.log(i18n.get("detect_25"))
            config = types.GenerateContentConfig(
                response_modalities=["IMAGE"]
            )
        else:
            if not aspect_ratio: aspect_ratio = "1:1"
            if not resolution: resolution = "2K"

            config = types.GenerateContentConfig(
                response_modalities=["IMAGE"],
                image_config=types.ImageConfig(
                    aspect_ratio=aspect_ratio,
                    image_size=resolution
                )
            )

        # 发送请求
        response = client.models.generate_content(
            model=model_id,
            contents=contents,
            config=config
        )

        # ⬇️ 新增：打印 Token 用量 ⬇️
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            u = response.usage_metadata
            # 获取输入、输出和总数
            in_tok = getattr(u, "prompt_token_count", 0)
            out_tok = getattr(u, "candidates_token_count", 0)
            tot_tok = getattr(u, "total_token_count", 0)

            logger_utils.log(i18n.get("log_token_usage", input=in_tok, output=out_tok, total=tot_tok))

        # 检查 parts 是否存在
        if not hasattr(response, 'parts'):
            err_msg = "❌ API Response Error: No 'parts' attribute (Safety Filter?)"
            logger_utils.log(err_msg)
            raise gr.Error(err_msg)

        # 遍历 parts 寻找图片
        for part in response.parts:

            # 1. 优先尝试 Inline Data (Gemini 3 Pro / Standard)
            if part.inline_data and part.inline_data.data:
                try:
                    logger_utils.log(i18n.get("recv_img_inline"))
                    return Image.open(BytesIO(part.inline_data.data))
                except Exception as e:
                    logger_utils.log(f"❌ Parse Inline Data Failed: {e}")
                    continue

            # 2. 备用尝试 SDK Helper (Gemini 2.5 / Newer SDKs)
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

            # 检查是否返回了纯文本警告
            if hasattr(part, 'text') and part.text:
                logger_utils.log(i18n.get("api_text_warn", text=part.text))

        # 错误汇总
        error_text = ""
        for part in response.parts:
            if hasattr(part, 'text') and part.text:
                error_text += part.text

        if error_text:
            err_msg = i18n.get("err_model_text", text=error_text)
            logger_utils.log(err_msg)
            raise gr.Error(err_msg)

        err_msg = i18n.get("err_no_img")
        logger_utils.log(err_msg)
        raise gr.Error(err_msg)

    except Exception as e:
        sys_err_msg = i18n.get("err_sys", err=str(e))
        logger_utils.log(sys_err_msg)
        if isinstance(e, gr.Error):
            raise e
        raise gr.Error(sys_err_msg)