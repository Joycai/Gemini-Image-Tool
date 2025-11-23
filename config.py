import platform

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
