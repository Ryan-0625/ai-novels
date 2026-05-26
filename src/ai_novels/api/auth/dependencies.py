"""
FastAPI 认证相关依赖注入

提供 get_workflow_context 用于路由层显式获取执行上下文。
"""

from typing import Optional

from fastapi import Depends, HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from ai_novels.core.context import WorkflowContext, get_current_context
from ai_novels.api.auth.jwt import verify_jwt
from ai_novels.config.hub import get_config_hub


security = HTTPBearer(auto_error=False)


async def get_workflow_context(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security),
) -> WorkflowContext:
    """获取 WorkflowContext (认证失败抛 401)"""
    # 优先验证显式携带的 token
    if credentials is not None:
        payload = await verify_jwt(credentials.credentials)
        if payload is None:
            raise HTTPException(status_code=401, detail="Invalid or expired token")
        return WorkflowContext.from_jwt_payload(payload)

    # 无 token — 尝试中间件上下文
    ctx = get_current_context()
    if ctx is not None and ctx.identity.user.user_id != "local":
        return ctx

    # 最终兜底
    if get_config_hub().get("auth.mode", "required") == "required":
        raise HTTPException(status_code=401, detail="Authentication required")
    return WorkflowContext.default()


async def get_optional_context() -> WorkflowContext:
    """获取 WorkflowContext (认证可选, 失败返回 default)"""
    ctx = get_current_context()
    if ctx is not None:
        return ctx
    return WorkflowContext.default()
