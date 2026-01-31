import base64
import re
from io import BytesIO
from typing import List, Optional, Any, Dict, Tuple

import requests
from PIL import Image
from openai import OpenAI

from common import logger_utils, i18n, database as db


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


def _prepare_chat_messages(
        messages: List[Dict[str, Any]],
        prompt_parts: Optional[List[Any]] = None
) -> List[Dict[str, Any]]:
    """Common logic to prepare messages for chat, handling multimodal inputs."""
    if not prompt_parts:
        return messages

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

    new_messages = messages.copy()
    if new_messages and new_messages[-1]["role"] == "user":
        last_msg = new_messages[-1].copy()
        last_msg["content"] = content
        new_messages[-1] = last_msg
    else:
        new_messages.append({"role": "user", "content": content})

    return new_messages


def _extract_multimodal_parts(full_content_data: str, full_image_data: str) -> List[Any]:
    """Extracts text and images from raw response data using 3-tier logic."""
    parts = []
    if full_content_data:
        parts.append(full_content_data)

    # 1. Inline Base64
    inline_b64_pattern = r"data:image/(\w+);base64,([a-zA-Z0-9+/=]+)"
    inline_matches = re.findall(inline_b64_pattern, full_content_data)
    for mime_type, b64_str in inline_matches:
        try:
            parts.append(Image.open(BytesIO(base64.b64decode(b64_str))))
            logger_utils.log(f"✅ Extracted inline image ({mime_type})")
        except Exception as e:
            logger_utils.log(f"⚠️ Failed to decode inline image: {e}")

    # 2. Cloud URL
    url_pattern = r"(https?://storage\.googleapis\.com/[^\s)]+)"
    urls = re.findall(url_pattern, full_content_data)
    for url in urls:
        clean_url = url.strip('",.)]')
        b64_str, _ = url_to_base64(clean_url)
        if b64_str:
            try:
                parts.append(Image.open(BytesIO(base64.b64decode(b64_str))))
                logger_utils.log("✅ Downloaded and extracted cloud image")
            except Exception as e:
                logger_utils.log(f"⚠️ Failed to decode cloud image: {e}")

    # 3. Standard Stream
    if full_image_data:
        try:
            parts.append(Image.open(BytesIO(base64.b64decode(full_image_data))))
            logger_utils.log("✅ Extracted streamed image data")
        except Exception as e:
            logger_utils.log(f"⚠️ Failed to decode streamed image: {e}")

    return parts


def _execute_multimodal_request(
        client: OpenAI,
        model_id: str,
        messages: List[Dict[str, Any]],
        aspect_ratio: Optional[str] = None,
        resolution: Optional[str] = None
) -> Tuple[str, str, Any]:
    """Phase 2: Execute the api and fetch response parts (Streaming)."""

    extra_body = {
        "response_modalities": ["text", "image"],
        'extra_body': {
            "google": {
                "generation_config" : {
                    "imageConfig": {}
                },
                "safety_settings": [
                    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
                ]
            }
        }
    }
    # Only add image_generation_config if resolution is provided (implies generation intent)
    if 'gemini-3' in model_id and resolution:
        config = {
            "image_size": resolution
        }
        if aspect_ratio and aspect_ratio != "ar_none":
            config["aspect_ratio"] = aspect_ratio
        extra_body["extra_body"]["google"]["generation_config"]["imageConfig"] = config

    logger_utils.log(f"🚀 OpenAI Multimodal Request Sent | Model: {model_id}")
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
    logger_utils.log("正在接收数据...")
    for chunk in response:
        if chunk.usage is not None:
            final_usage = chunk.usage
        if len(chunk.choices) > 0:
            choice = chunk.choices[0]
            if choice.finish_reason == "content_filter":
                logger_utils.log("\n[警告] 内容生成被安全策略拦截 (Content Filter Triggered)")
                break

            delta = choice.delta
            if hasattr(delta, 'image_data') and delta.image_data:
                full_image_data += delta.image_data
                print(".", end="", flush=True)
            elif hasattr(delta, 'content') and delta.content:
                full_content_data += delta.content
            elif hasattr(delta, 'reasoning_content'):
                logger_utils.log(delta.reasoning_content)

    logger_utils.log("\n传输完成！")
    return full_content_data, full_image_data, final_usage


