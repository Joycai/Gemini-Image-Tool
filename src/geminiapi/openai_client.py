import base64
import os
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
        
        # Process text response
        if response.choices[0].message.content:
            content = response.choices[0].message.content
            messages.append({"role": "assistant", "content": content})
            response_parts.append(content)
        
        # Process image response (multimodal output)
        message_obj = response.choices[0].message
        if hasattr(message_obj, "data") and message_obj.data:
            for item in message_obj.data:
                if item.get("type") == "image":
                    b64_data = item.get("image", {}).get("base64")
                    if b64_data:
                        img = Image.open(BytesIO(base64.b64decode(b64_data)))
                        response_parts.append(img)
                        logger_utils.log("✅ OpenAI Received Image (Multimodal Output)")

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
    if "image-preview" in model_id:
        messages = []
        content = [{"type": "text", "text": prompt}]
        if image_paths:
            logger_utils.log(i18n.get("api_log_loadingImgs", count=len(image_paths)))
            for path in image_paths:
                base64_image = _encode_image(path)
                content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
                })
        messages.append({"role": "user", "content": content})
        
        _, parts = call_openai_chat(api_key, base_url, model_id, messages)
        for part in parts:
            if isinstance(part, Image.Image):
                return part
        return None

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
