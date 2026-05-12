"""
时间处理工具函数

@file: utils/time_utils.py
@date: 2026-03-13
@version: 1.0.0
@description: 时间处理和定时任务相关函数
"""

import time
import threading
from datetime import datetime, timedelta
from typing import Callable, Any, Optional
from functools import wraps


def get_timestamp_ms() -> int:
    """
    获取毫秒时间戳

    Returns:
        毫秒时间戳
    """
    return int(time.time() * 1000)


def get_timestamp_s() -> int:
    """
    获取秒级时间戳

    Returns:
        秒级时间戳
    """
    return int(time.time())


def format_timestamp_ms(timestamp_ms: int, fmt: str = '%Y-%m-%d %H:%M:%S') -> str:
    """
    格式化毫秒时间戳

    Args:
        timestamp_ms: 毫秒时间戳
        fmt: 格式字符串

    Returns:
        格式化后的时间字符串
    """
    dt = datetime.fromtimestamp(timestamp_ms / 1000)
    return dt.strftime(fmt)


def format_timestamp_s(timestamp_s: int, fmt: str = '%Y-%m-%d %H:%M:%S') -> str:
    """
    格式化秒级时间戳

    Args:
        timestamp_s: 秒级时间戳
        fmt: 格式字符串

    Returns:
        格式化后的时间字符串
    """
    dt = datetime.fromtimestamp(timestamp_s)
    return dt.strftime(fmt)


def parse_iso_datetime(iso_str: str) -> datetime:
    """
    解析ISO格式时间字符串

    Args:
        iso_str: ISO格式时间字符串

    Returns:
        datetime对象
    """
    # 处理带毫秒的格式
    if '.' in iso_str:
        iso_str = iso_str.split('.')[0]
    return datetime.fromisoformat(iso_str)


def calculate_duration(start_time: float, end_time: float) -> float:
    """
    计算持续时间（秒）

    Args:
        start_time: 开始时间戳
        end_time: 结束时间戳

    Returns:
        持续时间（秒）
    """
    return end_time - start_time


def calculate_duration_ms(start_time: float, end_time: float) -> float:
    """
    计算持续时间（毫秒）

    Args:
        start_time: 开始时间戳
        end_time: 结束时间戳

    Returns:
        持续时间（毫秒）
    """
    return (end_time - start_time) * 1000


# 紧张度计算 - 基于章节位置
def calculate_tension_level(chapter_index: int, total_chapters: int) -> int:
    """
    计算章节紧张度

    Args:
        chapter_index: 章节序号（从1开始）
        total_chapters: 总章节数

    Returns:
        1-10的紧张度
    """
    if total_chapters <= 0:
        return 5

    # 归一化章节位置
    position = chapter_index / total_chapters

    # 三幕结构紧张度分配
    # 第一幕（引入）：1-3 -> 3-5
    # 第二幕（发展）：4-7 -> 5-8
    # 第三幕（高潮）：8-10 -> 8-10

    if position <= 0.3:
        # 第一幕：较低紧张度
        base_tension = 3 + (position / 0.3) * 2
    elif position <= 0.7:
        # 第二幕：中等紧张度
        base_tension = 5 + ((position - 0.3) / 0.4) * 3
    else:
        # 第三幕：高紧张度
        base_tension = 8 + ((position - 0.7) / 0.3) * 2

    return min(10, max(1, int(base_tension)))


# 重试装饰器
def retry_on_failure(max_retries: int = 3, delay: float = 1.0, backoff: float = 2.0):
    """
    重试装饰器

    Args:
        max_retries: 最大重试次数
        delay: 基础延迟（秒）
        backoff: 延迟增长系数

    Returns:
        装饰器函数
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            current_delay = delay

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries:
                        time.sleep(current_delay)
                        current_delay *= backoff

            raise last_exception

        return wrapper
    return decorator


# 执行时间日志装饰器
def log_execution_time(func: Callable = None, *, level: str = 'info') -> Callable:
    """
    函数执行时间日志装饰器

    Args:
        func: 被装饰的函数
        level: 日志级别

    Returns:
        装饰器函数
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = f(*args, **kwargs)
                return result
            finally:
                elapsed = time.time() - start_time
                print(f"[{level.upper()}] {f.__name__} took {elapsed * 1000:.2f}ms")
        return wrapper
    return decorator(func) if func else decorator


# 延迟执行函数
def schedule_execution(func: Callable, delay_seconds: float, *args, **kwargs) -> threading.Timer:
    """
    安排函数延迟执行

    Args:
        func: 要执行的函数
        delay_seconds: 延迟秒数
        *args: 函数参数
        **kwargs: 函数关键字参数

    Returns:
        Timer对象
    """
    timer = threading.Timer(delay_seconds, func, args=args, kwargs=kwargs)
    timer.start()
    return timer


