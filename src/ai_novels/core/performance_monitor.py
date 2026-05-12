"""
性能监控模块

@file: core/performance_monitor.py
@date: 2026-04-08
@version: 1.0.0
@description: 性能监控、指标收集和优化建议
"""

import time
import functools
import threading
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass, field
from collections import defaultdict, deque
from contextlib import contextmanager
from enum import Enum

from ai_novels.utils import log_info, log_warn, log_error, get_logger


class MetricType(Enum):
    """指标类型"""
    COUNTER = "counter"      # 计数器
    GAUGE = "gauge"          # 仪表盘（瞬时值）
    HISTOGRAM = "histogram"  # 直方图
    TIMER = "timer"          # 计时器


@dataclass
class MetricValue:
    """指标值"""
    name: str
    value: float
    metric_type: MetricType
    timestamp: float = field(default_factory=time.time)
    labels: Dict[str, str] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "value": self.value,
            "type": self.metric_type.value,
            "timestamp": self.timestamp,
            "labels": self.labels
        }


@dataclass
class PerformanceSnapshot:
    """性能快照"""
    timestamp: float
    metrics: Dict[str, List[MetricValue]]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "metrics": {
                name: [m.to_dict() for m in values]
                for name, values in self.metrics.items()
            }
        }


class PerformanceMonitor:
    """
    性能监控器
    
    收集和管理性能指标，提供实时监控和历史分析
    """
    
    _instance: Optional['PerformanceMonitor'] = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, '_initialized'):
            return
        
        self._initialized = True
        self._metrics: Dict[str, List[MetricValue]] = defaultdict(list)
        self._counters: Dict[str, int] = defaultdict(int)
        self._gauges: Dict[str, float] = {}
        self._histograms: Dict[str, List[float]] = defaultdict(list)
        self._timers: Dict[str, Dict[str, Any]] = {}
        
        # 历史数据（保留最近1000条）
        self._history: deque = deque(maxlen=1000)
        
        # 告警阈值
        self._thresholds: Dict[str, Dict[str, float]] = {}
        
        # 锁
        self._lock = threading.RLock()
        
        self._logger = get_logger()
    
    def record_counter(self, name: str, value: int = 1, labels: Dict[str, str] = None):
        """
        记录计数器
        
        Args:
            name: 指标名称
            value: 增加值
            labels: 标签
        """
        with self._lock:
            self._counters[name] += value
            metric = MetricValue(
                name=name,
                value=self._counters[name],
                metric_type=MetricType.COUNTER,
                labels=labels or {}
            )
            self._metrics[name].append(metric)
            self._check_threshold(name, metric.value)
    
    def record_gauge(self, name: str, value: float, labels: Dict[str, str] = None):
        """
        记录仪表盘值
        
        Args:
            name: 指标名称
            value: 值
            labels: 标签
        """
        with self._lock:
            self._gauges[name] = value
            metric = MetricValue(
                name=name,
                value=value,
                metric_type=MetricType.GAUGE,
                labels=labels or {}
            )
            self._metrics[name].append(metric)
            self._check_threshold(name, value)
    
    def record_histogram(self, name: str, value: float, labels: Dict[str, str] = None):
        """
        记录直方图值
        
        Args:
            name: 指标名称
            value: 值
            labels: 标签
        """
        with self._lock:
            self._histograms[name].append(value)
            # 只保留最近1000个值
            if len(self._histograms[name]) > 1000:
                self._histograms[name] = self._histograms[name][-1000:]
            
            metric = MetricValue(
                name=name,
                value=value,
                metric_type=MetricType.HISTOGRAM,
                labels=labels or {}
            )
            self._metrics[name].append(metric)
    
    def start_timer(self, name: str, labels: Dict[str, str] = None) -> str:
        """
        开始计时
        
        Args:
            name: 指标名称
            labels: 标签
            
        Returns:
            计时器ID
        """
        timer_id = f"{name}_{time.time()}"
        with self._lock:
            self._timers[timer_id] = {
                "name": name,
                "start_time": time.time(),
                "labels": labels or {}
            }
        return timer_id
    
    def stop_timer(self, timer_id: str) -> Optional[float]:
        """
        停止计时
        
        Args:
            timer_id: 计时器ID
            
        Returns:
            耗时（毫秒），如果计时器不存在返回None
        """
        with self._lock:
            if timer_id not in self._timers:
                return None
            
            timer = self._timers.pop(timer_id)
            duration_ms = (time.time() - timer["start_time"]) * 1000
            
            metric = MetricValue(
                name=timer["name"],
                value=duration_ms,
                metric_type=MetricType.TIMER,
                labels=timer["labels"]
            )
            self._metrics[timer["name"]].append(metric)
            self._check_threshold(timer["name"], duration_ms)
            
            return duration_ms
    
    @contextmanager
    def timed_execution(self, name: str, labels: Dict[str, str] = None):
        """
        上下文管理器：计时执行块
        
        Usage:
            with monitor.timed_execution("db_query"):
                result = db.query()
        """
        timer_id = self.start_timer(name, labels)
        try:
            yield
        finally:
            self.stop_timer(timer_id)
    
    def set_threshold(self, name: str, min_value: float = None, max_value: float = None):
        """
        设置告警阈值
        
        Args:
            name: 指标名称
            min_value: 最小值（低于此值告警）
            max_value: 最大值（高于此值告警）
        """
        with self._lock:
            self._thresholds[name] = {
                "min": min_value,
                "max": max_value
            }
    
    def _check_threshold(self, name: str, value: float):
        """检查阈值并告警"""
        if name not in self._thresholds:
            return
        
        threshold = self._thresholds[name]
        
        if threshold.get("min") is not None and value < threshold["min"]:
            self._logger.performance(f"Metric {name} below threshold: {value} < {threshold['min']}")
        
        if threshold.get("max") is not None and value > threshold["max"]:
            self._logger.performance(f"Metric {name} above threshold: {value} > {threshold['max']}")
    
    def get_metric(self, name: str) -> List[MetricValue]:
        """
        获取指标历史
        
        Args:
            name: 指标名称
            
        Returns:
            指标值列表
        """
        with self._lock:
            return self._metrics.get(name, []).copy()
    
    def get_counter(self, name: str) -> int:
        """获取计数器当前值"""
        with self._lock:
            return self._counters.get(name, 0)
    
    def get_gauge(self, name: str) -> Optional[float]:
        """获取仪表盘当前值"""
        with self._lock:
            return self._gauges.get(name)
    
    def get_histogram_stats(self, name: str) -> Dict[str, float]:
        """
        获取直方图统计信息
        
        Args:
            name: 指标名称
            
        Returns:
            统计信息字典
        """
        with self._lock:
            values = self._histograms.get(name, [])
            if not values:
                return {}
            
            sorted_values = sorted(values)
            n = len(sorted_values)
            
            return {
                "count": n,
                "min": sorted_values[0],
                "max": sorted_values[-1],
                "mean": sum(values) / n,
                "p50": sorted_values[int(n * 0.5)],
                "p90": sorted_values[int(n * 0.9)],
                "p95": sorted_values[int(n * 0.95)],
                "p99": sorted_values[int(n * 0.99)] if n >= 100 else sorted_values[-1]
            }
    
    def get_all_metrics(self) -> Dict[str, Any]:
        """获取所有指标"""
        with self._lock:
            return {
                "counters": dict(self._counters),
                "gauges": dict(self._gauges),
                "histograms": {
                    name: self.get_histogram_stats(name)
                    for name in self._histograms.keys()
                }
            }
    
    def take_snapshot(self) -> PerformanceSnapshot:
        """创建性能快照"""
        with self._lock:
            snapshot = PerformanceSnapshot(
                timestamp=time.time(),
                metrics=dict(self._metrics)
            )
            self._history.append(snapshot)
            return snapshot
    
    def get_history(self) -> List[PerformanceSnapshot]:
        """获取历史快照"""
        with self._lock:
            return list(self._history)
    
    def clear(self):
        """清空所有指标"""
        with self._lock:
            self._metrics.clear()
            self._counters.clear()
            self._gauges.clear()
            self._histograms.clear()
            self._timers.clear()
            self._history.clear()
    
    def generate_report(self) -> Dict[str, Any]:
        """生成性能报告"""
        with self._lock:
            return {
                "timestamp": time.time(),
                "summary": {
                    "total_counters": len(self._counters),
                    "total_gauges": len(self._gauges),
                    "total_histograms": len(self._histograms),
                    "active_timers": len(self._timers)
                },
                "counters": dict(self._counters),
                "gauges": dict(self._gauges),
                "histograms": {
                    name: self.get_histogram_stats(name)
                    for name in self._histograms.keys()
                }
            }


