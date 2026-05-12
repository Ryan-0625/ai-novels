"""
性能监控模块测试

@file: tests/test_performance_monitor.py
@date: 2026-04-08
@version: 1.0.0
"""

import pytest
import time
from ai_novels.core.performance_monitor import (
    PerformanceMonitor,
    MetricType,
    MetricValue,
    timed,
    count_calls,
    record_llm_call,
    record_db_query
)


class TestMetricValue:
    """指标值测试"""
    
    def test_metric_value_creation(self):
        """测试指标值创建"""
        metric = MetricValue(
            name="test_metric",
            value=100.0,
            metric_type=MetricType.COUNTER,
            labels={"env": "test"}
        )
        
        assert metric.name == "test_metric"
        assert metric.value == 100.0
        assert metric.metric_type == MetricType.COUNTER
        assert metric.labels == {"env": "test"}
    
    def test_metric_value_to_dict(self):
        """测试指标值转字典"""
        metric = MetricValue(
            name="test",
            value=50,
            metric_type=MetricType.GAUGE
        )
        
        result = metric.to_dict()
        assert result["name"] == "test"
        assert result["value"] == 50
        assert result["type"] == "gauge"


class TestPerformanceMonitor:
    """性能监控器测试"""
    
    def setup_method(self):
        """每个测试前清理监控器"""
        monitor = PerformanceMonitor()
        monitor.clear()
    
    def test_record_counter(self):
        """测试记录计数器"""
        monitor = PerformanceMonitor()
        monitor.record_counter("requests", 1)
        monitor.record_counter("requests", 1)
        
        assert monitor.get_counter("requests") == 2
    
    def test_record_gauge(self):
        """测试记录仪表盘"""
        monitor = PerformanceMonitor()
        monitor.record_gauge("active_users", 100)
        
        assert monitor.get_gauge("active_users") == 100
    
    def test_record_histogram(self):
        """测试记录直方图"""
        monitor = PerformanceMonitor()
        
        for i in range(10):
            monitor.record_histogram("response_time", float(i * 10))
        
        stats = monitor.get_histogram_stats("response_time")
        assert stats["count"] == 10
        assert stats["min"] == 0
        assert stats["max"] == 90
    
    def test_timer(self):
        """测试计时器"""
        monitor = PerformanceMonitor()
        
        timer_id = monitor.start_timer("operation")
        time.sleep(0.01)  # 10ms
        duration = monitor.stop_timer(timer_id)
        
        assert duration is not None
        assert duration >= 10  # 至少10ms
    
    def test_timed_execution(self):
        """测试计时执行块"""
        monitor = PerformanceMonitor()
        
        with monitor.timed_execution("test_operation"):
            time.sleep(0.01)
        
        # timed_execution使用start_timer/stop_timer，数据存储在_metrics而非_histograms
        # 验证计时器数据被记录
        metrics = monitor.get_metric("test_operation")
        assert len(metrics) == 1
        assert metrics[0].name == "test_operation"
    
    def test_threshold_alert(self):
        """测试阈值告警"""
        monitor = PerformanceMonitor()
        monitor.set_threshold("cpu_usage", max_value=80)
        
        # 超过阈值
        monitor.record_gauge("cpu_usage", 90)
        # 应该触发告警（通过日志）
    
    def test_get_all_metrics(self):
        """测试获取所有指标"""
        monitor = PerformanceMonitor()
        
        monitor.record_counter("counter1", 5)
        monitor.record_gauge("gauge1", 100)
        monitor.record_histogram("hist1", 50)
        
        all_metrics = monitor.get_all_metrics()
        
        assert "counters" in all_metrics
        assert "gauges" in all_metrics
        assert "histograms" in all_metrics
        assert all_metrics["counters"]["counter1"] == 5
        assert all_metrics["gauges"]["gauge1"] == 100


class TestDecorators:
    """装饰器测试"""
    
    def test_timed_decorator(self):
        """测试计时装饰器"""
        
        @timed("test_function")
        def slow_function():
            time.sleep(0.01)
            return "done"
        
        result = slow_function()
        assert result == "done"
    
    def test_count_calls_decorator(self):
        """测试计数装饰器"""
        monitor = PerformanceMonitor()
        monitor.clear()
        
        @count_calls("function_calls")
        def test_func():
            return "result"
        
        test_func()
        test_func()
        test_func()
        
        assert monitor.get_counter("function_calls") == 3


class TestConvenienceFunctions:
    """便捷函数测试"""
    
    def test_record_llm_call(self):
        """测试记录LLM调用"""
        monitor = PerformanceMonitor()
        monitor.clear()
        
        record_llm_call(100.0, "openai", "gpt-4")
        
        stats = monitor.get_histogram_stats("llm_call_duration")
        assert stats["count"] == 1
        assert monitor.get_counter("llm_call_count") == 1
    
    def test_record_db_query(self):
        """测试记录数据库查询"""
        monitor = PerformanceMonitor()
        monitor.clear()
        
        record_db_query(50.0, "mysql", "select")
        
        stats = monitor.get_histogram_stats("db_query_duration")
        assert stats["count"] == 1
