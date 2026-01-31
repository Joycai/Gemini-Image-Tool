import base64
import re
from io import BytesIO
from typing import List, Optional, Any, Dict, Tuple

import requests
from PIL import Image
from common import logger_utils, i18n, database as db
from openai import OpenAI


def _encode_image(image_path: str) -> str:
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')


def _pil_to_base64(pil_img: Image.Image) -> str:
    buffered = BytesIO()
    pil_img.save(buffered, format="JPEG")
    return base64.b64encode(buffered.getvalue()).decode('utf-8')


# 2. 定义转换函数（仅在内存操作）
def url_to_base64(url):
    try:
        # 清理 URL 中的标点
        clean_url = url.strip('",.)')

        # 发起下载请求
        response = requests.get(clean_url)
        response.raise_for_status()  # 检查是否成功 (200 OK)

        # 获取二进制数据 (bytes)
        image_bytes = response.content

        # 转换为 Base64 bytes
        b64_bytes = base64.b64encode(image_bytes)

        # 解码为 UTF-8 字符串
        b64_string = b64_bytes.decode('utf-8')

        # 获取图片类型 (MIME type)，比如 image/png
        mime_type = response.headers.get('Content-Type', 'image/png')

        return b64_string, mime_type

    except Exception as e:
        print(f"转换失败: {e}")
        return None, None


def refine_prompt_openai(
        user_prompt: str,
        api_key: str,
        base_url: str,
        model_id: str,
        system_instruction: str,
        image_paths: Optional[List[str]] = None
) -> str:
    """Uses OpenAI-compatible API to refine a prompt."""
    if not api_key:
        raise ValueError("OpenAI API Key not configured.")

    logger_utils.log(f"✨ OpenAI Refine Prompt | Model: {model_id}")
    client = OpenAI(api_key=api_key, base_url=base_url)

    messages = [
        {"role": "system", "content": system_instruction},
    ]

    content = []
    if image_paths:
        logger_utils.log(i18n.get("api_log_loadingImgs", count=len(image_paths)))
        for path in image_paths:
            try:
                base64_image = _encode_image(path)
                content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{base64_image}"
                    }
                })
            except Exception as e:
                logger_utils.log(f"Failed to encode image for OpenAI refinement: {path}, error: {e}")

    content.append({"type": "text", "text": f"User Idea: {user_prompt}"})
    messages.append({"role": "user", "content": content})

    try:
        response = client.chat.completions.create(
            model=model_id,
            messages=messages,
        )

        if response.usage:
            u = response.usage
            logger_utils.log(i18n.get("api_log_tokenUsage", input=u.prompt_tokens,
                                      output=u.completion_tokens,
                                      total=u.total_tokens))
            db.add_token_usage(model_id, u.prompt_tokens, u.completion_tokens)

        if response.choices and response.choices[0].message.content:
            logger_utils.log("✅ OpenAI Refinement successful.")
            return response.choices[0].message.content.strip()

        raise ValueError("OpenAI API returned empty response.")

    except Exception as e:
        logger_utils.log(f"❌ OpenAI Refinement failed: {e}")
        raise e


