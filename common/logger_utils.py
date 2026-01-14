import datetime
from typing import Callable, List

# 全局日志缓存
_LOG_BUFFER = []
# 回调函数列表，用于通知 UI 更新
_callbacks: List[Callable[[str], None]] = []


def subscribe(callback: Callable[[str], None]):
    """订阅日志更新"""
    if callback not in _callbacks:
        _callbacks.append(callback)


def unsubscribe(callback: Callable[[str], None]):
    """取消订阅"""
    if callback in _callbacks:
        _callbacks.remove(callback)


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

    # 5. 通知所有订阅者
    all_logs = get_logs()
    for callback in _callbacks:
        try:
            callback(all_logs)
        except Exception as e:
            print(f"Error in log callback: {e}")


def get_logs():
    """获取所有日志文本，用于 UI 显示"""
    # 倒序排列，最新的在最上面
    return "\n".join(reversed(_LOG_BUFFER))


def clear_logs():
    """清空日志"""
    _LOG_BUFFER.clear()
    # 通知订阅者日志已清空
    for callback in _callbacks:
        callback("")
    return ""
