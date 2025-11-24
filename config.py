import platform
import os

# ==============================================================
# 路径配置
# ==============================================================
TEMP_DIR = "tmp"
UPLOAD_DIR = os.path.join(TEMP_DIR, "upload")
OUTPUT_DIR = os.path.join(TEMP_DIR, "output")

# ==============================================================
# 图像文件扩展名
# ==============================================================
VALID_IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp', '.bmp'}

# ==============================================================
# Gradio `launch` 函数的 `allowed_paths`
# ==============================================================
def get_allowed_paths():
    """
    根据操作系统生成 Gradio `launch` 函数的 `allowed_paths` 列表。
    """
    allowed_paths = []
    if platform.system() == "Windows":
        # 允许所有驱动器号
        for char in range(ord('A'), ord('Z') + 1):
            allowed_paths.append(f"{chr(char)}:\\")
        # 添加常见的网络驱动器路径
        nas_paths = ["\\\\DS720plus\\home", "\\\\192.168.1.1\\share"]
        allowed_paths.extend(nas_paths)
    else:
        # 对于 Linux 和 macOS，允许常见的挂载点
        allowed_paths = ["/", "/mnt", "/media", "/home"]
    return allowed_paths

# ==============================================================
# UI 组件的配置
# ==============================================================

# 模型选择器
MODEL_SELECTOR_CHOICES = ["gemini-2.5-flash-image", "gemini-3-pro-image-preview"]
MODEL_SELECTOR_DEFAULT = "gemini-3-pro-image-preview"

# 宽高比选择器
AR_SELECTOR_CHOICES = ["1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9"]
AR_SELECTOR_DEFAULT = "1:1"

# 分辨率选择器
RES_SELECTOR_CHOICES = ["1K", "2K", "4K"]
RES_SELECTOR_DEFAULT = "2K"
