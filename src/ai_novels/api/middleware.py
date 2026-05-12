"""
API中间件层

@file: api/middleware.py
@date: 2026-04-08
@version: 2.0.0
@description: FastAPI中间件 - 请求追踪、响应标准化、性能监控
"""

import time
import uuid
import json
from typing import Any, Dict, Optional, Callable
from functools import wraps

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from ai_novels.utils import get_logger
from ai_novels.core.performance_monitor import get_performance_monitor

logger = get_logger()


class RequestContext:
    """请求上下文管理器"""
    
    _context: Dict[str, Any] = {}
    
    @classmethod
    def set(cls, key: str, value: Any):
        """设置上下文值"""
        cls._context[key] = value
    
    @classmethod
    def get(cls, key: str, default: Any = None) -> Any:
        """获取上下文值"""
        return cls._context.get(key, default)
    
    @classmethod
    def clear(cls):
        """清除上下文"""
        cls._context.clear()
    
    @classmethod
    def to_dict(cls) -> Dict[str, Any]:
        """转换为字典"""
        return cls._context.copy()


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    请求ID中间件
    
    为每个请求生成唯一ID，便于追踪和日志关联
    """
    
    def __init__(self, app: ASGIApp, header_name: str = "X-Request-ID"):
        super().__init__(app)
        self.header_name = header_name
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # 从请求头获取或生成请求ID
        request_id = request.headers.get(self.header_name)
        if not request_id:
            request_id = str(uuid.uuid4())
        
        # 设置到请求上下文
        RequestContext.set("request_id", request_id)
        request.state.request_id = request_id
        
        # 处理请求
        response = await call_next(request)
        
        # 添加请求ID到响应头
        response.headers[self.header_name] = request_id
        
        # 清除上下文
        RequestContext.clear()
        
        return response


class TimingMiddleware(BaseHTTPMiddleware):
    """
    请求耗时监控中间件
    
    记录每个请求的耗时和性能指标
    """
    
    def __init__(
        self,
        app: ASGIApp,
        slow_request_threshold: float = 1.0,  # 慢请求阈值（秒）
        enable_logging: bool = True
    ):
        super().__init__(app)
        self.slow_request_threshold = slow_request_threshold
        self.enable_logging = enable_logging
        self.monitor = get_performance_monitor()
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()
        
        # 记录请求开始
        request.state.start_time = start_time
        
        try:
            response = await call_next(request)
        except Exception as e:
            # 记录异常耗时
            duration = time.time() - start_time
            self.monitor.record_histogram("request_duration_error", duration)
            raise
        
        # 计算耗时
        duration = time.time() - start_time
        
        # 记录指标
        self.monitor.record_histogram("request_duration", duration)
        self.monitor.record_counter(f"requests_{response.status_code}")
        
        # 添加耗时到响应头
        response.headers["X-Response-Time"] = f"{duration:.3f}s"
        
        # 慢请求警告
        if duration > self.slow_request_threshold and self.enable_logging:
            logger.warning(
                "Slow request detected",
                request_id=getattr(request.state, "request_id", None),
                method=request.method,
                path=request.url.path,
                duration=duration,
                threshold=self.slow_request_threshold
            )
        
        return response


class LoggingMiddleware(BaseHTTPMiddleware):
    """
    请求日志中间件
    
    记录请求和响应的详细信息
    """
    
    def __init__(
        self,
        app: ASGIApp,
        log_request_body: bool = False,
        log_response_body: bool = False,
        exclude_paths: list = None
    ):
        super().__init__(app)
        self.log_request_body = log_request_body
        self.log_response_body = log_response_body
        self.exclude_paths = exclude_paths or ["/health", "/docs", "/redoc", "/openapi.json"]
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # 跳过排除的路径
        if any(request.url.path.startswith(path) for path in self.exclude_paths):
            return await call_next(request)
        
        request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
        start_time = time.time()
        
        # 记录请求
        log_data = {
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "query": str(request.query_params),
            "client": request.client.host if request.client else None,
            "user_agent": request.headers.get("user-agent"),
        }
        
        if self.log_request_body:
            try:
                body = await request.body()
                if body:
                    log_data["body"] = body.decode("utf-8")[:1000]  # 限制长度
                    # 重新设置body以便后续读取
                    async def receive():
                        return {"type": "http.request", "body": body}
                    request._receive = receive
            except Exception:
                pass
        
        logger.api("Request started", **log_data)
        
        # 处理请求
        try:
            response = await call_next(request)
            
            # 计算耗时
            duration = time.time() - start_time
            
            # 记录响应
            logger.api(
                "Request completed",
                request_id=request_id,
                status_code=response.status_code,
                duration=f"{duration:.3f}s"
            )
            
            return response
            
        except Exception as e:
            duration = time.time() - start_time
            logger.error(
                "Request failed",
                request_id=request_id,
                error=str(e),
                duration=f"{duration:.3f}s"
            )
            raise


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    速率限制中间件
    
    基于令牌桶算法的请求限流
    """
    
    def __init__(
        self,
        app: ASGIApp,
        requests_per_minute: int = 60,
        burst_size: int = 10,
        key_func: Callable[[Request], str] = None
    ):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.burst_size = burst_size
        self.key_func = key_func or self._default_key_func
        self._buckets: Dict[str, Dict[str, Any]] = {}
    
    @staticmethod
    def _default_key_func(request: Request) -> str:
        """默认的限流键生成函数（基于客户端IP）"""
        return request.client.host if request.client else "unknown"
    
    def _check_rate_limit(self, key: str) -> tuple[bool, int]:
        """
        检查是否超过速率限制
        
        Returns:
            (是否允许, 剩余请求数)
        """
        import time
        
        now = time.time()
        window = 60.0  # 1分钟窗口
        
        if key not in self._buckets:
            self._buckets[key] = {
                "tokens": self.burst_size,
                "last_update": now
            }
        
        bucket = self._buckets[key]
        
        # 计算新增的令牌
        elapsed = now - bucket["last_update"]
        tokens_to_add = elapsed * (self.requests_per_minute / window)
        bucket["tokens"] = min(self.burst_size, bucket["tokens"] + tokens_to_add)
        bucket["last_update"] = now
        
        # 检查是否有可用令牌
        if bucket["tokens"] >= 1:
            bucket["tokens"] -= 1
            remaining = int(bucket["tokens"])
            return True, remaining
        
        return False, 0
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        key = self.key_func(request)
        allowed, remaining = self._check_rate_limit(key)
        
        if not allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Rate limit exceeded",
                    "retry_after": 60
                },
                headers={
                    "X-RateLimit-Limit": str(self.requests_per_minute),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(time.time() + 60))
                }
            )
        
        response = await call_next(request)
        
        # 添加限流头
        response.headers["X-RateLimit-Limit"] = str(self.requests_per_minute)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        
        return response


