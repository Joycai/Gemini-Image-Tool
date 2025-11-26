from typing import Callable, List, Tuple, Any
import gradio as gr

class Ticker:
    """
    一个用于管理和执行周期性回调函数的类。
    """
    def __init__(self):
        self._callbacks: List[Callable[[], Any]] = []

    def register(self, func: Callable[[], Any]):
        """
        注册一个回调函数，该函数将在每个 tick 中被执行。
        
        Args:
            func: 一个无参数的函数。其返回值将被收集。
        """
        self._callbacks.append(func)

    def tick(self) -> Tuple[Any, ...]:
        """
        执行所有已注册的回调函数并收集它们的返回值。
        
        此方法旨在由 gr.Timer.tick() 调用。
        
        Returns:
            一个包含所有回调函数返回值的元组。
            如果回调函数返回的是元组，其元素会被展开并合并到主元组中。
        """
        all_results = []
        for func in self._callbacks:
            try:
                result = func()
                # 如果返回的是 gr.skip()，直接添加
                if isinstance(result, type(gr.skip())):
                    all_results.append(result)
                # 如果返回的是元组，则展开它
                elif isinstance(result, tuple):
                    all_results.extend(result)
                # 否则，直接添加单个返回值
                else:
                    all_results.append(result)
            except Exception as e:
                print(f"Error executing callback {func.__name__}: {e}")
                # 发生异常时，根据回调函数的预期返回数量，填充 gr.skip()
                # 这是一个简化的处理，实际应用中可能需要更复杂的逻辑
                # 但对于目前的需求是足够的
                # 我们假设 poll_task_status 返回2个值，get_logs 返回1个值
                if 'poll_task_status' in func.__name__:
                    all_results.extend([gr.skip(), gr.skip()])
                elif 'get_logs' in func.__name__:
                    all_results.append(gr.skip())
        
        return tuple(all_results)

# 创建一个全局单例
ticker_instance = Ticker()