# 定期执行函数
class ScheduledTask:
    """定期执行任务"""

    def __init__(self, interval: float, func: Callable, *args, **kwargs):
        """
        初始化定时任务

        Args:
            interval: 执行间隔（秒）
            func: 要执行的函数
            *args: 函数参数
            **kwargs: 函数关键字参数
        """
        self.interval = interval
        self.func = func
        self.args = args
        self.kwargs = kwargs
        self._running = False
        self._timer: Optional[threading.Timer] = None
        self._last_executed: Optional[float] = None
        self._execution_count = 0

    def _run(self):
        """运行任务"""
        if not self._running:
            return

        try:
            self.func(*self.args, **self.kwargs)
            self._execution_count += 1
            self._last_executed = time.time()
        except Exception:
            pass

        if self._running:
            self._timer = threading.Timer(self.interval, self._run)
            self._timer.start()

    def start(self):
        """开始执行"""
        if not self._running:
            self._running = True
            self._timer = threading.Timer(self.interval, self._run)
            self._timer.start()

    def stop(self):
        """停止执行"""
        self._running = False
        if self._timer:
            self._timer.cancel()
            self._timer = None

    def is_running(self) -> bool:
        """检查是否正在运行"""
        return self._running

    def get_execution_count(self) -> int:
        """获取执行次数"""
        return self._execution_count

    def get_last_executed(self) -> Optional[float]:
        """获取最后执行时间戳"""
        return self._last_executed


# 任务超时管理
class TimeoutManager:
    """任务超时管理器"""

    def __init__(self):
        self._timeouts: dict = {}
        self._start_times: dict = {}

    def start_timer(self, task_id: str, timeout_seconds: float):
        """
        开始计时

        Args:
            task_id: 任务ID
            timeout_seconds: 超时秒数
        """
        self._start_times[task_id] = time.time()
        self._timeouts[task_id] = timeout_seconds

    def check_timeout(self, task_id: str) -> bool:
        """
        检查是否超时

        Args:
            task_id: 任务ID

        Returns:
            是否超时
        """
        if task_id not in self._start_times:
            return False

        elapsed = time.time() - self._start_times[task_id]
        return elapsed > self._timeouts.get(task_id, float('inf'))

    def get_remaining_time(self, task_id: str) -> float:
        """
        获取剩余时间

        Args:
            task_id: 任务ID

        Returns:
            剩余秒数，负数表示已超时
        """
        if task_id not in self._start_times:
            return 0

        elapsed = time.time() - self._start_times[task_id]
        timeout = self._timeouts.get(task_id, float('inf'))
        return timeout - elapsed

    def clear_timer(self, task_id: str):
        """
        清除计时器

        Args:
            task_id: 任务ID
        """
        if task_id in self._start_times:
            del self._start_times[task_id]
        if task_id in self._timeouts:
            del self._timeouts[task_id]


# 时间范围检查
def is_within_time_range(start_hour: int, end_hour: int) -> bool:
    """
    检查当前时间是否在范围内

    Args:
        start_hour: 开始小时
        end_hour: 结束小时

    Returns:
        是否在范围内
    """
    current_hour = datetime.now().hour
    if start_hour <= end_hour:
        return start_hour <= current_hour < end_hour
    else:
        # 跨天情况
        return current_hour >= start_hour or current_hour < end_hour


# 时间格式化工具
def format_duration(seconds: float) -> str:
    """
    格式化持续时间

    Args:
        seconds: 秒数

    Returns:
        格式化后的字符串
    """
    if seconds < 60:
        return f"{seconds:.1f}秒"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        remaining = seconds % 60
        return f"{minutes}分{remaining:.1f}秒"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return f"{hours}小时{minutes}分"


def get_next_occurrence(hour: int, minute: int = 0) -> datetime:
    """
    获取下次 occurrence 时间

    Args:
        hour: 小时
        minute: 分钟

    Returns:
        datetime对象
    """
    now = datetime.now()
    next_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

    if next_time <= now:
        next_time += timedelta(days=1)

    return next_time


if __name__ == "__main__":
    # 示例用法
    print("Time utils module loaded successfully!")

    # 测试时间戳
    print(f"Timestamp (ms): {get_timestamp_ms()}")
    print(f"Timestamp (s): {get_timestamp_s()}")

    # 测试紧张度计算
    for chapter in [1, 10, 20, 30, 40, 50]:
        tension = calculate_tension_level(chapter, 50)
        print(f"Chapter {chapter}: tension level {tension}")