def _call_openai_multimodal_chat(
        client: OpenAI,
        model_id: str,
        messages: List[Dict[str, Any]]
) -> Tuple[List[Dict[str, Any]], List[Any]]:
    """Handles chat for models that can output multimodal content (text + images)."""
    # 1. Execute request (reusing shared logic)
    full_content_data, full_image_data, final_usage = _execute_multimodal_request(
        client, model_id, messages
    )

    # 2. Log usage
    if final_usage:
        db.add_token_usage(model_id, final_usage.prompt_tokens, final_usage.completion_tokens)
        logger_utils.log(i18n.get("api_log_tokenUsage", input=final_usage.prompt_tokens,
                                  output=final_usage.completion_tokens,
                                  total=final_usage.total_tokens))

    # 3. Extract parts
    response_parts = _extract_multimodal_parts(full_content_data, full_image_data)

    # 4. Update messages with text content
    new_messages = messages.copy()
    if full_content_data:
        new_messages.append({"role": "assistant", "content": full_content_data})

    return new_messages, response_parts


def _call_openai_standard_chat(
        client: OpenAI,
        model_id: str,
        messages: List[Dict[str, Any]]
) -> Tuple[List[Dict[str, Any]], List[Any]]:
    """Handles standard text-only chat completions."""
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

    message_obj = response.choices[0].message
    new_messages = messages.copy()
    response_parts = []

    if message_obj.content and isinstance(message_obj.content, str):
        content = message_obj.content
        new_messages.append({"role": "assistant", "content": content})
        response_parts.append(content)

    return new_messages, response_parts


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

    prepared_messages = _prepare_chat_messages(messages, prompt_parts)

    try:
        if "gemini-3" in model_id or "image" in model_id:
            return _call_openai_multimodal_chat(client, model_id, prepared_messages)
        else:
            return _call_openai_standard_chat(client, model_id, prepared_messages)

    except Exception as e:
        logger_utils.log(f"❌ OpenAI Chat failed: {e}")
        raise e


def _prepare_multimodal_messages(prompt: str, image_paths: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """Phase 1: Prepare the message to be sent."""
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

    return [{"role": "user", "content": content}]


def _call_openai_multimodal_image(
        prompt: str,
        api_key: str,
        base_url: str,
        model_id: str,
        aspect_ratio: str = "1:1",
        resolution: str = "1024x1024",
        image_paths: Optional[List[str]] = None
) -> Image.Image | None:
    """Handles image generation for multimodal models (like Gemini 3) via Chat Completions."""
    client = OpenAI(api_key=api_key, base_url=base_url)

    try:
        # 1. Prepare
        messages = _prepare_multimodal_messages(prompt, image_paths)

        # 2. Execute (reusing shared logic)
        full_content_data, full_image_data, final_usage = _execute_multimodal_request(
            client, model_id, messages, aspect_ratio, resolution
        )

        # 3. Log usage
        if final_usage:
            db.add_token_usage(model_id, final_usage.prompt_tokens, final_usage.completion_tokens)
            logger_utils.log(i18n.get("api_log_tokenUsage", input=final_usage.prompt_tokens,
                                      output=final_usage.completion_tokens,
                                      total=final_usage.total_tokens))

        # 4. Extract and return the first image found
        parts = _extract_multimodal_parts(full_content_data, full_image_data)
        for part in parts:
            if isinstance(part, Image.Image):
                return part

        logger_utils.log(f"DEBUG - Full Content: {full_content_data[:200]}...")
        raise ValueError("OpenAI API returned no valid image data.")

    except Exception as e:
        logger_utils.log(f"❌ OpenAI Multimodal Image Generation failed: {e}")
        raise e


def _call_openai_standard_image(
        prompt: str,
        api_key: str,
        base_url: str,
        model_id: str,
        aspect_ratio: str = "1:1"
) -> Image.Image | None:
    """Handles standard image generation (DALL-E series)."""
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

    if "gemini-3" in model_id or "image" in model_id:
        return _call_openai_multimodal_image(
            prompt=prompt,
            api_key=api_key,
            base_url=base_url,
            model_id=model_id,
            aspect_ratio=aspect_ratio,
            resolution=resolution,
            image_paths=image_paths
        )
    else:
        return _call_openai_standard_image(
            prompt=prompt,
            api_key=api_key,
            base_url=base_url,
            model_id=model_id,
            aspect_ratio=aspect_ratio
        )
