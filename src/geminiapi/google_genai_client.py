import os
import time
from io import BytesIO
from typing import List, Any, Optional, Dict

from PIL import Image
from google import genai
from google.genai import types
from google.genai.chats import Chat
from google.genai.types import PIL_Image

from common import logger_utils, i18n, database as db
from common.config import MODEL_SELECTOR_DEFAULT
from common.prompts import REFINE_TASKS


def _get_model_config(model_id: str, aspect_ratio: str, resolution: str) -> types.GenerateContentConfig:
    """Returns the configuration object for Google GenAI models."""
    is_gemini25_model = "gemini-2.5" in model_id

    if is_gemini25_model:
        logger_utils.log(i18n.get("api_log_gemini25"))
        return types.GenerateContentConfig(
            response_modalities=["IMAGE"]
        )
    else:
        if not resolution:
            resolution = "2K"

        image_config_dict: Dict[str, Any] = {"image_size": resolution}

        if aspect_ratio and aspect_ratio != "ar_none":
            image_config_dict["aspect_ratio"] = aspect_ratio

        return types.GenerateContentConfig(
            response_modalities=["IMAGE"],
            image_config=types.ImageConfig(**image_config_dict)
        )


def _process_response_parts(response_parts: List[Any]) -> Optional['PIL_Image']:
    """Processes image parts in API response and extracts PIL.Image objects."""
    for part in response_parts:
        if part.inline_data and part.inline_data.data:
            logger_utils.log(i18n.get("api_log_receivedImgInline"))
            return Image.open(BytesIO(part.inline_data.data))

        if hasattr(part, "as_image"):
            try:
                g_img = part.as_image()
                if hasattr(g_img, "data"):
                    logger_utils.log(i18n.get("api_log_receivedImgSdk"))
                    return Image.open(BytesIO(g_img.data))
                if hasattr(g_img, "_pil_image"):  # pylint: disable=protected-access
                    logger_utils.log(i18n.get("api_log_receivedImgSdk"))
                    return g_img._pil_image  # pylint: disable=protected-access
            except Exception:  # pylint: disable=broad-exception-caught
                pass

        if hasattr(part, 'text') and part.text:
            raise ValueError(i18n.get("api_error_textResponse", text=part.text))

    raise ValueError(i18n.get("api_error_noValidImage"))


def call_google_genai(
        prompt: Optional[str],
        image_paths: List[str],
        api_key: str,
        model_id: str,
        aspect_ratio: str,
        resolution: str,
        max_retries: int = 3
) -> Image.Image | None:
    """Calls Google GenAI Image Generation API."""
    if not api_key:
        msg = i18n.get("api_error_apiKey")
        logger_utils.log(msg)
        return None

    if not model_id:
        model_id = MODEL_SELECTOR_DEFAULT

    client = genai.Client(api_key=api_key)
    contents: List[Any] = []
    if prompt:
        contents.append(prompt)
        
    if image_paths:
        logger_utils.log(i18n.get("api_log_loadingImgs", count=len(image_paths)))
        for path in image_paths:
            try:
                img = Image.open(path)
                contents.append(f"Reference Image Filename: {os.path.basename(path)}")
                contents.append(img)
            except (IOError, OSError) as e:
                logger_utils.log(i18n.get("api_log_skipImg", path=path, err=e))

    ar_log_val = i18n.get(aspect_ratio, aspect_ratio)
    prompt_len = len(prompt) if prompt else 0
    logger_utils.log(i18n.get("api_log_requestInfo", prompt_len=prompt_len, img_count=len(image_paths)))
    logger_utils.log(i18n.get("api_log_requestSent", model=model_id, ar=ar_log_val, res=resolution))

    config = _get_model_config(model_id, aspect_ratio, resolution)

    last_exception: Optional[Exception] = None

    for attempt in range(max_retries):
        try:
            if attempt > 0:
                logger_utils.log(i18n.get("api_log_networkRetry", attempt=attempt + 1, max_retries=max_retries))

            response = client.models.generate_content(
                model=model_id,
                contents=contents,
                config=config
            )

            if hasattr(response, "usage_metadata") and response.usage_metadata:
                u = response.usage_metadata
                logger_utils.log(i18n.get("api_log_tokenUsage", input=getattr(u, "prompt_token_count", 0),
                                          output=getattr(u, "candidates_token_count", 0),
                                          total=getattr(u, "total_token_count", 0)))
                db.add_token_usage(model_id, getattr(u, "prompt_token_count", 0), getattr(u, "candidates_token_count", 0))

            if not response.parts:
                if response.candidates and response.candidates[0]:
                    first_candidate = response.candidates[0]
                    finish_reason = first_candidate.finish_reason.value
                    logger_utils.log(i18n.get("api_log_gemini_api_error", reason=finish_reason))
                    raise ValueError(f"Request was blocked due to: {finish_reason}")
                if response.prompt_feedback and response.prompt_feedback.block_reason:
                    reason = response.prompt_feedback.block_reason.name
                    logger_utils.log(i18n.get("api_log_gemini_api_error", reason=reason))
                    raise ValueError(f"Request was blocked due to: {reason}")
                raise ValueError(i18n.get("api_error_noParts"))

            return _process_response_parts(response.parts)

        except Exception as e:  # pylint: disable=broad-exception-caught
            last_exception = e
            if "401" in str(e) or "403" in str(e):
                break
            time.sleep(2 * (attempt + 1))
            continue

    sys_err_msg = i18n.get("api_error_system", err=str(last_exception))
    logger_utils.log(sys_err_msg)
    return None