# 全局监控器实例
monitor = PerformanceMonitor()


def get_performance_monitor() -> PerformanceMonitor:
    """获取性能监控器实例"""
    return monitor


def timed(name: str, labels: Dict[str, str] = None):
    """
    装饰器：计时函数执行
    
    Usage:
        @timed("db_query", {"table": "users"})
        def query_users():
            pass
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            timer_id = monitor.start_timer(name, labels)
            try:
                return func(*args, **kwargs)
            finally:
                duration = monitor.stop_timer(timer_id)
                if duration:
                    get_logger().performance_debug(
                        f"Function {func.__name__} executed",
                        duration_ms=duration
                    )
        return wrapper
    return decorator


def count_calls(name: str, labels: Dict[str, str] = None):
    """
    装饰器：统计函数调用次数
    
    Usage:
        @count_calls("api_calls", {"endpoint": "/users"})
        def handle_request():
            pass
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            monitor.record_counter(name, 1, labels)
            return func(*args, **kwargs)
        return wrapper
    return decorator


# 便捷函数
def record_llm_call(duration_ms: float, provider: str, model: str):
    """记录LLM调用性能"""
    monitor.record_histogram("llm_call_duration", duration_ms, {"provider": provider, "model": model})
    monitor.record_counter("llm_call_count", 1, {"provider": provider, "model": model})


def record_db_query(duration_ms: float, db_type: str, operation: str):
    """记录数据库查询性能"""
    monitor.record_histogram("db_query_duration", duration_ms, {"db_type": db_type, "operation": operation})
    monitor.record_counter("db_query_count", 1, {"db_type": db_type, "operation": operation})


def record_agent_execution(duration_ms: float, agent_name: str, status: str):
    """记录Agent执行性能"""
    monitor.record_histogram("agent_execution_duration", duration_ms, {"agent": agent_name, "status": status})
    monitor.record_counter("agent_execution_count", 1, {"agent": agent_name, "status": status})


def record_task_progress(task_id: str, progress: float):
    """记录任务进度"""
    monitor.record_gauge(f"task_progress_{task_id}", progress)
