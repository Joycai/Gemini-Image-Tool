import os
from typing import List, Any, Optional, Dict, Tuple
from PIL import Image

from common import logger_utils, i18n, database as db
from geminiapi import api_client
from geminiapi import openai_client

def generate_image(
    prompt: Optional[str],
    image_paths: List[str],
    model_id: str,
    aspect_ratio: str,
    resolution: str,
    max_retries: int = 3
) -> Image.Image | None:
    """Unified interface for image generation."""
    # We need to know the series to route correctly. 
    # Since model_id might not be unique across series, we should ideally pass series too.
    # For now, we'll try to find the model and assume the first match is correct, 
    # or better, we can look at the context (e.g., if OpenAI API key is set and Google isn't).
    # A better fix is to make the UI pass both ID and Series.

    model_info = db.get_model(model_id)
    if not model_info:
        logger_utils.log(f"Error: Model {model_id} not found in database.")
        return None

    settings = db.get_all_settings()
    
    if model_info["series"] == "google-genai":
        api_key = settings.get("api_key")
        return api_client.call_google_genai(
            prompt=prompt,
            image_paths=image_paths,
            api_key=api_key,
            model_id=model_id,
            aspect_ratio=aspect_ratio,
            resolution=resolution,
            max_retries=max_retries
        )
    elif model_info["series"] == "openai":
        api_key = settings.get("openai_api_key")
        base_url = settings.get("openai_base_url")
        return openai_client.call_openai_image(
            prompt=prompt,
            api_key=api_key,
            base_url=base_url,
            model_id=model_id,
            aspect_ratio=aspect_ratio,
            resolution=resolution,
            image_paths=image_paths
        )
    
    return None

def chat_completions(
    model_id: str,
    messages: List[Dict[str, Any]],
    prompt_parts: Optional[List[Any]] = None, # For Gemini multimodal
    chat_session: Optional[Any] = None, # For Gemini stateful chat
    aspect_ratio: str = "ar_none",
    resolution: str = "2K"
) -> Any:
    """Unified interface for chat completions."""
    model_info = db.get_model(model_id)
    if not model_info:
        logger_utils.log(f"Error: Model {model_id} not found in database.")
        return None

    settings = db.get_all_settings()

    if model_info["series"] == "google-genai":
        api_key = settings.get("api_key")
        genai_client = api_client.genai.Client(api_key=api_key)
        return api_client.call_google_chat(
            genai_client=genai_client,
            chat_session=chat_session,
            prompt_parts=prompt_parts,
            model_id=model_id,
            aspect_ratio=aspect_ratio,
            resolution=resolution
        )
    elif model_info["series"] == "openai":
        api_key = settings.get("openai_api_key")
        base_url = settings.get("openai_base_url")
        return openai_client.call_openai_chat(
            api_key=api_key,
            base_url=base_url,
            model_id=model_id,
            messages=messages,
            prompt_parts=prompt_parts
        )

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
        model_id = db.get_setting("refine_model_id", "gemini-3-flash-preview")
        model_info = db.get_model(model_id)

    settings = db.get_all_settings()

    if model_info["series"] == "google-genai":
        api_key = settings.get("refine_api_key") or settings.get("api_key")
        return api_client.refine_prompt(
            user_prompt=user_prompt,
            api_key=api_key,
            model_id=model_id,
            task_type=task_type,
            image_paths=image_paths
        )
    elif model_info["series"] == "openai":
        api_key = settings.get("openai_api_key")
        base_url = settings.get("openai_base_url")
        
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