def call_openai_chat(
        api_key: str,
        base_url: str,
        model_id: str,
        messages: List[Dict[str, Any]],
        prompt_parts: Optional[List[Any]] = None
) -> Tuple[List[Dict[str, Any]], List[Any]]:
    """Calls OpenAI-compatible Chat Completion API with multimodal support."""
    if not api_key:
        raise ValueError("OpenAI API Key not configured.")

    logger_utils.log(f"💬 OpenAI Chat | Model: {model_id}")
    client = OpenAI(api_key=api_key, base_url=base_url)

    # If prompt_parts is provided (multimodal input from UI), we need to format the last message
    if prompt_parts:
        content = []
        img_count = 0
        for part in prompt_parts:
            if isinstance(part, str):
                content.append({"type": "text", "text": part})
            elif isinstance(part, Image.Image):
                base64_image = _pil_to_base64(part)
                content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
                })
                img_count += 1

        if img_count > 0:
            logger_utils.log(i18n.get("api_log_loadingImgs", count=img_count))

        # Replace or append the last user message with multimodal content
        if messages and messages[-1]["role"] == "user":
            messages[-1]["content"] = content
        else:
            messages.append({"role": "user", "content": content})

    try:
        # Check if model supports image generation via chat (like gemini-3-pro-image-preview via OpenAI proxy)
        extra_body = {}
        if "image-preview" in model_id:
            extra_body["response_modalities"] = ["text", "image"]

        response = client.chat.completions.create(
            model=model_id,
            messages=messages,
            extra_body=extra_body if extra_body else None
        )

        if response.usage:
            u = response.usage
            logger_utils.log(i18n.get("api_log_tokenUsage", input=u.prompt_tokens,
                                      output=u.completion_tokens,
                                      total=u.total_tokens))
            db.add_token_usage(model_id, u.prompt_tokens, u.completion_tokens)

        response_parts = []
        message_obj = response.choices[0].message

        # Process text response
        if message_obj.content:
            if isinstance(message_obj.content, str):
                content = message_obj.content
                messages.append({"role": "assistant", "content": content})
                response_parts.append(content)
            elif isinstance(message_obj.content, list):
                # Handle list of parts in content
                text_content = ""
                for part in message_obj.content:
                    if part.get("type") == "text":
                        text_content += part.get("text", "")
                    elif part.get("type") == "image":
                        b64_data = part.get("image", {}).get("base64")
                        if b64_data:
                            img = Image.open(BytesIO(base64.b64decode(b64_data)))
                            response_parts.append(img)
                            logger_utils.log("✅ OpenAI Received Image (Multimodal Output)")
                if text_content:
                    messages.append({"role": "assistant", "content": text_content})
                    response_parts.insert(0, text_content)

        # Process image response (multimodal output) - check other common locations
        if hasattr(message_obj, "data") and message_obj.data:
            for item in message_obj.data:
                if item.get("type") == "image":
                    b64_data = item.get("image", {}).get("base64")
                    if b64_data:
                        img = Image.open(BytesIO(base64.b64decode(b64_data)))
                        response_parts.append(img)
                        logger_utils.log("✅ OpenAI Received Image (Multimodal Output via data)")

        return messages, response_parts

    except Exception as e:
        logger_utils.log(f"❌ OpenAI Chat failed: {e}")
        raise e


