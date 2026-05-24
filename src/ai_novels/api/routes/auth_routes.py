"""
认证路由 — 用户注册、登录、信息查询

@file: api/routes/auth_routes.py
@date: 2026-05-24
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_novels.api.auth.dependencies import get_workflow_context
from ai_novels.api.auth.jwt import create_access_token
from ai_novels.api.auth.password import hash_password, verify_password
from ai_novels.core.context import WorkflowContext
from ai_novels.database.tenant_session import get_tenant_session
from ai_novels.models.user import User
from ai_novels.models.tenant import Tenant

router = APIRouter(prefix="/api/v2/auth", tags=["auth"])


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(
    username: str,
    email: str = "",
    password: str = "",
    tenant_id: str = "default",
):
    """用户注册

    Args:
        username: 用户名 (唯一, 按租户隔离)
        email: 邮箱 (可选)
        password: 密码 (至少 6 位)
        tenant_id: 租户 ID, 默认注册到 "default" 租户

    Returns:
        {"access_token": str, "token_type": "bearer", "user": {...}}
    """
    if not username or len(username) < 2:
        raise HTTPException(status_code=422, detail="Username too short")

    if password and len(password) < 6:
        raise HTTPException(status_code=422, detail="Password too short")

    session = await get_tenant_session()
    try:
        # 检查用户名唯一性 (按 tenant)
        stmt = select(User).where(
            User.username == username,
            User.tenant_id == tenant_id,
        )
        result = await session.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing:
            raise HTTPException(
                status_code=409,
                detail=f"Username '{username}' already exists in this tenant",
            )

        # 确保租户存在
        if tenant_id != "default":
            t_stmt = select(Tenant).where(Tenant.id == tenant_id)
            t_result = await session.execute(t_stmt)
            if not t_result.scalar_one_or_none():
                raise HTTPException(status_code=404, detail=f"Tenant '{tenant_id}' not found")

        # 创建用户
        hashed = hash_password(password) if password else ""
        user = User(
            username=username,
            email=email,
            hashed_password=hashed,
            tenant_id=tenant_id,
            roles=["viewer"],
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

        # 签发 JWT
        access_token = await create_access_token({
            "sub": user.id,
            "tenant_id": tenant_id,
            "name": username,
            "email": email,
            "roles": ["viewer"],
            "tier": "free",
        })

        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "tenant_id": user.tenant_id,
                "roles": user.roles,
            },
        }

    except HTTPException:
        await session.rollback()
        raise
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await session.close()


@router.post("/login")
async def login(username: str, password: str, tenant_id: str = "default"):
    """用户登录

    Args:
        username: 用户名
        password: 密码
        tenant_id: 租户 ID, 默认 "default"

    Returns:
        {"access_token": str, "token_type": "bearer", "user": {...}, "tenant": {...}}
    """
    if not username or not password:
        raise HTTPException(status_code=422, detail="Username and password required")

    session = await get_tenant_session()
    try:
        stmt = select(User).where(
            User.username == username,
            User.tenant_id == tenant_id,
            User.is_active == True,
        )
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

        if not user or not verify_password(password, user.hashed_password):
            raise HTTPException(status_code=401, detail="Invalid credentials")

        # 获取租户信息
        t_stmt = select(Tenant).where(Tenant.id == tenant_id)
        t_result = await session.execute(t_stmt)
        tenant = t_result.scalar_one_or_none()
        tier = tenant.tier if tenant else "free"

        # 更新最后登录时间
        from datetime import datetime, timezone
        user.last_login_at = datetime.now(timezone.utc)
        session.add(user)
        await session.commit()

        # 签发 JWT
        access_token = await create_access_token({
            "sub": user.id,
            "tenant_id": tenant_id,
            "name": username,
            "email": user.email,
            "roles": user.roles,
            "tier": tier,
        })

        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "roles": user.roles,
            },
            "tenant": {
                "id": tenant_id,
                "tier": tier,
            },
        }

    except HTTPException:
        await session.rollback()
        raise
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await session.close()


@router.get("/me")
async def me(ctx: WorkflowContext = Depends(get_workflow_context)):
    """当前用户信息 (需认证)"""
    return {
        "user_id": ctx.user_id,
        "username": ctx.identity.user.username,
        "email": ctx.identity.user.email,
        "roles": list(ctx.identity.user.roles),
        "tenant": {
            "id": ctx.tenant_id,
            "name": ctx.identity.tenant.tenant_name,
            "tier": ctx.identity.tenant.tier.value,
            "features": list(ctx.identity.tenant.features),
        },
        "trace_id": ctx.trace_id,
    }