def call_google_chat(
        genai_client: genai.Client,
        chat_session: Optional[Chat],
        prompt_parts: List[Any],
        model_id: str,
        aspect_ratio: str,
        resolution: str,
        max_retries: int = 3
) -> Optional[tuple[Chat, List[Any]]]:
    """Calls Google GenAI Chat API."""
    if genai_client is None:
        msg = i18n.get("api_error_apiKey")
        logger_utils.log(msg)
        return None

    if not model_id:
        model_id = "gemini-1.5-pro-image-preview"

    if chat_session is None:
        logger_utils.log("✨ Creating new chat session.")
        chat_session = genai_client.chats.create(
            model=model_id,
            config=types.GenerateContentConfig(
                response_modalities=['TEXT', 'IMAGE']
            )
        )

    image_config_dict: Dict[str, Any] = {}
    is_flash_model = "2.5" in model_id or "flash" in model_id

    if not is_flash_model:
        if aspect_ratio and aspect_ratio != "ar_none":
            image_config_dict["aspect_ratio"] = aspect_ratio
        if resolution:
            image_config_dict["image_size"] = resolution
    else:
        logger_utils.log(i18n.get("api_log_gemini25"))

    gen_config = types.GenerateContentConfig(
        image_config=types.ImageConfig(**image_config_dict) if image_config_dict else None
    )

    ar_log_val = i18n.get(aspect_ratio, aspect_ratio)
    logger_utils.log(f"💬 Sending message to chat | Model: {model_id} | AR: {ar_log_val} | Res: {resolution}")

    last_exception: Optional[Exception] = None

    for attempt in range(max_retries):
        try:
            if attempt > 0:
                logger_utils.log(i18n.get("api_log_networkRetry", attempt=attempt + 1, max_retries=max_retries))

            response = chat_session.send_message(
                prompt_parts,
                config=gen_config
            )

            if hasattr(response, "usage_metadata") and response.usage_metadata:
                u = response.usage_metadata
                logger_utils.log(i18n.get("api_log_tokenUsage", input=u.prompt_token_count,
                                          output=u.candidates_token_count,
                                          total=u.total_token_count))
                db.add_token_usage(model_id, u.prompt_token_count, u.candidates_token_count)

            if not response.parts:
                if response.prompt_feedback and response.prompt_feedback.block_reason:
                    reason = response.prompt_feedback.block_reason.name
                    raise ValueError(f"Request was blocked due to: {reason}")
                raise ValueError(i18n.get("api_error_noParts"))

            response_parts_list: List[Any] = []
            for part in response.parts:
                if part.text is not None:
                    response_parts_list.append(part.text)
                elif image := part.as_image():
                    response_parts_list.append(image)

            if not response_parts_list:
                raise ValueError(i18n.get("api_error_noValidImage"))

            logger_utils.log(f"✅ Received {len(response_parts_list)} parts from chat.")
            return chat_session, response_parts_list

        except Exception as e:  # pylint: disable=broad-exception-caught
            last_exception = e
            if "401" in str(e) or "403" in str(e) or "client has been closed" in str(e):
                break
            time.sleep(2 * (attempt + 1))
            continue

    sys_err_msg = i18n.get("api_error_system", err=str(last_exception))
    logger_utils.log(sys_err_msg)
    return None