def call_openai_image(
        prompt: str,
        api_key: str,
        base_url: str,
        model_id: str,
        aspect_ratio: str = "1:1",
        resolution: str = "1024x1024",
        image_paths: Optional[List[str]] = None
) -> Image.Image | None:
    """Calls OpenAI-compatible Image Generation API (DALL-E or multimodal chat)."""
    if not api_key:
        raise ValueError("OpenAI API Key not configured.")

    # If it's a multimodal model (like gemini-3-pro-image-preview), use chat completions for image gen
    if "image" in model_id:
        client = OpenAI(api_key=api_key, base_url=base_url)

        content = []
        if prompt:
            content.append({"type": "text", "text": prompt})

        if image_paths:
            logger_utils.log(i18n.get("api_log_loadingImgs", count=len(image_paths)))
            for path in image_paths:
                try:
                    base64_image = _encode_image(path)
                    content.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
                    })
                except Exception as e:
                    logger_utils.log(f"Failed to encode image: {path}, error: {e}")

        messages = [{"role": "user", "content": content}]

        try:
            extra_body = {
                "response_modalities": ["text", "image"]
            }
            if 'gemini-3' in model_id:
                if aspect_ratio == "ar_none":
                    extra_body["image_generation_config"] = {
                        "safety_setting": "BLOCK_NONE",
                        "person_generation": "ALLOW_ALL",
                        "image_size": resolution
                    }
                else:
                    extra_body["image_generation_config"] = {
                        "safety_setting": "BLOCK_NONE",
                        "person_generation": "ALLOW_ALL",
                        "aspect_ratio": aspect_ratio,
                        "image_size": resolution
                    }

            logger_utils.log(f"🚀 OpenAI Multimodal Image Request Sent | Model: {model_id}")
            response = client.chat.completions.create(
                model=model_id,
                messages=messages,
                extra_body=extra_body,
                stream=True,
                stream_options={"include_usage": True},
            )

            final_usage = None
            full_image_data = ""
            full_content_data = ""
            print("正在接收图片数据...", end="", flush=True)
            for chunk in response:
                # 检查是否有 usage 信息
                # 在 OpenAI 协议中，最后一个 chunk 的 choices 列表通常为空，但包含 usage 字段
                if chunk.usage is not None:
                    final_usage = chunk.usage
                if len(chunk.choices) > 0:
                    choice = chunk.choices[0]
                    # 检查 finish_reason
                    if choice.finish_reason == "content_filter":
                        logger_utils.log("\n[警告] 内容生成被安全策略拦截 (Content Filter Triggered)")
                        # Gemini 有时会在这里返回 refusal 信息
                        if hasattr(choice, 'message') and hasattr(choice.message, 'refusal'):
                            logger_utils.log(f"拒绝原因: {choice.message.refusal}")
                        break

                    # process data
                    delta = chunk.choices[0].delta

                    # 判断是否有图片数据片段 (在 Gemini 3 协议中通常位于 delta.image 或特定扩展字段)
                    if hasattr(delta, 'image_data'):
                        full_image_data += delta.image_data
                        print(".", end="", flush=True)

                    # 如果你同时也请求了文字
                    if delta.content:
                        full_content_data += delta.content
                        if len(delta.content) < 255:
                            logger_utils.log(f"\n文本描述: {delta.content}")
                        else:
                            logger_utils.log(f"\n文本描述: {delta.content[:255]}...")

            logger_utils.log("\n传输完成！")

            # 打印最终统计 (保持不变)
            if final_usage:
                u = final_usage
                logger_utils.log(i18n.get("api_log_tokenUsage", input=u.prompt_tokens,
                                          output=u.completion_tokens,
                                          total=u.total_tokens))
                db.add_token_usage(model_id, u.prompt_tokens, u.completion_tokens)

            # ==========================================
            # 核心修改：统一图片提取逻辑 (优先级 1 -> 2 -> 3)
            # ==========================================

            # --- 优先级 1: 检查 full_content_data 中是否包含内嵌的 Base64 图片 (Markdown) ---
            # 匹配格式: data:image/jpeg;base64,.....
            # Group 1: mime_type (如 jpeg, png)
            # Group 2: base64 string
            inline_b64_pattern = r"data:image/(\w+);base64,([a-zA-Z0-9+/=]+)"
            inline_matches = re.findall(inline_b64_pattern, full_content_data)

            if inline_matches:
                logger_utils.log(f"✅ 检测到 full_content_data 中包含 {len(inline_matches)} 个内嵌 Base64 图片")
                try:
                    # 通常取第一个匹配到的图片
                    mime_type, b64_str = inline_matches[0]
                    logger_utils.log(f"正在解码内嵌图片 (类型: {mime_type}, 长度: {len(b64_str)})...")
                    return Image.open(BytesIO(base64.b64decode(b64_str)))
                except Exception as e:
                    logger_utils.log(f"⚠️ 内嵌 Base64 解码失败，尝试后续方法: {e}")

            # --- 优先级 2: 检查 full_content_data 中是否包含 Google Storage URL ---
            url_pattern = r"(https?://storage\.googleapis\.com/[^\s)]+)"
            urls = re.findall(url_pattern, full_content_data)

            if urls:
                logger_utils.log(f"\n检测到 {len(urls)} 个云端图片链接，正在下载转换...")
                # 你的辅助函数 (确保 url_to_base64 已定义并引入 request)
                for url in urls:
                    # 清理 URL (去除可能粘连的 Markdown 括号)
                    clean_url = url.strip('",.)]')
                    b64_str, mime_type = url_to_base64(clean_url)

                    if b64_str:
                        logger_utils.log(f"下载并转换成功！Base64 长度: {len(b64_str)}")
                        return Image.open(BytesIO(base64.b64decode(b64_str)))
            else:
                logger_utils.log("未检测到 URL")

            # --- 优先级 3: 检查标准的 delta.image_data 流式累积数据 ---
            if full_image_data:
                logger_utils.log("✅ OpenAI Received Image (Standard Multimodal Stream)")
                return Image.open(BytesIO(base64.b64decode(full_image_data)))

            # 如果三种方式都失败
            logger_utils.log(f"DEBUG - Full Content: {full_content_data[:200]}...")  # 打印前200字用于调试
            raise ValueError("OpenAI API returned no valid image data (checked Inline Base64, URL, and Stream).")

        except Exception as e:
            logger_utils.log(f"❌ OpenAI Multimodal Image Generation failed: {e}")
            raise e

    # Standard DALL-E path
    client = OpenAI(api_key=api_key, base_url=base_url)

    size = "1024x1024"
    if aspect_ratio == "16:9":
        size = "1792x1024"
    elif aspect_ratio == "9:16":
        size = "1024x1792"

    try:
        logger_utils.log(f"🚀 OpenAI Image Request Sent | Model: {model_id} | Size: {size}")
        response = client.images.generate(
            model=model_id,
            prompt=prompt,
            size=size,
            quality="standard",
            n=1,
        )

        if response.data and response.data[0].url:
            img_url = response.data[0].url
            logger_utils.log(f"✅ OpenAI Image URL received: {img_url[:50]}...")
            img_response = requests.get(img_url)
            if img_response.status_code == 200:
                return Image.open(BytesIO(img_response.content))

        raise ValueError("OpenAI API returned no image URL.")

    except Exception as e:
        logger_utils.log(f"❌ OpenAI Image Generation failed: {e}")
        raise e
