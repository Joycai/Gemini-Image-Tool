import base64
from io import BytesIO
from typing import List, Optional

import requests
from PIL import Image

from common import logger_utils, i18n


def _encode_image(image_path: str) -> str:
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

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

    # Ensure base_url doesn't end with a slash for consistent joining
    clean_base_url = base_url.rstrip('/')
    url = f"{clean_base_url}/models/{model_id}:generateContent"

    headers = {
        "Authorization": "Bearer " + api_key,
        "x-goog-api-key": api_key,
        "Content-Type": "application/json"
    }

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

    # Build Generation Config
    image_config = {}
    if aspect_ratio and aspect_ratio != "ar_none":
        image_config["aspectRatio"] = aspect_ratio

    if resolution:
        image_config["imageSize"] = resolution

    # Build Safety Settings (Set to BLOCK_NONE for maximum flexibility)
    safety_settings = [
        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
    ]

    payload = {
        "contents": [{
            "parts": parts
        }],
        "generationConfig": {
            "imageConfig": image_config
        },
        "safetySettings": safety_settings
    }

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
        logger_utils.log(f"❌ Gemini REST Request failed: {e}")
        if hasattr(e, 'response') and e.response is not None:
            logger_utils.log(f"Response body: {e.response.text}")
        return None