def refine_prompt(
        user_prompt: str,
        api_key: str,
        model_id: str,
        task_type: str = "cosplay_photo",
        image_paths: Optional[List[str]] = None
) -> str:
    """Uses Google GenAI to refine and expand a simple image generation prompt."""
    logger_utils.log(i18n.get("logic_log_refiningPrompt", task=task_type))
    
    if not api_key:
        raise ValueError(i18n.get("api_error_apiKey"))

    # Try to get instruction from database first
    db_task = db.get_refine_task(task_type)
    if db_task:
        system_instruction = db_task["system_instruction"]
    else:
        task_config = REFINE_TASKS.get(task_type, REFINE_TASKS["cosplay_photo"])
        system_instruction = task_config["system_instruction"]

    client = genai.Client(api_key=api_key)
    contents = [system_instruction]
    
    if image_paths:
        logger_utils.log(i18n.get("logic_log_refineIncludeImgs", count=len(image_paths)))
        for path in image_paths:
            try:
                img = Image.open(path)
                contents.append(f"Reference Image Filename: {os.path.basename(path)}")
                contents.append(img)
            except Exception as e:
                logger_utils.log(f"Failed to load image for refinement: {path}, error: {e}")

    contents.append(f"User Idea: {user_prompt}")

    try:
        response = client.models.generate_content(
            model=model_id,
            contents=contents,
            config=types.GenerateContentConfig(
                response_modalities=["TEXT"]
            )
        )
        
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            u = response.usage_metadata
            db.add_token_usage(model_id, getattr(u, "prompt_token_count", 0), getattr(u, "candidates_token_count", 0))

        if not response.parts:
            # Check for block reason in prompt_feedback
            if response.prompt_feedback and response.prompt_feedback.block_reason:
                reason = response.prompt_feedback.block_reason.name
                logger_utils.log(i18n.get("api_log_gemini_api_error", reason=reason))
                raise ValueError(f"Refinement was blocked due to: {reason}")
            
            # Check for finish reason in candidates
            if response.candidates and response.candidates[0]:
                first_candidate = response.candidates[0]
                if first_candidate.finish_reason:
                    finish_reason = first_candidate.finish_reason.value
                    logger_utils.log(i18n.get("api_log_gemini_api_error", reason=finish_reason))
                    raise ValueError(f"Refinement was blocked due to: {finish_reason}")
            
            raise ValueError("API returned no parts and no specific block reason.")

        # Access response.text safely
        if hasattr(response, "text") and response.text:
            logger_utils.log(i18n.get("logic_log_refineSuccess"))
            return response.text.strip()
        
        # Fallback: check parts
        if response.candidates and response.candidates[0].content.parts:
            text_parts = [p.text for p in response.candidates[0].content.parts if p.text]
            if text_parts:
                logger_utils.log(i18n.get("logic_log_refineSuccessParts"))
                return "".join(text_parts).strip()
                
        raise ValueError("API returned empty text during refinement.")
            
    except Exception as e:
        logger_utils.log(i18n.get("logic_log_refineFail", err=str(e)))
        raise e