class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """
    错误处理中间件
    
    统一处理异常并返回标准化错误响应
    """
    
    def __init__(
        self,
        app: ASGIApp,
        include_traceback: bool = False,
        log_errors: bool = True
    ):
        super().__init__(app)
        self.include_traceback = include_traceback
        self.log_errors = log_errors
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        try:
            return await call_next(request)
            
        except Exception as e:
            request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
            
            if self.log_errors:
                logger.error(
                    "Unhandled exception",
                    request_id=request_id,
                    error=str(e),
                    exc_info=True
                )
            
            # 构建错误响应
            error_response = {
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "An internal error occurred",
                    "request_id": request_id
                }
            }
            
            if self.include_traceback:
                import traceback
                error_response["error"]["traceback"] = traceback.format_exc()
            
            return JSONResponse(
                status_code=500,
                content=error_response
            )


class CORSMiddlewareConfig:
    """CORS配置"""
    
    def __init__(
        self,
        allow_origins: list = None,
        allow_credentials: bool = True,
        allow_methods: list = None,
        allow_headers: list = None,
        max_age: int = 600
    ):
        self.allow_origins = allow_origins or ["*"]
        self.allow_credentials = allow_credentials
        self.allow_methods = allow_methods or ["*"]
        self.allow_headers = allow_headers or ["*"]
        self.max_age = max_age


def create_standard_response(
    data: Any = None,
    message: str = "success",
    code: str = "OK",
    request_id: str = None,
    meta: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    创建标准化响应格式
    
    Args:
        data: 响应数据
        message: 消息
        code: 状态码
        request_id: 请求ID
        meta: 元数据
        
    Returns:
        标准化响应字典
    """
    response = {
        "success": code == "OK",
        "code": code,
        "message": message,
        "data": data,
        "request_id": request_id or RequestContext.get("request_id"),
        "timestamp": time.time()
    }
    
    if meta:
        response["meta"] = meta
    
    return response


class ResponseStandardizationMiddleware(BaseHTTPMiddleware):
    """
    响应标准化中间件
    
    将所有响应转换为统一格式
    """
    
    def __init__(
        self,
        app: ASGIApp,
        exclude_paths: list = None,
        exclude_status_codes: list = None
    ):
        super().__init__(app)
        self.exclude_paths = exclude_paths or ["/docs", "/redoc", "/openapi.json"]
        self.exclude_status_codes = exclude_status_codes or [204, 304]
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        
        # 跳过排除的路径和状态码
        if any(request.url.path.startswith(path) for path in self.exclude_paths):
            return response
        
        if response.status_code in self.exclude_status_codes:
            return response
        
        # 只处理JSON响应
        content_type = response.headers.get("content-type", "")
        if "application/json" not in content_type:
            return response
        
        # 读取原始响应体
        body = b""
        async for chunk in response.body_iterator:
            body += chunk
        
        try:
            original_data = json.loads(body)
            
            # 如果已经是标准格式，直接返回
            if isinstance(original_data, dict) and "success" in original_data:
                return Response(
                    content=json.dumps(original_data),
                    status_code=response.status_code,
                    headers=dict(response.headers),
                    media_type="application/json"
                )
            
            # 转换为标准格式
            standardized = create_standard_response(
                data=original_data,
                request_id=getattr(request.state, "request_id", None)
            )
            
            return JSONResponse(
                content=standardized,
                status_code=response.status_code,
                headers=dict(response.headers)
            )
            
        except json.JSONDecodeError:
            # 非JSON响应，直接返回
            return Response(
                content=body,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type
            )


def get_middleware_stack(
    enable_request_id: bool = True,
    enable_timing: bool = True,
    enable_logging: bool = True,
    enable_rate_limit: bool = False,
    enable_error_handling: bool = True,
    enable_response_standardization: bool = False
) -> list:
    """
    获取中间件栈配置
    
    返回中间件类列表，按执行顺序排列
    """
    middlewares = []
    
    if enable_error_handling:
        middlewares.append(ErrorHandlingMiddleware)
    
    if enable_request_id:
        middlewares.append(RequestIDMiddleware)
    
    if enable_rate_limit:
        middlewares.append(RateLimitMiddleware)
    
    if enable_logging:
        middlewares.append(LoggingMiddleware)
    
    if enable_timing:
        middlewares.append(TimingMiddleware)
    
    if enable_response_standardization:
        middlewares.append(ResponseStandardizationMiddleware)
    
    return middlewares
