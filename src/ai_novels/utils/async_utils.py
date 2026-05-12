"""
异步工具模块

@file: utils/async_utils.py
@date: 2026-04-08
@version: 1.0.0
@description: 异步编程工具函数
"""

import asyncio
import functools
from typing import Any, Callable, List, Optional, TypeVar, Coroutine
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

T = TypeVar('T')


class AsyncTaskManager:
    """异步任务管理器"""
    
    def __init__(self, max_workers: int = 10):
        self.max_workers = max_workers
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._tasks: List[asyncio.Task] = []
    
    async def run_in_executor(
        self,
        func: Callable[..., T],
        *args,
        **kwargs
    ) -> T:
        """
        在线程池中运行同步函数
        
        Args:
            func: 同步函数
            *args: 位置参数
            **kwargs: 关键字参数
            
        Returns:
            函数返回值
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self._executor,
            functools.partial(func, *args, **kwargs)
        )
    
    async def gather_with_concurrency(
        self,
        coroutines: List[Coroutine],
        limit: int = None
    ) -> List[Any]:
        """
        限制并发数的gather
        
        Args:
            coroutines: 协程列表
            limit: 并发限制
            
        Returns:
            结果列表
        """
        limit = limit or self.max_workers
        semaphore = asyncio.Semaphore(limit)
        
        async def sem_coro(coro):
            async with semaphore:
                return await coro
        
        return await asyncio.gather(*[sem_coro(c) for c in coroutines])
    
    async def run_with_timeout(
        self,
        coro: Coroutine,
        timeout: float,
        default: Any = None
    ) -> Any:
        """
        带超时的运行
        
        Args:
            coro: 协程
            timeout: 超时时间（秒）
            default: 超时默认值
            
        Returns:
            结果或默认值
        """
        try:
            return await asyncio.wait_for(coro, timeout=timeout)
        except asyncio.TimeoutError:
            return default
    
    def shutdown(self):
        """关闭执行器"""
        self._executor.shutdown(wait=True)


def async_retry(
    max_retries: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,)
):
    """
    异步重试装饰器
    
    Args:
        max_retries: 最大重试次数
        delay: 初始延迟
        backoff: 退避系数
        exceptions: 捕获的异常类型
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            current_delay = delay
            
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    if attempt == max_retries:
                        raise
                    
                    await asyncio.sleep(current_delay)
                    current_delay *= backoff
            
            return None
        
        return wrapper
    return decorator


def sync_to_async(func: Callable) -> Callable:
    """
    将同步函数转换为异步函数
    
    Args:
        func: 同步函数
        
    Returns:
        异步函数
    """
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, functools.partial(func, *args, **kwargs))
    
    return wrapper


class RateLimiter:
    """异步限流器"""
    
    def __init__(self, rate: float = 10.0):
        """
        初始化
        
        Args:
            rate: 每秒请求数
        """
        self.rate = rate
        self.min_interval = 1.0 / rate
        self.last_request_time = 0
        self._lock = asyncio.Lock()
    
    async def acquire(self):
        """获取许可"""
        async with self._lock:
            now = time.time()
            elapsed = now - self.last_request_time
            
            if elapsed < self.min_interval:
                await asyncio.sleep(self.min_interval - elapsed)
            
            self.last_request_time = time.time()


class CircuitBreaker:
    """熔断器"""
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        expected_exception: type = Exception
    ):
        """
        初始化
        
        Args:
            failure_threshold: 失败阈值
            recovery_timeout: 恢复超时
            expected_exception: 预期异常类型
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        
        self._failure_count = 0
        self._last_failure_time = None
        self._state = "closed"  # closed, open, half-open
        self._lock = asyncio.Lock()
    
    async def call(self, func: Callable, *args, **kwargs):
        """
        调用函数
        
        Args:
            func: 函数
            *args: 位置参数
            **kwargs: 关键字参数
            
        Returns:
            函数返回值
        """
        async with self._lock:
            if self._state == "open":
                if time.time() - self._last_failure_time > self.recovery_timeout:
                    self._state = "half-open"
                    self._failure_count = 0
                else:
                    raise Exception("Circuit breaker is open")
        
        try:
            result = await func(*args, **kwargs)
            
            async with self._lock:
                if self._state == "half-open":
                    self._state = "closed"
                self._failure_count = 0
            
            return result
            
        except self.expected_exception as e:
            async with self._lock:
                self._failure_count += 1
                self._last_failure_time = time.time()
                
                if self._failure_count >= self.failure_threshold:
                    self._state = "open"
            
            raise


# 便捷函数
async def sleep(seconds: float):
    """异步睡眠"""
    await asyncio.sleep(seconds)


async def gather(*coroutines, return_exceptions: bool = False):
    """并发执行多个协程"""
    return await asyncio.gather(*coroutines, return_exceptions=return_exceptions)


def create_task(coro) -> asyncio.Task:
    """创建后台任务"""
    return asyncio.create_task(coro)


async def wait_for(coro, timeout: float):
    """等待协程完成（带超时）"""
    return await asyncio.wait_for(coro, timeout=timeout)
