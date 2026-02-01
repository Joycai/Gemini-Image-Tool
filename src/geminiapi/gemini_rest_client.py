import base64
import json
from io import BytesIO
from typing import List, Optional, Dict, Any

import requests
from PIL import Image

from common import logger_utils, i18n, database as db


def _encode_image(image_path: str) -> str:
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')


def _get_headers(api_key: str) -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "x-goog-api-key": api_key,
        "Content-Type": "application/json"
    }


def _prepare_parts(prompt: Optional[str], image_paths: List[str]) -> List[Dict[str, Any]]:
    parts = []
    if prompt:
        parts.append({"text": prompt})

    for path in image_paths:
        try:
            mime_type = "image/jpeg"
            if path.lower().endswith(".png"):
                mime_type = "image/png"
            elif path.lower().endswith(".webp"):
                mime_type = "image/webp"

            b64_data = _encode_image(path)
            parts.append({
                "inline_data": {
                    "mime_type": mime_type,
                    "data": b64_data
                }
            })
        except Exception as e:
            logger_utils.log(f"Failed to encode image {path}: {e}")
    return parts


def _prepare_payload(parts: List[Dict[str, Any]], aspect_ratio: str, resolution: str) -> Dict[str, Any]:
    image_config = {}
    if aspect_ratio and aspect_ratio != "ar_none":
        image_config["aspectRatio"] = aspect_ratio

    if resolution:
        image_config["imageSize"] = resolution

    safety_settings = [
        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
    ]

    return {
        "contents": [{"parts": parts}],
        "generationConfig": {"imageConfig": image_config},
        "safetySettings": safety_settings
    }


def _handle_request_exception(e: Exception):
    logger_utils.log(f"❌ Gemini REST Request failed: {e}")
    if hasattr(e, 'response') and e.response is not None:
        logger_utils.log(f"Response body: {e.response.text}")


def call_generate_image(
        prompt: Optional[str],
        image_paths: List[str],
        api_key: str,
        model_id: str,
        base_url: str = "https://generativelanguage.googleapis.com/v1beta",
        aspect_ratio: str = "1:1",
        resolution: str = "1024x1024",
) -> Image.Image | None:
    """Calls Gemini REST API for image generation."""
    if not api_key:
        logger_utils.log(i18n.get("api_error_apiKey"))
        return None

    clean_base_url = base_url.rstrip('/')
    url = f"{clean_base_url}/models/{model_id}:generateContent"
    headers = _get_headers(api_key)
    parts = _prepare_parts(prompt, image_paths)
    payload = _prepare_payload(parts, aspect_ratio, resolution)

    try:
        logger_utils.log(f"🚀 Gemini REST Request Sent | Model: {model_id} | AR: {aspect_ratio} | Res: {resolution}")
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()

        data = response.json()

        for candidate in data.get("candidates", []):
            for part in candidate.get("content", {}).get("parts", []):
                img_data = part.get("inline_data", {}).get("data") or part.get("inlineData", {}).get("data")
                if img_data:
                    return Image.open(BytesIO(base64.b64decode(img_data)))
                if "text" in part:
                    logger_utils.log(f"API returned text: {part['text']}")

        logger_utils.log(f"Error: No image data in response. Full response: {data}")
        return None

    except Exception as e:
        _handle_request_exception(e)
        return None


def call_generate_streaming(
        prompt: Optional[str],
        image_paths: List[str],
        api_key: str,
        model_id: str,
        base_url: str = "https://generativelanguage.googleapis.com/v1beta",
        aspect_ratio: str = "1:1",
        resolution: str = "1024x1024",
) -> Image.Image | None:
    if not api_key:
        logger_utils.log(i18n.get("api_error_apiKey"))
        return None

    clean_base_url = base_url.rstrip('/')
    url = f"{clean_base_url}/models/{model_id}:streamGenerateContent?alt=sse&key={api_key}"
    headers = _get_headers(api_key)
    parts = _prepare_parts(prompt, image_paths)
    payload = _prepare_payload(parts, aspect_ratio, resolution)

    try:
        logger_utils.log(f"🚀 Gemini REST Request Sent | Model: {model_id} | AR: {aspect_ratio} | Res: {resolution}")
        response = requests.post(url, headers=headers, json=payload, stream=True)
        response.raise_for_status()

        full_text = []
        for line in response.iter_lines():
            if not line:
                continue

            line_str = line.decode('utf-8')
            if line_str.startswith("data: "):
                line_str = line_str[6:]

            chunk_data = json.loads(line_str)

            if 'cpaUsageMetadata' in chunk_data:
                meta_data = chunk_data.get('cpaUsageMetadata', {})
                candidates_token_count = meta_data.get('candidatesTokenCount', 0)
                prompt_token_count = meta_data.get('promptTokenCount', 0)
                total_token_count = meta_data.get('totalTokenCount', 0)
                db.add_token_usage(model_id, prompt_token_count, candidates_token_count)
                logger_utils.log(i18n.get("api_log_tokenUsage", input=prompt_token_count,
                                          output=candidates_token_count,
                                          total=total_token_count))

            for part in chunk_data.get("candidates", [])[0].get("content", {}).get("parts", []):
                if "text" in part:
                    content = part["text"]
                    print(content, end="", flush=True)
                    full_text.append(content)
                img_b64 = part.get("inline_data", {}).get("data") or part.get("inlineData", {}).get("data")
                if img_b64:
                    return Image.open(BytesIO(base64.b64decode(img_b64)))

        logger_utils.log(f"Error: No image data in response. Full response: {full_text}")
        return None

    except Exception as e:
        _handle_request_exception(e)
        return None
