"""
API中间件测试
"""

import pytest
import time
from unittest.mock import Mock, AsyncMock, patch
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.testclient import TestClient

from deepnovel.api.middleware import (
    RequestContext,
    RequestIDMiddleware,
    TimingMiddleware,
    LoggingMiddleware
)


class TestRequestContext:
    """测试请求上下文"""

    def test_set_and_get(self):
        """测试设置和获取上下文"""
        RequestContext.set("key1", "value1")
        assert RequestContext.get("key1") == "value1"

    def test_get_with_default(self):
        """测试获取不存在的键返回默认值"""
        assert RequestContext.get("nonexistent", "default") == "default"
        assert RequestContext.get("nonexistent") is None

    def test_clear(self):
        """测试清除上下文"""
        RequestContext.set("key1", "value1")
        RequestContext.set("key2", "value2")
        RequestContext.clear()
        
        assert RequestContext.get("key1") is None
        assert RequestContext.get("key2") is None

    def test_to_dict(self):
        """测试转换为字典"""
        RequestContext.set("key1", "value1")
        RequestContext.set("key2", "value2")
        
        result = RequestContext.to_dict()
        assert result == {"key1": "value1", "key2": "value2"}


class TestRequestIDMiddleware:
    """测试请求ID中间件"""

    @pytest.mark.asyncio
    async def test_generate_request_id(self):
        """测试生成请求ID"""
        async def mock_app(scope, receive, send):
            pass
        
        middleware = RequestIDMiddleware(mock_app)
        
        # 创建模拟请求
        mock_request = Mock(spec=Request)
        mock_request.headers = {}
        mock_request.state = Mock()
        
        # 创建模拟响应
        mock_response = Mock(spec=Response)
        mock_response.headers = {}
        
        # 模拟call_next
        async def call_next(request):
            return mock_response
        
        response = await middleware.dispatch(mock_request, call_next)
        
        # 验证请求ID被生成并设置
        assert hasattr(mock_request.state, 'request_id')
        assert mock_request.state.request_id is not None
        assert len(mock_request.state.request_id) == 36  # UUID长度

    @pytest.mark.asyncio
    async def test_use_existing_request_id(self):
        """测试使用现有请求ID"""
        async def mock_app(scope, receive, send):
            pass
        
        middleware = RequestIDMiddleware(mock_app)
        
        existing_id = "existing-request-id"
        mock_request = Mock(spec=Request)
        mock_request.headers = {"X-Request-ID": existing_id}
        mock_request.state = Mock()
        
        mock_response = Mock(spec=Response)
        mock_response.headers = {}
        
        async def call_next(request):
            return mock_response
        
        response = await middleware.dispatch(mock_request, call_next)
        
        assert mock_request.state.request_id == existing_id


class TestTimingMiddleware:
    """测试耗时监控中间件"""

    @pytest.mark.asyncio
    async def test_record_duration(self):
        """测试记录请求耗时"""
        async def mock_app(scope, receive, send):
            pass
        
        middleware = TimingMiddleware(mock_app, slow_request_threshold=5.0)
        
        mock_request = Mock(spec=Request)
        mock_request.state = Mock()
        mock_request.method = "GET"
        mock_request.url.path = "/test"
        
        mock_response = Mock(spec=Response)
        mock_response.status_code = 200
        mock_response.headers = {}
        
        async def call_next(request):
            await AsyncMock()()  # 模拟异步操作
            return mock_response
        
        with patch.object(middleware.monitor, 'record_histogram') as mock_record:
            with patch.object(middleware.monitor, 'record_counter') as mock_counter:
                response = await middleware.dispatch(mock_request, call_next)
                
                # 验证性能指标被记录
                mock_record.assert_called()
                mock_counter.assert_called_with(f"requests_{mock_response.status_code}")

    @pytest.mark.asyncio
    async def test_slow_request_warning(self):
        """测试慢请求警告"""
        async def mock_app(scope, receive, send):
            pass
        
        middleware = TimingMiddleware(mock_app, slow_request_threshold=0.001)
        
        mock_request = Mock(spec=Request)
        mock_request.state = Mock()
        mock_request.state.request_id = "test-id"
        mock_request.method = "GET"
        mock_request.url.path = "/test"
        
        mock_response = Mock(spec=Response)
        mock_response.status_code = 200
        mock_response.headers = {}
        
        async def slow_call_next(request):
            time.sleep(0.01)  # 模拟慢请求
            return mock_response
        
        with patch.object(middleware.monitor, 'record_histogram'):
            with patch.object(middleware.monitor, 'record_counter'):
                with patch('deepnovel.api.middleware.logger') as mock_logger:
                    response = await middleware.dispatch(mock_request, slow_call_next)
                    
                    # 验证慢请求被记录
                    mock_logger.warning.assert_called()


class TestLoggingMiddleware:
    """测试日志中间件"""

    @pytest.mark.asyncio
    async def test_log_request(self):
        """测试记录请求日志"""
        async def mock_app(scope, receive, send):
            pass
        
        middleware = LoggingMiddleware(mock_app)
        
        mock_request = Mock(spec=Request)
        mock_request.state = Mock()
        mock_request.state.request_id = "test-id"
        mock_request.method = "POST"
        mock_request.url.path = "/api/test"
        mock_request.url.query = "param=value"
        mock_request.query_params = "param=value"
        mock_request.client = Mock()
        mock_request.client.host = "127.0.0.1"
        mock_request.headers = {"user-agent": "test-agent"}
        
        mock_response = Mock(spec=Response)
        mock_response.status_code = 200
        
        async def call_next(request):
            return mock_response
        
        with patch('deepnovel.api.middleware.logger') as mock_logger:
            response = await middleware.dispatch(mock_request, call_next)
            
            # 验证请求被记录
            mock_logger.api.assert_called()

    @pytest.mark.asyncio
    async def test_skip_excluded_paths(self):
        """测试跳过排除的路径"""
        async def mock_app(scope, receive, send):
            pass
        
        middleware = LoggingMiddleware(mock_app, exclude_paths=["/health"])
        
        mock_request = Mock(spec=Request)
        mock_request.url.path = "/health"
        
        mock_response = Mock(spec=Response)
        
        async def call_next(request):
            return mock_response
        
        with patch('deepnovel.api.middleware.logger') as mock_logger:
            response = await middleware.dispatch(mock_request, call_next)
            
            # 验证日志未被记录
            mock_logger.api.assert_not_called()

    @pytest.mark.asyncio
    async def test_log_error_response(self):
        """测试记录错误响应"""
        async def mock_app(scope, receive, send):
            pass
        
        middleware = LoggingMiddleware(mock_app)
        
        mock_request = Mock(spec=Request)
        mock_request.state = Mock()
        mock_request.state.request_id = "test-id"
        mock_request.method = "GET"
        mock_request.url.path = "/api/test"
        mock_request.query_params = ""
        mock_request.client = Mock()
        mock_request.client.host = "127.0.0.1"
        mock_request.headers = {}
        
        mock_response = Mock(spec=Response)
        mock_response.status_code = 500
        
        async def call_next(request):
            return mock_response
        
        with patch('deepnovel.api.middleware.logger') as mock_logger:
            response = await middleware.dispatch(mock_request, call_next)
            
            # 验证请求被记录（LoggingMiddleware只记录请求开始，不区分成功/错误）
            mock_logger.api.assert_called()
