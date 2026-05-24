"""
租户上下文中间件 — 入口层

职责: 从 HTTP 请求中提取认证信息, 构建 WorkflowContext,
      同时写入 contextvars(旧代码兼容) 和 request.state(更旧代码兼容)。

安全:
  - auth_mode=optional: 无 token 时使用 WorkflowContext.default() (Phase 1)
  - auth_mode=required: 无 token 时返回 401 (Phase 2)
  - token 解码失败: 返回 401, 不降级到 default
  - finally 块确保 context 清理, 防止跨请求泄漏
"""

from typing import Optional

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from ai_novels.core.context import (
    WorkflowContext,
    set_current_context,
)
from ai_novels.api.auth.jwt import verify_jwt
from ai_novels.config.hub import get_config_hub


class TenantContextMiddleware(BaseHTTPMiddleware):
    """租户上下文中间件

    前置条件: 必须在 CORS 中间件之后注册
    后置条件: 所有请求(包括 401)都会在 finally 中清理 context
    """

    def __init__(self, app, auth_mode: Optional[str] = None):
        super().__init__(app)
        self._hub = get_config_hub()
        self._auth_mode = auth_mode or self._hub.get("auth.mode", "optional")

    async def dispatch(self, request: Request,
                       call_next: RequestResponseEndpoint) -> Response:
        ctx: Optional[WorkflowContext] = None
        token = self._extract_token(request)

        # Step 1: 有 token → 验证并构建上下文
        if token:
            payload = await verify_jwt(token)
            if payload is not None:
                ctx = WorkflowContext.from_jwt_payload(payload)
            elif self._auth_mode == "required":
                return JSONResponse(
                    status_code=401,
                    content={
                        "error": True,
                        "code": "AUTH_INVALID_TOKEN",
                        "message": "无效或过期的令牌",
                    },
                )

        # Step 2: 无 token / 匿名 → 模式决策
        if ctx is None:
            if self._auth_mode == "required":
                return JSONResponse(
                    status_code=401,
                    content={
                        "error": True,
                        "code": "AUTH_REQUIRED",
                        "message": "需要认证令牌",
                    },
                )
            ctx = WorkflowContext.default()

        # Step 3: 双路注入
        set_current_context(ctx)
        request.state.ctx = ctx
        request.state.tenant_id = ctx.tenant_id
        request.state.user_id = ctx.user_id
        request.state.trace_id = ctx.trace_id

        # Step 4: 请求处理 (finally 保证清理)
        try:
            response = await call_next(request)
            response.headers["X-Trace-ID"] = ctx.trace_id
            return response
        finally:
            set_current_context(None)

    def _extract_token(self, request: Request) -> Optional[str]:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            return auth[7:]
        api_key = request.headers.get("X-API-Key")
        return api_key
