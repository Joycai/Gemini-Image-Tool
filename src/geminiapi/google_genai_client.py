import os
import time
from io import BytesIO
from typing import List, Any, Optional, Dict

from PIL import Image
from google import genai
from google.genai import types
from google.genai.chats import Chat
from google.genai.errors import ClientError
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


def _build_contents(
        prompt: Optional[str] = None,
        image_paths: Optional[List[str]] = None,
        system_instruction: Optional[str] = None
) -> List[Any]:
    """Builds the contents list for GenAI API calls."""
    contents: List[Any] = []
    
    if system_instruction:
        contents.append(system_instruction)
        
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
                
    return contents


def _execute_genai_call(
        call_func,
        model_id: str,
        max_retries: int = 3,
        *args,
        **kwargs
) -> Any:
    """Executes a GenAI API call with retries and common error/response handling."""
    last_exception: Optional[Exception] = None

    for attempt in range(max_retries):
        try:
            if attempt > 0:
                logger_utils.log(i18n.get("api_log_networkRetry", attempt=attempt + 1, max_retries=max_retries))

            response = call_func(*args, **kwargs)

            # Log token usage
            if hasattr(response, "usage_metadata") and response.usage_metadata:
                u = response.usage_metadata
                p_tokens = getattr(u, "prompt_token_count", 0)
                c_tokens = getattr(u, "candidates_token_count", 0)
                t_tokens = getattr(u, "total_token_count", 0)
                logger_utils.log(i18n.get("api_log_tokenUsage", input=p_tokens, output=c_tokens, total=t_tokens))
                db.add_token_usage(model_id, p_tokens, c_tokens)

            # Check for blocked content or empty parts
            if not response.parts:
                if hasattr(response, "candidates") and response.candidates and response.candidates[0]:
                    cand = response.candidates[0]
                    if hasattr(cand, "finish_reason") and cand.finish_reason:
                        reason = cand.finish_reason.name if hasattr(cand.finish_reason, "name") else str(cand.finish_reason)
                        logger_utils.log(i18n.get("api_log_gemini_api_error", reason=reason))
                        raise ValueError(f"Request was blocked due to: {reason}")
                
                if hasattr(response, "prompt_feedback") and response.prompt_feedback and response.prompt_feedback.block_reason:
                    reason = response.prompt_feedback.block_reason.name
                    logger_utils.log(i18n.get("api_log_gemini_api_error", reason=reason))
                    raise ValueError(f"Request was blocked due to: {reason}")
                
                raise ValueError(i18n.get("api_error_noParts"))

            return response

        except Exception as e:
            last_exception = e
            err_str = str(e)
            
            # Non-retryable errors
            if any(code in err_str for code in ["401", "403"]) or "client has been closed" in err_str:
                break
                
            if isinstance(e, ClientError):
                try:
                    details = e.details["error"]
                    last_exception = ValueError(f"Gemini API error: {details['code']} - {details['status']} \n{details['message']}")
                except (KeyError, TypeError):
                    pass
                break
            
            if attempt < max_retries - 1:
                time.sleep(2 * (attempt + 1))
            else:
                break

    raise last_exception


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
    contents = _build_contents(prompt=prompt, image_paths=image_paths)

    ar_log_val = i18n.get(aspect_ratio, aspect_ratio)
    prompt_len = len(prompt) if prompt else 0
    logger_utils.log(i18n.get("api_log_requestInfo", prompt_len=prompt_len, img_count=len(image_paths)))
    logger_utils.log(i18n.get("api_log_requestSent", model=model_id, ar=ar_log_val, res=resolution))

    config = _get_model_config(model_id, aspect_ratio, resolution)

    try:
        response = _execute_genai_call(
            client.models.generate_content,
            model_id,
            max_retries,
            model=model_id,
            contents=contents,
            config=config
        )
        return _process_response_parts(response.parts)
    except Exception as e:
        sys_err_msg = i18n.get("api_error_system", err=str(e))
        logger_utils.log(sys_err_msg)
        return None


def call_google_chat(
        api_key: str,
        chat_session: Optional[Chat],
        prompt_parts: List[Any],
        model_id: str,
        aspect_ratio: str,
        resolution: str,
        max_retries: int = 3
) -> Optional[tuple[Chat, List[Any]]]:
    """Calls Google GenAI Chat API."""
    if not api_key:
        msg = i18n.get("api_error_apiKey")
        logger_utils.log(msg)
        return None

    if not model_id:
        model_id = "gemini-1.5-pro-image-preview"

    # Use existing client from session if available to prevent "client has been closed"
    if chat_session and hasattr(chat_session, "_persistent_client"):
        genai_client = chat_session._persistent_client
    else:
        genai_client = genai.Client(api_key=api_key)

    if chat_session is None:
        logger_utils.log(i18n.get("api_log_creatingChatSession"))
        chat_session = genai_client.chats.create(
            model=model_id,
            config=types.GenerateContentConfig(
                response_modalities=['TEXT', 'IMAGE']
            )
        )
        # Monkey-patch the session to keep the client alive
        chat_session._persistent_client = genai_client

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
    logger_utils.log(i18n.get("api_log_chatRequestSent", model=model_id, ar=ar_log_val, res=resolution))

    try:
        response = _execute_genai_call(
            chat_session.send_message,
            model_id,
            max_retries,
            prompt_parts,
            config=gen_config
        )

        response_parts_list: List[Any] = []
        for part in response.parts:
            if part.text is not None:
                response_parts_list.append(part.text)
            elif image := part.as_image():
                response_parts_list.append(image)

        if not response_parts_list:
            raise ValueError(i18n.get("api_error_noValidImage"))

        logger_utils.log(i18n.get("api_log_chatReceivedParts", count=len(response_parts_list)))
        return chat_session, response_parts_list

    except Exception as e:
        sys_err_msg = i18n.get("api_error_system", err=str(e))
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
    contents = _build_contents(
        prompt=f"User Idea: {user_prompt}",
        image_paths=image_paths,
        system_instruction=system_instruction
    )

    try:
        response = _execute_genai_call(
            client.models.generate_content,
            model_id,
            3,
            model=model_id,
            contents=contents,
            config=types.GenerateContentConfig(response_modalities=["TEXT"])
        )
        
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
                
        raise ValueError(i18n.get("api_error_noParts"))

    except Exception as e:
        logger_utils.log(i18n.get("logic_log_refineFail", err=str(e)))
        raise e
