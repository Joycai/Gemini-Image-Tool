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

    client = OpenAI(api_key=api_key, base_url=base_url)
    
    messages = [
        {"role": "system", "content": system_instruction},
    ]
    
    content = []
    if image_paths:
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
            db.add_token_usage(
                model_id, 
                response.usage.prompt_tokens, 
                response.usage.completion_tokens
            )

        if response.choices and response.choices[0].message.content:
            return response.choices[0].message.content.strip()
        
        raise ValueError("OpenAI API returned empty response.")
            
    except Exception as e:
        logger_utils.log(f"❌ OpenAI Refinement failed: {e}")
        raise e

def call_openai_chat(
    api_key: str,
    base_url: str,
    model_id: str,
    messages: List[Dict[str, Any]]
) -> Tuple[List[Dict[str, Any]], str]:
    """Calls OpenAI-compatible Chat Completion API."""
    if not api_key:
        raise ValueError("OpenAI API Key not configured.")

    client = OpenAI(api_key=api_key, base_url=base_url)
    
    try:
        response = client.chat.completions.create(
            model=model_id,
            messages=messages
        )
        
        if response.usage:
            db.add_token_usage(
                model_id, 
                response.usage.prompt_tokens, 
                response.usage.completion_tokens
            )

        content = response.choices[0].message.content
        new_messages = messages + [{"role": "assistant", "content": content}]
        return new_messages, content

    except Exception as e:
        logger_utils.log(f"❌ OpenAI Chat failed: {e}")
        raise e

def call_openai_image(
    prompt: str,
    api_key: str,
    base_url: str,
    model_id: str,
    aspect_ratio: str = "1:1",
    resolution: str = "1024x1024"
) -> Image.Image | None:
    """Calls OpenAI-compatible Image Generation API (DALL-E)."""
    if not api_key:
        raise ValueError("OpenAI API Key not configured.")

    client = OpenAI(api_key=api_key, base_url=base_url)
    
    # Map resolution and aspect ratio to DALL-E format if needed
    # DALL-E 3 supports 1024x1024, 1792x1024, 1024x1792
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
            img_response = requests.get(img_url)
            if img_response.status_code == 200:
                return Image.open(BytesIO(img_response.content))
        
        raise ValueError("OpenAI API returned no image URL.")

    except Exception as e:
        logger_utils.log(f"❌ OpenAI Image Generation failed: {e}")
        raise e
