import os
from typing import List, Any, Optional, Dict, Tuple
from PIL import Image

from common import logger_utils, i18n, database as db
from geminiapi import google_genai_client
from geminiapi import openai_client
from geminiapi import gemini_rest_client

def _get_api_credentials(model_info: Dict[str, Any]) -> Tuple[str, Optional[str]]:
    """Helper to get the correct API key and base URL based on model and settings."""
    settings = db.get_all_settings()
    series = model_info["series"]
    
    if series == "google-genai":
        # Logic for Google GenAI: Paid vs Free
        if settings.get("google_use_paid_for_all"):
            return settings.get("google_paid_api_key"), None
        
        if model_info.get("is_paid"):
            return settings.get("google_paid_api_key"), None
        else:
            return settings.get("google_free_api_key"), None
            
    elif series == "openai":
        return settings.get("openai_api_key"), settings.get("openai_base_url")
    
    elif series == "gemini_rest_api":
        # Per request, use openai-api key for gemini_rest_api series
        return settings.get("openai_api_key"), db.get_setting("gemini_rest_base_url", "https://generativelanguage.googleapis.com/v1beta")
    
    return None, None

def generate_image(
    prompt: Optional[str],
    image_paths: List[str],
    model_id: str,
    aspect_ratio: str,
    resolution: str,
    max_retries: int = 3
) -> Image.Image | None:
    """Unified interface for image generation."""
    model_info = db.get_model(model_id)
    if not model_info:
        logger_utils.log(f"Error: Model {model_id} not found in database.")
        return None

    api_key, base_url = _get_api_credentials(model_info)
    
    if model_info["series"] == "google-genai":
        return google_genai_client.call_google_genai(
            prompt=prompt,
            image_paths=image_paths,
            api_key=api_key,
            model_id=model_id,
            aspect_ratio=aspect_ratio,
            resolution=resolution,
            max_retries=max_retries
        )
    elif model_info["series"] == "openai":
        return openai_client.call_openai_image(
            prompt=prompt,
            api_key=api_key,
            base_url=base_url,
            model_id=model_id,
            aspect_ratio=aspect_ratio,
            resolution=resolution,
            image_paths=image_paths
        )
    elif model_info["series"] == "gemini_rest_api":
        return gemini_rest_client.call_generate_image(
            prompt=prompt,
            image_paths=image_paths,
            api_key=api_key,
            model_id=model_id,
            base_url=base_url,
            aspect_ratio=aspect_ratio,
            resolution=resolution
        )
    
    return None

def chat_completions(
    model_id: str,
    messages: List[Dict[str, Any]],
    prompt_parts: Optional[List[Any]] = None,
    chat_session: Optional[Any] = None,
    aspect_ratio: str = "ar_none",
    resolution: str = "2K"
) -> Any:
    """Unified interface for chat completions."""
    model_info = db.get_model(model_id)
    if not model_info:
        logger_utils.log(f"Error: Model {model_id} not found in database.")
        return None

    api_key, base_url = _get_api_credentials(model_info)

    if model_info["series"] == "google-genai":
        genai_client = google_genai_client.genai.Client(api_key=api_key)
        return google_genai_client.call_google_chat(
            genai_client=genai_client,
            chat_session=chat_session,
            prompt_parts=prompt_parts,
            model_id=model_id,
            aspect_ratio=aspect_ratio,
            resolution=resolution
        )
    elif model_info["series"] == "openai":
        return openai_client.call_openai_chat(
            api_key=api_key,
            base_url=base_url,
            model_id=model_id,
            messages=messages,
            prompt_parts=prompt_parts
        )
    
    # Note: gemini_rest_api currently only supports Image tag as per requirements

    return None

def refine_prompt(
    user_prompt: str,
    model_id: str,
    task_type: str = "cosplay_photo",
    image_paths: Optional[List[str]] = None
) -> str:
    """Unified interface for prompt refinement."""
    model_info = db.get_model(model_id)
    if not model_info:
        # Fallback to a default if model not found
        model_id = db.get_setting("refine_model_id", "gemini-1.5-flash")
        model_info = db.get_model(model_id)

    api_key, base_url = _get_api_credentials(model_info)

    if model_info["series"] == "google-genai":
        return google_genai_client.refine_prompt(
            user_prompt=user_prompt,
            api_key=api_key,
            model_id=model_id,
            task_type=task_type,
            image_paths=image_paths
        )
    elif model_info["series"] == "openai":
        # Get system instruction
        db_task = db.get_refine_task(task_type)
        system_instruction = db_task["system_instruction"] if db_task else ""
        
        return openai_client.refine_prompt_openai(
            user_prompt=user_prompt,
            api_key=api_key,
            base_url=base_url,
            model_id=model_id,
            system_instruction=system_instruction,
            image_paths=image_paths
        )

    return user_prompt
