import datetime

# 全局日志缓存
_LOG_BUFFER = []


def log(message):
    """
    记录日志：同时打印到控制台和添加到缓存
    """
    # 1. 生成时间戳
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    formatted_msg = f"[{timestamp}] {message}"

    # 2. 打印到控制台 (保留原有的终端输出)
    print(formatted_msg)

    # 3. 添加到内存缓存
    _LOG_BUFFER.append(formatted_msg)

    # 4. 限制长度 (防止无限增长，保留最近 500 行)
    if len(_LOG_BUFFER) > 500:
        _LOG_BUFFER.pop(0)


def get_logs():
    """获取所有日志文本，用于 UI 显示"""
    # 倒序排列，最新的在最上面
    return "\n".join(reversed(_LOG_BUFFER))


def clear_logs():
    """清空日志"""
    _LOG_BUFFER.clear()
    return ""

# # 移除自动注册
# ticker_instance.register(get_logs)
