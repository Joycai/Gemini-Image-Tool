from PIL import Image

from common import logger_utils
from common.config import AR_SELECTOR_CHOICES

def get_image_details(image_path: str) -> str:
    """
    Gets the closest aspect ratio and resolution for an image.
    """
    try:
        with Image.open(image_path) as img:
            width, height = img.size
    except Exception as e:
        logger_utils.log(f"Error opening image {image_path}: {e}")
        return "Unknown"

    # Resolution
    max_dim = max(width, height)
    if 1024 <= max_dim < 2048:
        res_text = "1K"
    elif 2048 <= max_dim < 4096:
        res_text = "2K"
    elif max_dim >= 4096:
        res_text = "4K"
    else:
        res_text = f"{height}p"

    # Aspect Ratio
    if height == 0:
        return f"{res_text} / ?"

    image_ar = width / height

    best_ar_choice = ""
    min_diff = float('inf')

    for ar_choice in AR_SELECTOR_CHOICES:
        if ar_choice == "ar_none":
            continue

        try:
            ar_parts = ar_choice.split(':')
            ar_value = int(ar_parts[0]) / int(ar_parts[1])

            diff = abs(image_ar - ar_value)

            if diff < min_diff:
                min_diff = diff
                best_ar_choice = ar_choice
        except (ValueError, ZeroDivisionError):
            continue

    return f"{res_text} / {best_ar_choice}"
